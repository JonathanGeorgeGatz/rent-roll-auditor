#!/usr/bin/env python3
"""EP40 independent checker — the Rent Roll Auditor law (SPEC.md), reimplemented in Python.
Reads the two CSVs + dials, emits the same JSON shape as the page engine. No shared code."""
import sys, csv, json, io, re, calendar

def cents(s):
    if s is None: return None
    t = str(s).strip().lstrip("$").replace(",", "")
    if not re.fullmatch(r"-?\d+(\.\d{1,2})?", t): return None
    neg = t.startswith("-"); t = t.lstrip("-")
    w, _, f = t.partition(".")
    c = int(w) * 100 + (int((f + "00")[:2]) if f else 0)
    return -c if neg else c

def pdate(s):
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", str(s).strip())
    if not m: return None
    y, mo, d = int(m[1]), int(m[2]), int(m[3])
    if not (1 <= mo <= 12): return None
    if not (1 <= d <= calendar.monthrange(y, mo)[1]): return None
    return (y, mo, d)

iso = lambda y, mo, d: "%04d-%02d-%02d" % (y, mo, d)
mk = lambda y, mo: "%04d-%02d" % (y, mo)
def rdiv(num, den):  # round half up, num>=0
    return (num * 2 + den) // (2 * den)

def add_days(y, mo, d, n):
    d += n
    while d > calendar.monthrange(y, mo)[1]:
        d -= calendar.monthrange(y, mo)[1]; mo += 1
        if mo == 13: mo, y = 1, y + 1
    return (y, mo, d)

