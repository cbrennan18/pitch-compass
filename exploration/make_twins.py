#!/usr/bin/env python3
"""
Pitch Compass -- twins.json for the explorer (relaunch step 2, item 4).
For every pitch in docs/data/cast.json, find its NEAREST neighbour within
300 m and the angle between their bearings. Stdlib only; reads the frozen
cast.json, writes docs/data/twins.json. No new pull, no page/JS changes.

Method matches the frozen "twins" stat's distance/angle functions
(analyse_extra.py: dist_m, axis_diff) -- same 300 m threshold, same
axial (0-90) angle fold -- but here it's nearest-neighbour PER PITCH,
keyed by cast index, not an all-pairs list.
"""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
CAST = os.path.join(HERE, "..", "docs", "data", "cast.json")
OUT = os.path.join(HERE, "..", "docs", "data", "twins.json")

LAT0 = 53.4  # matches analyse_extra.py's dist_m reference latitude


def dist_m(lat1, lon1, lat2, lon2):
    dx = (lon2 - lon1) * math.cos(math.radians(LAT0)) * 111320
    dy = (lat2 - lat1) * 110540
    return math.hypot(dx, dy)


def axis_diff(a, b):
    d = abs(a - b) % 180
    return min(d, 180 - d)


cast = json.load(open(CAST))
fields = cast["fields"]
LAT, LON, BR = fields.index("lat"), fields.index("lon"), fields.index("bearing")
data = cast["data"]
n = len(data)

# cheap spatial bucketing (0.01deg ~ 1.1km cells) so this stays fast at n=2707
CELL = 0.01
buckets = {}
for i, row in enumerate(data):
    key = (round(row[LAT] / CELL), round(row[LON] / CELL))
    buckets.setdefault(key, []).append(i)

twins = {}
with_neighbour = 0
for i, row in enumerate(data):
    lat, lon, brg = row[LAT], row[LON], row[BR]
    cy, cx = round(lat / CELL), round(lon / CELL)
    best_j, best_d = None, None
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            for j in buckets.get((cy + dy, cx + dx), ()):
                if j == i:
                    continue
                d = dist_m(lat, lon, data[j][LAT], data[j][LON])
                if d <= 300 and (best_d is None or d < best_d):
                    best_d, best_j = d, j
    if best_j is not None:
        with_neighbour += 1
        twins[str(i)] = [best_j, round(best_d, 1),
                          round(axis_diff(brg, data[best_j][BR]), 1)]

with open(OUT, "w") as f:
    json.dump({
        "fields": ["neighbor_idx", "dist_m", "angle_deg"],
        "note": "nearest neighbour within 300m per cast.json index; "
                "angle_deg is the axial (0-90) difference between bearings; "
                "entries with no neighbour within 300m are omitted",
        "n_with_neighbour": with_neighbour,
        "n_total": n,
        "data": twins,
    }, f, separators=(",", ":"))

size = os.path.getsize(OUT)
print(f"twins.json: {with_neighbour} of {n} pitches have a neighbour within 300m")
print(f"file size: {size} bytes ({size/1024:.1f} KB)")
