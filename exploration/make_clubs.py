#!/usr/bin/env python3
"""
Pitch Compass -- docs/data/clubs.json, the GPF name join (relaunch step 2
follow-up, item 2). For each cast.json pitch, the nearest GAA Pitch
Finder record within 300 m becomes its club + pitch_name.
Source: gaapitchfinder_data.csv, commit 256eb08482b2c385614415db18841f8a43e1f61b,
CC BY 4.0. Credit: "Club and pitch location data from GAA Pitch Finder by
Ryan McGuinness: https://gaapitchfinder.com"

Method: island scope (File=='Ireland', not Country=='Ireland' -- Northern
Ireland rows carry Country='United Kingdom'). Nearest within 300 m wins;
ties/multiple candidates within 300 m are recorded as n_matches but the
nearest is still used. A dry run before building this (see reflection)
found 77.8% coverage at 300 m, median match distance 29.6 m -- the
threshold is not over-matching.

Stdlib only. Reads docs/data/cast.json and the pinned GPF clone. Writes
docs/data/clubs.json.
"""
import json, csv, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
CAST = os.path.join(HERE, "..", "docs", "data", "cast.json")
OUT = os.path.join(HERE, "..", "docs", "data", "clubs.json")
GPF_PATH = "/tmp/gaapitchfinder/gaapitchfinder_data.csv"
GPF_COMMIT = "256eb08482b2c385614415db18841f8a43e1f61b"

LAT0 = 53.4
def dist_m(lat1, lon1, lat2, lon2):
    dx = (lon2 - lon1) * math.cos(math.radians(LAT0)) * 111320
    dy = (lat2 - lat1) * 110540
    return math.hypot(dx, dy)

cast = json.load(open(CAST))
fields = cast["fields"]
IDX = {f: i for i, f in enumerate(fields)}
data = cast["data"]

gpf = [r for r in csv.DictReader(open(GPF_PATH)) if r["File"] == "Ireland"]

CELL = 0.01
buckets = {}
for i, r in enumerate(gpf):
    key = (round(float(r["Latitude"]) / CELL), round(float(r["Longitude"]) / CELL))
    buckets.setdefault(key, []).append(i)

clubs = {}
county_total = {}
county_matched = {}

for i, row in enumerate(data):
    lat, lon = row[IDX["lat"]], row[IDX["lon"]]
    county = row[IDX["county"]]
    county_total[county] = county_total.get(county, 0) + 1

    cy, cx = round(lat / CELL), round(lon / CELL)
    cands = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            for j in buckets.get((cy + dy, cx + dx), ()):
                r = gpf[j]
                d = dist_m(lat, lon, float(r["Latitude"]), float(r["Longitude"]))
                if d <= 300:
                    cands.append((d, r))
    if cands:
        cands.sort(key=lambda c: c[0])
        d, r = cands[0]
        clubs[str(i)] = {
            "club": r["Club"], "pitch_name": r["Pitch"],
            "match_dist_m": round(d, 1), "n_matches": len(cands),
        }
        county_matched[county] = county_matched.get(county, 0) + 1

with open(OUT, "w") as f:
    json.dump({
        "note": "nearest GAA Pitch Finder (gaapitchfinder_data.csv) record within 300m, "
                "keyed by cast.json index; n_matches counts all GPF candidates within 300m "
                "(nearest is used regardless)",
        "source": "https://github.com/ryanmcg2203/gaapitchfinder",
        "source_commit": GPF_COMMIT,
        "licence": "CC BY 4.0",
        "credit": "Club and pitch location data from GAA Pitch Finder by Ryan McGuinness: "
                  "https://gaapitchfinder.com",
        "n": len(clubs), "n_total": len(data),
        "data": clubs,
    }, f, separators=(",", ":"))

size = os.path.getsize(OUT)
print(f"clubs.json: {len(clubs)} of {len(data)} cast pitches matched ({len(clubs)/len(data)*100:.1f}%)")
print(f"file size: {size} bytes ({size/1024:.1f} KB)")
print(f"\ncoverage by county:")
for county in sorted(county_total):
    tot = county_total[county]
    m = county_matched.get(county, 0)
    print(f"  {county:<12} {m:>4}/{tot:<4} {m/tot*100:5.1f}%")
