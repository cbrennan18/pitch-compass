#!/usr/bin/env python3
"""
Pitch Compass -- superlatives.csv, v2 (relaunch step 2 follow-up, item 4).
N/S/E/W are regenerated from the pool of pitches named via the GPF join
(docs/data/clubs.json) rather than OSM's own sparse 'name' field --
2,106 candidates instead of 395. June-sunset, N-S, E-W and loneliest keep
the author's picks from design/verify.md unchanged. Output drops L/W
(location + name only), per instruction.

Stdlib only. Reads docs/data/cast.json, docs/data/clubs.json. Writes
exploration/superlatives.csv (overwrites the v1 file).
"""
import json, math, csv, os

HERE = os.path.dirname(os.path.abspath(__file__))
CAST = os.path.join(HERE, "..", "docs", "data", "cast.json")
CLUBS = os.path.join(HERE, "..", "docs", "data", "clubs.json")
OUT = os.path.join(HERE, "superlatives.csv")

cast = json.load(open(CAST))
fields = cast["fields"]
IDX = {f: i for i, f in enumerate(fields)}
data = cast["data"]

clubs = json.load(open(CLUBS))["data"]
named_via_join = [int(i) for i in clubs.keys()]

def gpf_name(i):
    c = clubs[str(i)]
    club, pitch = c["club"], c["pitch_name"]
    return f"{club} -- {pitch}" if pitch else club

rows = []

def top3(label, key_fn, reverse):
    ranked = sorted(named_via_join, key=key_fn, reverse=reverse)[:3]
    for rank, i in enumerate(ranked, 1):
        r = data[i]
        rows.append({"category": label, "rank": rank, "name": gpf_name(i),
                     "county": r[IDX["county"]], "lat": r[IDX["lat"]], "lon": r[IDX["lon"]]})
    return ranked[0]

winner_n = top3("northernmost", lambda i: data[i][IDX["lat"]], True)
winner_s = top3("southernmost", lambda i: data[i][IDX["lat"]], False)
winner_w = top3("westernmost", lambda i: data[i][IDX["lon"]], False)
winner_e = top3("easternmost", lambda i: data[i][IDX["lon"]], True)

# ---- locked picks, unchanged from design/verify.md, L/W dropped ----
LOCKED = [
    ("closest_to_june_sunset_axis", 1, "Ramor United Park", "Cavan", 53.8306, -7.0693),
    ("closest_to_true_ns", 1, "Pearse Park", "Longford", 53.7393, -7.8049),
    ("closest_to_true_ew", 1, "Blarney GAA Club", "Cork", 51.9291, -8.5615),
    ("loneliest", 1, "Eoghan Rua Pitch", "Derry", 55.1646, -6.696),
]
for cat, rank, name, county, lat, lon in LOCKED:
    rows.append({"category": cat, "rank": rank, "name": name, "county": county,
                 "lat": lat, "lon": lon})

cols = ["category", "rank", "name", "county", "lat", "lon"]
with open(OUT, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(rows)

print(f"superlatives.csv rewritten: {len(rows)} rows")
print(f"\nnew winners (GPF-named pool, n={len(named_via_join)} candidates):")
for label, i in [("northernmost", winner_n), ("southernmost", winner_s),
                  ("westernmost", winner_w), ("easternmost", winner_e)]:
    print(f"  {label}: {gpf_name(i)} ({data[i][IDX['county']]})")

print(f"\nprevious (OSM-name-pool, n=395) winners were:")
print("  northernmost: Malin Gaelic Football Pitch (Donegal)")
print("  southernmost: Castlehaven GAA Main Pitch (Cork)")
print("  westernmost: Portmagee GAA (Kerry)")
print("  easternmost: Saul GAC (Down)")
