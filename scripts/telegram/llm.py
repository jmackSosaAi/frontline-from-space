"""Cached, schema-validated Claude call wrapper for the Telegram pipeline.

    from llm import call
    out = call(prompt_version="type_v1", system=SYSTEM, user=post_text, schema=SCHEMA,
               model="claude-haiku-5-5")          # -> dict validated against SCHEMA

Cache: data/interim/telegram/llm_cache/<prompt_version>/<sha256[:2]>/<sha256>.json
       key = sha256(prompt_version + "\\x1f" + model + "\\x1f" + user)
       (system prompt is part of prompt_version by contract: bump the version when it changes).
Key:   ANTHROPIC_API_KEY read from <project>/.env (or the environment). Never printed.
API:   Anthropic Python SDK >= 1.x (installed: 2.x). Structured output via
       output_config={"format": {"type": "json_schema", "schema": ...}} so the reply is
       guaranteed-valid JSON for the schema. Haiku 5.5 / Sonnet 5.5 reject non-default
       sampling params (no temperature=0): determinism comes from effort="low" + the cache.
Models (ids current as of 2026-10): claude-haiku-5-5 (typing), claude-sonnet-5-5 (extraction),
       claude-opus-5-5 (adjudication). Pricing table in the claude-api skill.
"""
from __future__ import annotations
import hashlib, json, os, sys, time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CACHE_ROOT = ROOT / "data" / "interim" / "telegram" / "llm_cache"
ENV_FILE = ROOT / ".env"

MODEL_TYPING = "claude-haiku-5-5"
MODEL_EXTRACT = "claude-sonnet-5-5"
MODEL_ADJUDICATE = "claude-opus-5-5"

_client = None
STATS = {"calls": 0, "cache_hits": 0, "input_tokens": 0, "output_tokens": 0, "refusals": 0,
         "cache_read_tokens": 0, "cache_write_tokens": 0}


class LLMKeyMissing(RuntimeError):
    pass


class LLMRefusal(RuntimeError):
    pass


def _load_env_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key and ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("ANTHROPIC_API_KEY") and "=" in line:
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    if not key:
        raise LLMKeyMissing(
            "ANTHROPIC_API_KEY not found: set it in the environment or add a line "
            f"ANTHROPIC_API_KEY=... to {ENV_FILE} (the file is gitignored). The key is never printed."
        )
    return key


def _get_client():
    global _client
    if _client is None:
        import anthropic  # imported lazily so offline scripts can import this module
        _client = anthropic.Anthropic(api_key=_load_env_key(), max_retries=4, timeout=120.0)
    return _client


def cache_key(prompt_version: str, model: str, user: str) -> str:
    h = hashlib.sha256()
    h.update(prompt_version.encode("utf-8")); h.update(b"\x1f")
    h.update(model.encode("utf-8")); h.update(b"\x1f")
    h.update(user.encode("utf-8"))
    return h.hexdigest()


def cache_path(prompt_version: str, key: str) -> Path:
    return CACHE_ROOT / prompt_version / key[:2] / f"{key}.json"


def _validate(obj: Any, schema: dict, path: str = "$") -> None:
    """Minimal JSON-schema check (type / required / enum / additionalProperties / items).
    The API already enforces the schema; this guards cache files edited by hand."""
    if "anyOf" in schema:
        errs = []
        for sub in schema["anyOf"]:
            try:
                _validate(obj, sub, path); break
            except ValueError as e:
                errs.append(str(e))
        else:
            raise ValueError(f"{path}: matches no anyOf branch ({'; '.join(errs)})")
        return
    t = schema.get("type")
    types = {"object": dict, "array": list, "string": str, "integer": int, "number": (int, float),
             "boolean": bool, "null": type(None)}
    if t:
        allowed = t if isinstance(t, list) else [t]
        ok = any(isinstance(obj, types[a]) and not (a in ("integer", "number") and isinstance(obj, bool)) for a in allowed)
        if not ok:
            raise ValueError(f"{path}: expected {t}, got {type(obj).__name__}")
    if "enum" in schema and obj not in schema["enum"]:
        raise ValueError(f"{path}: {obj!r} not in enum")
    if isinstance(obj, dict):
        props = schema.get("properties", {})
        for r in schema.get("required", []):
            if r not in obj:
                raise ValueError(f"{path}: missing required {r!r}")
        if schema.get("additionalProperties") is False:
            extra = set(obj) - set(props)
            if extra:
                raise ValueError(f"{path}: unexpected keys {sorted(extra)}")
        for k, v in obj.items():
            if k in props:
                _validate(v, props[k], f"{path}.{k}")
    if isinstance(obj, list) and "items" in schema:
        for i, v in enumerate(obj):
            _validate(v, schema["items"], f"{path}[{i}]")


