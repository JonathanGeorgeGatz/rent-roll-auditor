THE RENT ROLL AUDITOR — free giveaway from Build It With AI (EP40)
Live page: https://jonathangeorgegatz.github.io/rent-roll-auditor/

Two exports — your rent roll and your payments ledger — and every rent payment has to
prove which month it paid. Missing months, short months, habitual lates, duplicate
deposits, orphan payments and holdovers, each with a name and a dollar amount. The page
runs entirely in your browser: no internet access, no account, nothing uploaded anywhere.

WHAT'S IN THIS FOLDER
  index.html ................ the Rent Roll Auditor (open it in any browser; this is the tool)
  sample/quillbrook_rent_roll.csv
  sample/quillbrook_payments.csv ... the fictional 14-unit sample portfolio from the episode
  PROMPTS.txt ............... the three prompts, exactly as used on camera
  v1.html ................... PRESERVED WRONG BUILD #1 — prompt one's output. It reported a
                              102.4% collection rate and called it healthy. Its lies are
                              labeled in comments in the source. Kept for honesty, not use.
  v2.html ................... PRESERVED WRONG BUILD #2 — prompt two's output. Calendar
                              buckets: it accused the tenant who pays early, billed a month
                              that wasn't due yet, dropped an orphan payment without a word
                              and counted a duplicated deposit as income. Lies labeled.
  checker.py ................ the independent Python re-implementation ("the rival") built
                              from SPEC.md by a separate session. Run:
                              python3 checker.py sample/quillbrook_rent_roll.csv sample/quillbrook_payments.csv 5 500 3
  SPEC.md ................... the written law both implementations follow

HOW TO USE IT WITH YOUR OWN BOOKS
  1. Export or build a rent roll CSV: unit,tenant,monthly_rent,lease_start,lease_end,deposit
     (ISO dates like 2026-01-01; leave lease_end blank for month-to-month).
  2. Export your payments from the bank or register as: payment_id,date,unit,amount,method
  3. Open index.html, paste both files (or use the file pickers), set the three dials,
     and click "Audit the books".
  Most of what gets flagged will have a boring explanation — a roommate's half-check, a
  typo'd unit number. The point is the short list with names on it.

All sample data is fictional. This is arithmetic on your own exports, not legal, tax or
collections advice.
