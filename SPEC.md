# EP40 — The Rent Roll Auditor — engine spec (the law, prompt 3)

Inputs: two CSVs.
- RENT ROLL: header `unit,tenant,monthly_rent,lease_start,lease_end,deposit`
- PAYMENTS: header `payment_id,date,unit,amount,method`

All money is an integer count of cents, parsed from `$1,234.56`-style or plain decimal; rounding half-up once at parse. Dates are ISO `YYYY-MM-DD` only.

## Refusals (row-level, printed by name with reason; refused rows take no further part)
Rent roll row refused when: unit blank · tenant blank · monthly_rent missing/not a number/≤ 0 · lease_start invalid or missing · lease_end present but invalid · lease_end before lease_start · duplicate unit (second and later occurrences refused).
Payment row refused when: payment_id blank or a duplicate of an earlier row's id (the later row is refused) · date invalid (not ISO, or an impossible calendar date — 2026-02-30 is refused, leap rules apply) · unit blank · amount missing/not a number · amount negative (reason: this auditor reads rent income, not refunds) · amount zero.

## Audit window
as_of = the latest valid payment date. The audit runs through the last full calendar month ending on or before as_of. For each lease, the months owed are every calendar month from the month of lease_start through the earlier of (lease_end month, audit end month). First month owed is prorated when lease_start is after the 1st: owed = round_half_up(rent_cents × days_from_start_to_month_end_inclusive / days_in_month). Last month prorated the same way when lease_end is before that month's last day. A lease with blank lease_end owes every month through the audit end month.

## Allocation
Valid payments sort by (date, payment_id). The duplicate test precedes the orphan test. DUPLICATE SUSPECT: a payment whose (unit, date, amount) exactly matches an EARLIER valid payment is flagged `duplicate-held` and is NOT allocated; its dollars sit in a held bucket. An ORPHAN: unit not on the (accepted) rent roll — flagged, never allocated. Every other payment applies to its unit's owed months oldest-first: fill the oldest month with a remaining balance, overflow rolls forward. Money left after every owed month is full = `unapplied credit` for that unit (flagged). A payment dated after the unit's lease_end is additionally flagged `after lease end` (holdover) whatever it allocates to.

## Findings (computed at as_of)
- MISSED MONTH: an owed month with balance == full owed amount.
- SHORT MONTH: an owed month with 0 < balance < owed. Forgiveness dial `tolerance` ∈ {0, 500, 2000} cents: a balance ≤ tolerance is treated as paid in full (not listed, not counted in uncollected).
- LATE MONTH: only for months with owed > tolerance and a completion date. The COMPLETION DATE of a month is the date of the allocation that first brought its allocated total to ≥ (owed − tolerance). The month is LATE when its completion date is after graceEnd = the month's (1 + grace)th day. Grace dial `grace` ∈ {3, 5, 10} (grace 5 ⇒ on time through the 6th). A month that never completes is missed/short, not late. For a lease's prorated FIRST month, graceEnd = lease_start + grace days instead. `paid_day` reported = the completion date.
- CHRONIC LATE TENANT: a tenant with ≥ `repeat` late months, repeat dial ∈ {2, 3, 5}.
- DUPLICATE-HELD, ORPHANS, UNAPPLIED CREDIT, HOLDOVER: as above, listed with dollars.
- UNCOLLECTED = Σ missed balances + Σ short balances (post-tolerance). Headline % = uncollected / Σ owed (scheduled) over the audit window.
- BANNER: when uncollected > 5% of scheduled → "DO NOT CALL THIS COLLECTED".

## Self-audit (every run)
(1) each file's rows re-tallied two independent ways (accepted + refused == total parsed lines). (2) conservation: Σ allocated + Σ unapplied credit + Σ duplicate-held + Σ orphan dollars == Σ valid payment cents. (3) the suspect list (count AND cents) recounted independently from the month grid. (4) a file with more than a quarter of its data rows refused cannot be vouched for. A missing/mangled header is fatal (no findings at all). Any failure → banner "DO NOT TRUST THIS AUDIT" with the reason; findings withheld.

## Outputs (both implementations emit this JSON shape)
{scheduled_cents, collected_cents (=Σ allocated), uncollected_cents, pct_uncollected (1dp, half-up), banner (bool), missed:[{unit,tenant,month,cents}...], short:[{unit,tenant,month,cents_short}...], late_count, late:[{unit,month,paid_day}...], chronic:[{tenant,unit,n}...], dup_held:[{payment_id,unit,date,cents}], orphans:[{payment_id,unit,date,cents}], unapplied:[{unit,cents}], holdover:[{payment_id,unit,date}], refusals_roll:[{line,reason}], refusals_pay:[{line,reason}], counts:{roll_total,roll_ok,pay_total,pay_ok}, audit_end:"YYYY-MM", self_audit:"OK"|reason}
Sort orders: missed/short by (unit asc, month asc); late by (unit, month); chronic by unit; dup/orphans/holdover by payment_id; unapplied by unit; refusals by line number.
