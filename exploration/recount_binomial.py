#!/usr/bin/env python3
"""
Pitch Compass -- recount (relaunch step 2 follow-up, item 5).
E-W/N-S/diagonal split over county_main + national (one row per county
+ Croke Park, n=33) after the verify.md + GPF reconciliation updates,
with an exact two-sided binomial test of the diagonal share against 1/3
(the three +-30deg bands each cover exactly 60 of the 180-degree axial
range, so 1/3 is the natural null). Same split reported over all 2,707
cast.json pitches for contrast, using the standard z-test the rest of
the project uses at that sample size.

Stdlib only. Reads exploration/county_grounds.csv, docs/data/cast.json.
"""
import csv, json, math, os
from math import comb

HERE = os.path.dirname(os.path.abspath(__file__))
def p(*parts): return os.path.join(HERE, *parts)


def axis_diff(a, b):
    d = abs(a - b) % 180
    return min(d, 180 - d)


def classify(bearing):
    if axis_diff(bearing, 90) <= 30:
        return "ew"
    if axis_diff(bearing, 0) <= 30:
        return "ns"
    return "diag"


def exact_binomial_two_sided(k, n, p0):
    """Two-sided exact binomial p-value: sum P(X=i) for all i whose
    probability is <= P(X=k) (the standard two-sided exact test)."""
    pmf = [comb(n, i) * (p0 ** i) * ((1 - p0) ** (n - i)) for i in range(n + 1)]
    pk = pmf[k]
    return sum(pi for pi in pmf if pi <= pk * (1 + 1e-9))


def two_sided_z(z):
    return math.erfc(abs(z) / math.sqrt(2))


# ---- county_main + national (n=33) ----
cg = list(csv.DictReader(open(p("county_grounds.csv"))))
main_rows = [r for r in cg if r["role"] in ("county_main", "national") and r["pitch_bearing"]]

counts_main = {"ew": 0, "ns": 0, "diag": 0}
for r in main_rows:
    counts_main[classify(float(r["pitch_bearing"]))] += 1

n_main = len(main_rows)
diag_main = counts_main["diag"]
p_exact = exact_binomial_two_sided(diag_main, n_main, 1/3)

print("=" * 60)
print(f"COUNTY_MAIN + NATIONAL (n={n_main})")
print("=" * 60)
for cat in ("ew", "ns", "diag"):
    c = counts_main[cat]
    print(f"  {cat:<6} {c:>3} / {n_main} = {c/n_main*100:5.1f}%")
print(f"\n  exact two-sided binomial test, diagonal share vs 1/3:")
print(f"  observed diagonal = {diag_main}/{n_main} ({diag_main/n_main*100:.1f}%), "
      f"expected = {n_main/3:.1f} ({100/3:.1f}%)")
print(f"  p = {p_exact:.4f}")

skipped = [r["name"] for r in cg if r["role"] in ("county_main", "national") and not r["pitch_bearing"]]
if skipped:
    print(f"\n  excluded (needs_manual, no bearing): {skipped}")

# ---- all 2,707 cast pitches, for contrast ----
cast = json.load(open(p("..", "docs", "data", "cast.json")))
fields = cast["fields"]
BR = fields.index("bearing")
data = cast["data"]

counts_all = {"ew": 0, "ns": 0, "diag": 0}
for row in data:
    counts_all[classify(row[BR])] += 1

n_all = len(data)
diag_all = counts_all["diag"]
p_expected = 1/3
z = (diag_all - n_all * p_expected) / math.sqrt(n_all * p_expected * (1 - p_expected))
p_z = two_sided_z(z)

print()
print("=" * 60)
print(f"ALL CAST PITCHES (n={n_all}), for contrast")
print("=" * 60)
for cat in ("ew", "ns", "diag"):
    c = counts_all[cat]
    print(f"  {cat:<6} {c:>4} / {n_all} = {c/n_all*100:5.1f}%")
print(f"\n  z-test (normal approximation, appropriate at this n), diagonal vs 1/3:")
print(f"  observed diagonal = {diag_all}/{n_all} ({diag_all/n_all*100:.1f}%), "
      f"expected = {n_all/3:.1f} ({100/3:.1f}%)")
print(f"  z = {z:.2f}, p = {p_z:.2e}")