def run(roll_text, pay_text, grace=5, tol=0, repeat=3):
    out = dict(refusals_roll=[], refusals_pay=[], missed=[], short=[], late=[], chronic=[],
               dup_held=[], orphans=[], unapplied=[], holdover=[], counts={}, self_audit="OK")
    rr = [r for r in csv.reader(io.StringIO(roll_text)) if any(c.strip() for c in r)]
    pr = [r for r in csv.reader(io.StringIO(pay_text)) if any(c.strip() for c in r)]
    want_r = ["unit","tenant","monthly_rent","lease_start","lease_end","deposit"]
    want_p = ["payment_id","date","unit","amount","method"]
    hr = {w: next((i for i,c in enumerate(rr[0]) if c.strip().lower()==w), -1) for w in want_r} if rr else {}
    hp = {w: next((i for i,c in enumerate(pr[0]) if c.strip().lower()==w), -1) for w in want_p} if pr else {}
    if not rr or any(v < 0 for v in hr.values()): return {"fatal": "rent roll header must be " + ",".join(want_r)}
    if not pr or any(v < 0 for v in hp.values()): return {"fatal": "payments header must be " + ",".join(want_p)}
    g = lambda row, idx: row[idx].strip() if idx < len(row) else ""

    leases = {}; roll_ok = 0
    for i, row in enumerate(rr[1:], start=2):
        unit = g(row, hr["unit"]); tenant = g(row, hr["tenant"])
        if not unit: out["refusals_roll"].append({"line": i, "reason": "unit is blank"}); continue
        if not tenant: out["refusals_roll"].append({"line": i, "reason": "tenant is blank"}); continue
        rent = cents(g(row, hr["monthly_rent"]))
        if rent is None or rent <= 0:
            out["refusals_roll"].append({"line": i, "reason": "monthly_rent missing or not a positive amount — unit " + unit}); continue
        ls = pdate(g(row, hr["lease_start"]))
        if not ls: out["refusals_roll"].append({"line": i, "reason": "lease_start is not a real ISO date — unit " + unit}); continue
        le = None
        if g(row, hr["lease_end"]) != "":
            le = pdate(g(row, hr["lease_end"]))
            if not le: out["refusals_roll"].append({"line": i, "reason": "lease_end is not a real ISO date — unit " + unit}); continue
            if iso(*le) < iso(*ls):
                out["refusals_roll"].append({"line": i, "reason": "lease_end is before lease_start — unit " + unit}); continue
        if unit in leases:
            out["refusals_roll"].append({"line": i, "reason": "duplicate unit " + unit + " — row refused, first row kept"}); continue
        leases[unit] = dict(unit=unit, tenant=tenant, rent=rent, ls=ls, le=le)
        roll_ok += 1

    ids = set(); pays = []; pay_ok = 0
    for i, row in enumerate(pr[1:], start=2):
        pid = g(row, hp["payment_id"])
        ref = lambda why: out["refusals_pay"].append({"line": i, "reason": why})
        if not pid: ref("payment_id is blank"); continue
        if pid in ids: ref("duplicate payment_id " + pid + " — later row refused"); continue
        dt = pdate(g(row, hp["date"]))
        if not dt: ref("date “" + g(row, hp["date"]) + "” is not a real ISO date — payment " + pid); continue
        unit = g(row, hp["unit"])
        if not unit: ref("unit is blank — payment " + pid); continue
        amt = cents(g(row, hp["amount"]))
        if amt is None: ref("amount “" + g(row, hp["amount"]) + "” is not a number — payment " + pid); continue
        if amt < 0: ref("negative amount — this auditor reads rent income, not refunds — payment " + pid); continue
        if amt == 0: ref("zero amount — payment " + pid); continue
        ids.add(pid); pays.append(dict(id=pid, dt=dt, unit=unit, amt=amt)); pay_ok += 1
    if not pays: return {"fatal": "no valid payment rows"}

    as_of = max(iso(*p["dt"]) for p in pays)
    ay, am, ad = int(as_of[:4]), int(as_of[5:7]), int(as_of[8:10])
    ey, em = (ay, am) if ad == calendar.monthrange(ay, am)[1] else ((ay, am - 1) if am > 1 else (ay - 1, 12))
    out["audit_end"] = mk(ey, em)
    end_idx = ey * 12 + em - 1

    for L in leases.values():
        months = []
        y, mo = L["ls"][0], L["ls"][1]
        stop = end_idx if not L["le"] else min(L["le"][0] * 12 + L["le"][1] - 1, end_idx)
        while y * 12 + mo - 1 <= stop:
            dim = calendar.monthrange(y, mo)[1]
            first = (y, mo) == (L["ls"][0], L["ls"][1])
            owed = L["rent"]
            if first and L["ls"][2] > 1: owed = rdiv(L["rent"] * (dim - L["ls"][2] + 1), dim)
            if L["le"] and (y, mo) == (L["le"][0], L["le"][1]) and L["le"][2] < dim:
                owed = rdiv(L["rent"] * (L["le"][2] - L["ls"][2] + 1), dim) if first and L["ls"][2] > 1 else rdiv(L["rent"] * L["le"][2], dim)
            months.append(dict(key=mk(y, mo), owed=owed, paid=0, allocs=[], first=first))
            mo += 1
            if mo == 13: mo, y = 1, y + 1
        L["months"] = months; L["credit"] = 0

    pays.sort(key=lambda p: (iso(*p["dt"]), p["id"]))
    seen = set(); allocated = dup_c = orph_c = 0
    for p in pays:
        k = (p["unit"], iso(*p["dt"]), p["amt"])
        if k in seen:
            out["dup_held"].append({"payment_id": p["id"], "unit": p["unit"], "date": iso(*p["dt"]), "cents": p["amt"]}); dup_c += p["amt"]; continue
        seen.add(k)
        L = leases.get(p["unit"])
        if not L:
            out["orphans"].append({"payment_id": p["id"], "unit": p["unit"], "date": iso(*p["dt"]), "cents": p["amt"]}); orph_c += p["amt"]; continue
        if L["le"] and iso(*p["dt"]) > iso(*L["le"]):
            out["holdover"].append({"payment_id": p["id"], "unit": p["unit"], "date": iso(*p["dt"])})
        rem = p["amt"]
        for M in L["months"]:
            if rem == 0: break
            bal = M["owed"] - M["paid"]
            if bal <= 0: continue
            take = min(bal, rem)
            M["paid"] += take; rem -= take; allocated += take
            M["allocs"].append((iso(*p["dt"]), M["paid"]))
        L["credit"] += rem

    def ukey(u):
        try: return (int(u), "")
        except ValueError: return (0, u)
    units = sorted(leases.values(), key=lambda L: ukey(L["unit"]))
    scheduled = uncollected = late_total = 0
    chronic = {}
    for L in units:
        for M in L["months"]:
            scheduled += M["owed"]
            bal = M["owed"] - M["paid"]
            if bal == M["owed"] and M["owed"] > 0:
                out["missed"].append({"unit": L["unit"], "tenant": L["tenant"], "month": M["key"], "cents": bal}); uncollected += bal; continue
            if bal > tol:
                out["short"].append({"unit": L["unit"], "tenant": L["tenant"], "month": M["key"], "cents_short": bal}); uncollected += bal; continue
            if M["owed"] > tol:
                completion = next((d for d, pa in M["allocs"] if pa >= M["owed"] - tol), None)
                if M["first"] and L["ls"][2] > 1:
                    ge = iso(*add_days(L["ls"][0], L["ls"][1], L["ls"][2], grace))
                else:
                    ge = M["key"] + "-%02d" % (1 + grace)
                if completion and completion > ge:
                    out["late"].append({"unit": L["unit"], "month": M["key"], "paid_day": completion})
                    late_total += 1; chronic[L["unit"]] = chronic.get(L["unit"], 0) + 1
        if L["credit"] > 0: out["unapplied"].append({"unit": L["unit"], "cents": L["credit"]})
    for L in units:
        n = chronic.get(L["unit"], 0)
        if n >= repeat: out["chronic"].append({"tenant": L["tenant"], "unit": L["unit"], "n": n})

    out["late_count"] = late_total
    out["scheduled_cents"] = scheduled
    out["collected_cents"] = allocated
    out["uncollected_cents"] = uncollected
    out["pct_uncollected"] = rdiv(uncollected * 1000, scheduled) / 10 if scheduled > 0 else 0
    out["banner"] = uncollected * 20 > scheduled
    out["counts"] = {"roll_total": len(rr) - 1, "roll_ok": roll_ok, "pay_total": len(pr) - 1, "pay_ok": pay_ok}

    sa = []
    if roll_ok + len(out["refusals_roll"]) != len(rr) - 1: sa.append("rent roll rows do not re-tally")
    if pay_ok + len(out["refusals_pay"]) != len(pr) - 1: sa.append("payment rows do not re-tally")
    valid_total = sum(p["amt"] for p in pays)
    unap = sum(u["cents"] for u in out["unapplied"])
    if allocated + unap + dup_c + orph_c != valid_total:
        sa.append("conservation check failed: allocated + credit + held + orphans != valid payments")
    rc = rcc = 0
    for L in units:
        for M in L["months"]:
            bal = M["owed"] - M["paid"]
            if (bal == M["owed"] and M["owed"] > 0) or bal > tol: rc += 1; rcc += bal
    if rc != len(out["missed"]) + len(out["short"]) or rcc != uncollected: sa.append("suspect recount mismatch")
    if len(out["refusals_pay"]) * 4 > len(pr) - 1: sa.append("more than a quarter of the payment rows were unreadable")
    if len(out["refusals_roll"]) * 4 > len(rr) - 1: sa.append("more than a quarter of the rent roll rows were unreadable")
    if sa: out["self_audit"] = "; ".join(sa); out["trust_banner"] = True

    def um(x): return (ukey(x["unit"]), x["month"])
    out["missed"].sort(key=um); out["short"].sort(key=um); out["late"].sort(key=um)
    for k in ("dup_held", "orphans", "holdover"): out[k].sort(key=lambda x: x["payment_id"])
    return out

if __name__ == "__main__":
    roll, pay = open(sys.argv[1]).read(), open(sys.argv[2]).read()
    grace = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    tol = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    repeat = int(sys.argv[5]) if len(sys.argv) > 5 else 3
    print(json.dumps(run(roll, pay, grace, tol, repeat), indent=1, sort_keys=True))
