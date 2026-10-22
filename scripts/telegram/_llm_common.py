"""Shared pieces for the two LLM scripts (11_type_llm.py, 23_extract_impacts.py):
prompt loading, the one canonical post->user-message formatter, dry-run printing, cost estimate.
No network access in this module."""
from __future__ import annotations
import json, math, re, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import llm
from _common import ROOT, log

PROMPTS = Path(__file__).resolve().parent / "prompts"

# Prices $/MTok from the claude-api skill (cached 2026-10-06). cache_read = 0.1x input (Sonnet 5.5: $0.20
# per the skill; Haiku assumed 0.1x), cache_write = 1.25x input (5-minute TTL).
PRICES = {
    "claude-haiku-5-5":  {"in": 0.10, "out": 0.50,  "cache_read": 0.01, "cache_write": 0.125},
    "claude-sonnet-5-5": {"in": 2.00, "out": 10.00, "cache_read": 0.20, "cache_write": 2.50},
}
BATCH_DISCOUNT = 0.5   # Message Batches API; not wired into llm.py, quoted for the decision only

CHANNEL_REGION = {
    "synegubov": "Kharkiv oblast military administration",
    "VA_Kyiv": "Kyiv CITY military administration (not Kyiv oblast)",
    "odeskaODA": "Odesa oblast military administration",
    "dnipropetrovskaODA": "Dnipropetrovsk oblast military administration",
    "zoda_gov_ua": "Zaporizhzhia oblast military administration",
    "kozytskyy_maksym_official": "Lviv oblast military administration",
    "kpszsu": "Ukrainian Air Force (national)",
    "war_monitor": "volunteer monitor channel (national)",
    "monitoringwar": "volunteer monitor channel (national)",
}


def load_prompt(name: str, **subs: str) -> str:
    """Read prompts/<name>.md; drop a leading HTML comment (author notes); fill {{KEY}} slots."""
    txt = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    txt = re.sub(r"\A\s*<!--.*?-->\s*", "", txt, flags=re.S)
    for k, v in subs.items():
        txt = txt.replace("{{" + k + "}}", v)
    left = re.findall(r"\{\{[A-Z_]+\}\}", txt)
    if left:
        raise ValueError(f"prompt {name}: unfilled slots {left}")
    return txt.strip() + "\n"


def fmt_post(channel: str, ts_kyiv, edit_ts_utc, text: str) -> str:
    """The ONLY place a post becomes a user message. Few-shot examples in the prompts use this exact shape."""
    t = pd.Timestamp(ts_kyiv)
    edited = "yes" if (edit_ts_utc is not None and not pd.isna(edit_ts_utc)) else "no"
    return (f"channel: {channel} ({CHANNEL_REGION.get(channel, 'unknown')})\n"
            f"post_date_kyiv: {t.strftime('%Y-%m-%d')}\n"
            f"post_time_kyiv: {t.strftime('%H:%M')}\n"
            f"edited_after_posting: {edited}\n"
            f"text:\n{text.strip()}")


def row_user(r) -> str:
    return fmt_post(r.channel, r.ts_kyiv, r.edit_ts_utc, r.text)


# ---------------------------------------------------------------- token / cost estimate
def est_tokens(s: str, chars_per_token: float) -> int:
    return math.ceil(len(s) / chars_per_token)


def estimate_cost(model: str, system: str, users: list[str], *, out_tokens_per_call: int,
                  chars_per_token: float, cache_system: bool, label: str, n_calls: int | None = None) -> dict:
    """n_calls: price this many calls instead of len(users), scaling user tokens proportionally."""
    p = PRICES[model]
    n = n_calls or len(users)
    sys_t = est_tokens(system, chars_per_token)
    user_t = sum(est_tokens(u, chars_per_token) for u in users) * n / max(len(users), 1)
    out_t = n * out_tokens_per_call
    if cache_system:
        # one write per ~5 min window is negligible next to n reads; count a single write
        sys_cost = (sys_t * p["cache_write"] + max(n - 1, 0) * sys_t * p["cache_read"]) / 1e6
    else:
        sys_cost = n * sys_t * p["in"] / 1e6
    in_cost = user_t * p["in"] / 1e6
    out_cost = out_t * p["out"] / 1e6
    total = sys_cost + in_cost + out_cost
    return {"label": label, "model": model, "calls": n, "system_tokens": sys_t,
            "user_tokens_total": int(user_t), "out_tokens_total": out_t,
            "system_cost": round(sys_cost, 2), "user_cost": round(in_cost, 2),
            "output_cost": round(out_cost, 2), "total": round(total, 2),
            "total_batch_api": round(total * BATCH_DISCOUNT, 2),
            "if_system_not_cached": round((n * sys_t * p["in"] / 1e6) + in_cost + out_cost, 2)}


def print_cost(c: dict) -> None:
    print(f"\n--- cost estimate: {c['label']} ({c['model']}) ---")
    print(f"calls {c['calls']:,}  system~{c['system_tokens']:,} tok  user total~{c['user_tokens_total']:,} tok  "
          f"output total~{c['out_tokens_total']:,} tok")
    print(f"system ${c['system_cost']}  user ${c['user_cost']}  output ${c['output_cost']}  "
          f"=> TOTAL ${c['total']}   (Batch API -50%: ${c['total_batch_api']}; "
          f"without prompt caching: ${c['if_system_not_cached']})")


def print_requests(posts, system, schema, model, *, max_tokens, effort, cache_system):
    """Print the exact messages.create kwargs for each post (system printed in full once)."""
    for i, (ident, user) in enumerate(posts):
        req = llm.build_request(system, user, schema, model, max_tokens=max_tokens, effort=effort,
                                cache_system=cache_system)
        print(f"\n===== request {i+1}/{len(posts)}  {ident} =====")
        if i > 0:
            req = dict(req)
            req["system"] = f"<same system block as request 1: {len(system)} chars>"
            req["output_config"] = {"effort": effort, "format": "<same json_schema as request 1>"}
        print(json.dumps(req, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------- resumable concurrent runner
def run_calls(items, fn, *, model: str, workers: int, prompt_version: str, warm_first: bool = True):
    """items: list of (ident, user, meta). fn(user, meta) -> dict. Returns {ident: output | None}.
    Resumable because fn goes through llm.call (on-disk cache). The first uncached call runs alone so the
    API prompt-cache entry exists before the pool starts. Failures are logged (ident only) and left as None."""
    out, todo = {}, []
    for ident, user, meta in items:
        key = llm.cache_key(prompt_version, model, user)
        cp = llm.cache_path(prompt_version, key)
        if cp.exists():
            out[ident] = json.loads(cp.read_text(encoding="utf-8"))["output"]
        else:
            todo.append((ident, user, meta))
    log(f"{prompt_version}: {len(out):,} cached, {len(todo):,} to call")
    if not todo:
        return out
    if warm_first:
        ident, user, meta = todo.pop(0)
        out[ident] = fn(user, meta)
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fn, u, m): i for i, u, m in todo}
        for f in as_completed(futs):
            ident = futs[f]
            try:
                out[ident] = f.result()
            except llm.LLMKeyMissing:
                raise
            except Exception as e:   # refusal, max_tokens, transient API error after SDK retries
                log(f"FAILED {ident}: {type(e).__name__}: {str(e)[:160]}")
                out[ident] = None
            done += 1
            if done % 500 == 0:
                log(f"  {done:,}/{len(todo):,}  {llm.STATS}")
    return out