def build_request(system: str, user: str, schema: dict, model: str, *, max_tokens: int = 1024,
                  effort: str = "low", cache_system: bool = True) -> dict:
    """The exact kwargs passed to client.messages.create (used by call() and by --dry-run)."""
    return dict(
        model=model,
        max_tokens=max_tokens,
        system=([{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
                if cache_system else system),
        messages=[{"role": "user", "content": user}],
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
    )


def call(prompt_version: str, system: str, user: str, schema: dict, model: str = MODEL_TYPING,
         *, max_tokens: int = 1024, effort: str = "low", use_cache: bool = True,
         meta: dict | None = None, cache_system: bool = True) -> dict:
    """One post -> one JSON object validated against `schema`. Cached by (prompt_version, model, user).

    `cache_system=True` marks the system prompt as an Anthropic prompt-cache prefix (cache_control
    ephemeral) so the long few-shot prefix is billed at the cache-read rate after the first call.
    This is the API prompt cache, unrelated to the on-disk result cache above.
    `meta` (e.g. {"channel":..., "msg_id":...}) is stored beside the result for provenance only;
    it is not part of the cache key.
    """
    key = cache_key(prompt_version, model, user)
    cp = cache_path(prompt_version, key)
    if use_cache and cp.exists():
        rec = json.loads(cp.read_text(encoding="utf-8"))
        _validate(rec["output"], schema)
        STATS["cache_hits"] += 1
        return rec["output"]

    client = _get_client()
    STATS["calls"] += 1
    resp = client.messages.create(**build_request(system, user, schema, model, max_tokens=max_tokens,
                                                  effort=effort, cache_system=cache_system))
    if resp.stop_reason == "refusal":
        STATS["refusals"] += 1
        cat = getattr(getattr(resp, "stop_details", None), "category", None)
        raise LLMRefusal(f"model refused (category={cat}); key={key[:12]}")
    if resp.stop_reason == "max_tokens":
        raise RuntimeError(f"max_tokens={max_tokens} hit before JSON completed; key={key[:12]}")
    text = next(b.text for b in resp.content if b.type == "text")
    out = json.loads(text)
    _validate(out, schema)
    u = resp.usage
    STATS["input_tokens"] += getattr(u, "input_tokens", 0) or 0
    STATS["output_tokens"] += getattr(u, "output_tokens", 0) or 0
    STATS["cache_read_tokens"] += getattr(u, "cache_read_input_tokens", 0) or 0
    STATS["cache_write_tokens"] += getattr(u, "cache_creation_input_tokens", 0) or 0

    cp.parent.mkdir(parents=True, exist_ok=True)
    rec = {"key": key, "prompt_version": prompt_version, "model": model,
           "system_sha256": hashlib.sha256(system.encode("utf-8")).hexdigest(),
           "user_sha256": hashlib.sha256(user.encode("utf-8")).hexdigest(),
           "meta": meta or {}, "output": out,
           "usage": {"input_tokens": getattr(u, "input_tokens", None),
                     "output_tokens": getattr(u, "output_tokens", None),
                     "cache_read": getattr(u, "cache_read_input_tokens", None),
                     "cache_write": getattr(u, "cache_creation_input_tokens", None)},
           "response_id": getattr(resp, "id", None), "ts": time.time()}
    tmp = cp.with_suffix(".tmp")
    tmp.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, cp)   # atomic: a crash never leaves a half-written cache file
    return out


def cache_stats(prompt_version: str) -> dict:
    d = CACHE_ROOT / prompt_version
    n = sum(1 for _ in d.rglob("*.json")) if d.exists() else 0
    return {"prompt_version": prompt_version, "cached": n, **STATS}


if __name__ == "__main__":
    # smoke test that never calls the API: key presence + cache key stability
    try:
        _load_env_key(); print("ANTHROPIC_API_KEY: present (not shown)")
    except LLMKeyMissing as e:
        print("ANTHROPIC_API_KEY: missing ->", str(e).split(":")[0], file=sys.stderr)
    print("cache_key demo:", cache_key("type_v1", MODEL_TYPING, "🛵 БпЛА на Київ")[:16])
    print("cache root:", CACHE_ROOT.relative_to(ROOT))
