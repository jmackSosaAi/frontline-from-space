# Research assistant guide

(Same text as the recruiting email. Placeholders in [brackets] are filled per assistant.)

Hi [Name],

Thanks for helping with this. The task is simple: you read a short English text, look at what an AI pulled out of it, and click Yes or No. Everything is already translated and set up for you.

WHAT THE PROJECT IS

I'm writing a research paper on how well NASA's satellite fire data shows what is happening in the war in Ukraine. Part of the project used an AI to read about 18,000 posts from official Ukrainian regional government channels and pull out each strike they reported: where it hit, the weapon, what was hit, how many people were killed or wounded, and when. You'll check a sample of its work. Your answers become the accuracy numbers in the paper, so the only thing that matters is being careful and honest. "No" is just as useful as "Yes."

YOUR ROLE

[Keep the role(s) this person is doing and delete the other.]

- Role A: strike details. File: ra_impacts. 165 rows, about 2 hours.
- Role B: missed strikes and categories. Files: ra_empty (35 rows) and ra_typing (100 rows), plus the first 20 rows of ra_impacts (imp-001 to imp-020). Both roles do those 20 on purpose, so I can measure how often two people agree. About 1.5-2 hours.

WHAT'S ATTACHED

- qa_checker.html: a page that opens in your web browser. It works offline and uploads nothing. This is the easiest way.
- Your files, each in two versions: .csv (for the checker page) and .xlsx (if you'd rather use Excel or Google Sheets instead).

OPTION 1: THE CHECKER PAGE (RECOMMENDED)

1. Save all the attachments into one folder.
2. Double-click qa_checker.html. It opens in your browser.
3. Type your initials in the box at the top.
4. Click "Choose File" and pick your .csv file.
5. For each row:
   a. Read the post on the left. It's already in English.
   b. On the right, look at what the AI extracted.
   c. Answer each question with Yes or No (click, or press Y / N).
   d. Click Next (or press the right-arrow key).
6. Your answers save automatically. If you close the page, reopen it, choose the same file and you'll be where you left off.
7. When you're done, click "Save CSV" and email me the downloaded file (named like ra_impacts_AB.csv).

OPTION 2: SPREADSHEET

1. Open your .xlsx file.
2. Each row is one item. Read the "text_en" column (the post, in English) and compare it with the AI's columns next to it.
3. In the yellow columns, pick y or n from the dropdown. If you put n in chk_all_found, type the number of missed strikes in the next column (required). Notes go in the note column.
4. Save the file and email it back to me with your initials added to the name.

THE QUESTIONS (WHEN TO ANSWER YES)

Role A (ra_impacts). Each row is ONE strike the AI found. If the post reports several, the place shown tells you which one this row is about.
- Place correct? The place matches where the post says this strike hit. Spelling differences don't matter. "withheld by the post" is correct if the post hides the location.
- Weapon correct? The weapon matches the post. "(none named)" is correct if the post names no weapon.
- Target type correct? The category fits what was hit: residential (homes, apartments), energy (power, gas, fuel), industrial (factories, businesses), military, transport (roads, rail, ports), agri (farms, grain), other, unknown.
- Killed / wounded correct? Both match the post for this strike. "none reported" is correct if the post reports nobody hurt.
- Date / time correct? The date (and time, if shown) is when the strike happened. "Overnight" posts usually mean the night before the post.
- Did the AI find every strike in this post? "Strikes AI found in this post" shows how many it found in the whole post. Yes if the post reports that many separate strikes and no more. If No, you MUST also type how many strikes it missed (a number, 1 or more) in the next box. A row isn't finished without it.

Role B, ra_empty. The AI found NO strike in these posts.
- Does this post report a strike or attack? Yes if it describes at least one strike, shelling or attack at a named place. No if it's about something else (air-raid alert only, repairs, aid, statements).

Role B, ra_typing. Each post was given a category.
- Category correct? Yes if right. If No, type the right one:
  alert = air-raid alert announced; all_clear = alert ended; aviation_activity = enemy aircraft in the air; launch = missiles/drones launched or incoming; track = a drone or missile's path ("heading toward X"); launch_intel = overnight totals launched or shot down; impact_report = a strike, damage or casualties at a place; daily_summary = roundup of a day or night; ua_strike_on_ru = Ukrainian strike on Russia; other = anything else.

RULES

- The English is a machine translation. If a single detail decides your answer (a number, a village name), check the Ukrainian original: in the checker page click "Show Ukrainian original", or in the spreadsheet see the "text" column. Paste it into translate.google.com if you need to.
- Judge only from the post. Don't look things up elsewhere.
- If you can't tell, answer No and write why in the note.
- If two people are doing this, don't compare answers until you've both sent your files.
- Some posts describe deaths and injuries, including of children. Take breaks; you can stop at any time.
- These files are research data: don't share them, and delete your copies once I confirm I've received yours.
- Partial work is useful. If you can't finish, send what you have.

Please send your file(s) by [date]. [Pay: $X per hour / flat $X.] If anything is unclear, email me before guessing.

Thanks again,
Jackson
