# analyse.py — the analysis engine for Pitch Compass. No network.
# Computes every headline finding from the frozen datasets.
#
# Inputs:
#   gaa_out/pitches.csv            GAA signal sample (from explore_gaa.py)
#   soccer_out/soccer_pitches.csv  soccer control (from soccer_control.py)
#   gaa_out/county_map.csv         pitch -> county (from assign_counties.py)
#   gaa_out/names_reviewed.csv     optional human review overrides (if present)
# Outputs:
#   stdout                         all findings, printed
#   gaa_out/names_clean.csv        every named feature, classified + deduped
#   gaa_out/names_review.csv       unique entities, for the human review pass
#   gaa_out/name_words.csv         word frequencies by bucket
#   gaa_out/name_bigrams.csv       bigram frequencies by bucket
#   gaa_out/county_stats.csv       per-county orientation stats
#   gaa_out/analysis_summary.json  every finding as data
#
# Data (c) OpenStreetMap contributors, ODbL 1.0. County stats derive from
# boundaries: Tailte Eireann (CC-BY 4.0) + OSNI (OGL).

import csv
import math
import json

# ---------------------------------------------------------------
# THE SIGNAL FILTER
# Which shapes count as real Irish pitches with a meaningful
# orientation? Everything downstream stands on this definition.
# ---------------------------------------------------------------

rows = []

def is_signal(row):
    if row["leisure"] != "pitch":
        return False
    if float(row["aspect"]) < 1.2:
        return False
    if not (2000 <= float(row["area_m2"]) <= 20000):
        return False
    if not (51.3 <= float(row["lat"]) <= 55.5):
        return False
    if not (-11.0 <= float(row["lon"]) <=-5.3):
        return False
    return True

# ---------------------------------------------------------------
# SHARED ANGLE TOOLS
# Pitch orientations are axes (0-180), not directions (0-360):
# play runs both ways, so 175 degrees and 355 degrees are the same line.
# ---------------------------------------------------------------

def axis_diff(a, b):
    d = abs(a - b) % 180
    return min(d, 180 - d)

# ---------------------------------------------------------------
# QUESTION 1: SUNSET
# Folklore says pitches avoid the setting sun. The sun sets NW in
# June, due W at equinox, SW in winter - so each season defines an
# axis, and we count pitches aligned within 15 degrees of it.
# Key comparison: June vs winter. Both axes are equally diagonal,
# so the grid effect hits both alike - any June-winter gap is the
# folklore's genuine fingerprint.
# ---------------------------------------------------------------

def sunset_azimuth(declination_deg):
    d = math.radians(declination_deg)
    lat = math.radians(53.4)
    return 360 - math.degrees(math.acos(math.sin(d) / math.cos(lat)))

def count_near_axis(rows, axis, tolerance=15):
    count = 0
    for row in rows:
        bearing = float(row["bearing_deg"])
        if axis_diff(bearing, axis) <= tolerance:
            count += 1
    return count


# ---------------------------------------------------------------
# LOAD + FILTER
# ---------------------------------------------------------------

with open("gaa_out/pitches.csv") as f:
    for row in csv.DictReader(f):
        if is_signal(row):
            rows.append(row)

print("signal sample:", len(rows))

# sunset counts by season (declination: +23.44 June, 0 equinox, -23.44 winter)
for name, decl in [("June", 23.44), ("Equinox", 0.0), ("Winter", -23.44)]:
    axis = sunset_azimuth(decl) % 180
    print(name, count_near_axis(rows, axis))

# ---------------------------------------------------------------
# QUESTION 2: TWIN PITCHES
# When a club has two pitches within 300m, does the second copy the
# first's orientation? Expect: heavy parallel + perpendicular, little between.
# ---------------------------------------------------------------

def dist_m(r1, r2):
    dx = (float(r1["lon"]) - float(r2["lon"])) * math.cos(math.radians(53.4)) * 111320
    dy = (float(r1["lat"]) - float(r2["lat"])) * 110540
    return math.hypot(dx, dy)

diffs = []
for i in range(len(rows)):
    for j in range(i + 1, len(rows)):
        if dist_m(rows[i], rows[j]) <= 300:
            b1 = float(rows[i]["bearing_deg"])
            b2 = float(rows[j]["bearing_deg"])
            diffs.append(axis_diff(b1, b2))

print("twin pitches:", len(diffs))

bins = [0, 0, 0, 0, 0, 0]
for d in diffs:
    slot = min(int(d // 15), 5)
    bins[slot] += 1

labels = ["0-15", "15-30", "30-45", "45-60", "60-75", "75-90"]
for label, count in zip(labels, bins):
    print(label, count, round(100 * count / len(diffs), 1))

# ---------------------------------------------------------------
# QUESTION 3: SIZES
# How many pitches are under regulation, and does town squeeze them?
# Regulation: length 130-145m, width 80-90m. Adult pitches only
# (length >= 100m) - below that are juvenile and training grounds.
# Caveat: polygons may trace the mown grass, not the marked lines.
# ---------------------------------------------------------------

adults = []
for row in rows:
    if float(row["length_m"]) >= 100:
        adults.append(row)

print("adult pitches:", len(adults))                    # target: 2380

lengths = sorted(float(r["length_m"]) for r in adults)
widths = sorted(float(r["width_m"]) for r in adults)
print("median length:", lengths[len(lengths) // 2])     # target: ~141
print("median width:", widths[len(widths) // 2])        # target: ~83

short = 0
narrow = 0
undersized = 0
for row in adults:
    length = float(row["length_m"])
    width = float(row["width_m"])
    if length < 130:
        short += 1
    if width < 80:
        narrow += 1
    if length < 130 or width < 80:
        undersized += 1

n = len(adults)
print("short (<130m):", round(100 * short / n, 1), "%")
print("narrow (<80m):", round(100 * narrow / n, 1), "%")
print("undersized (either):", round(100 * undersized / n, 1), "%")

# urban vs rural: within 20km of the five big cities
CITIES = [(53.3498, -6.2603), (51.8985, -8.4756), (53.2707, -9.0568),
          (52.6638, -8.6267), (54.5973, -5.9301)]

def is_urban(row):
    lat, lon = float(row["lat"]), float(row["lon"])
    for clat, clon in CITIES:
        dx = (lon - clon) * math.cos(math.radians(clat)) * 111.32   # km
        dy = (lat - clat) * 110.54
        if math.hypot(dx, dy) <= 20:
            return True
    return False

urban = [r for r in adults if is_urban(r)]
rural = [r for r in adults if not is_urban(r)]

def mean_length(group):
    return sum(float(r["length_m"]) for r in group) / len(group)

def pct_undersized(group):
    bad = sum(1 for r in group
              if float(r["length_m"]) < 130 or float(r["width_m"]) < 80)
    return round(100 * bad / len(group), 1)

print("urban:", len(urban), "mean length", round(mean_length(urban), 1),
      "undersized", pct_undersized(urban), "%")
print("rural:", len(rural), "mean length", round(mean_length(rural), 1),
      "undersized", pct_undersized(rural), "%")

# ---------------------------------------------------------------
# QUESTION 4: NAMES (publication-grade pipeline, v2)
# Rulings encoded:
#  - "X GAA Grounds/Club/Field" = CLUB label, unless the name
#    carries a dedication marker (naomh/st/father/memorial...).
#  - Ground-bucket names get a guessed dedication category; the
#    name must declare it (no benefactor assumptions) - surnames
#    stay "person" until the review pass attributes them.
# Dedup keys strip org suffixes: "naomh barrog" == "naomh barrog gaa".
# Never merges on location alone (two clubs can share one grounds).
# ---------------------------------------------------------------

from collections import Counter
import unicodedata

def fold(s):
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")

def clean_name(name):
    n = name.lower()
    for abbr in ["g.a.a.", "g.a.a", "g.f.c.", "g.f.c", "c.l.g.", "c.l.g",
                 "g.a.c.", "g.a.c", "h.c.", "f.c.", "st."]:
        n = n.replace(abbr, abbr.replace(".", ""))
    for ch in ",()'&/-.":
        n = n.replace(ch, " ")
    return " ".join(n.split())

SUFFIX_TOKENS = {"gaa", "gfc", "gac", "clg", "club", "hc", "fc",
                 "hurling", "camogie", "handball", "gac"}
GROUND_WORDS = ["park", "pairc", "field", "stadium", "grounds", "memorial"]
FUNCTIONAL_WORDS = ["training", "astro", "all weather", "handball", "alley",
                    "ball wall", "juvenile", "clubhouse", "dressing", "gym",
                    "pitch 1", "pitch 2", "pitch 3", "u12", "u14", "3g", "tap"]
DEDICATION_MARKERS = ["naomh", "saint", "st ", "mhuire", "father", "fr ",
                      "canon", "monsignor", "memorial", "pairc ui", "pairc"]
PATRIOTS = ["pearse", "emmet", "tone", "davitt", "sarsfield", "mitchel",
            "casement", "rossa", "plunkett", "ashe", "mccracken",
            "mac diarmada", "connolly", "clarke", "markievicz"]
STOPWORDS = {"the", "of", "and", "a", "an", "na", "de", "la"}

def entity_key(name):
    words = fold(clean_name(name)).split()
    while words and words[-1] in SUFFIX_TOKENS:
        words.pop()
    return " ".join(words) if words else fold(clean_name(name))

def has_dedication(folded):
    return any(m in folded for m in DEDICATION_MARKERS)

def classify(name):
    folded = fold(clean_name(name))
    if any(w in folded for w in FUNCTIONAL_WORDS):
        return "functional"
    if folded in ("pitch", "main pitch", "gaa pitch") or folded.isdigit():
        return "functional"
    if any(w in folded for w in GROUND_WORDS):
        # your ruling: club-labelled grounds are CLUB, unless dedicated
        club_labelled = any(t in folded.split() for t in SUFFIX_TOKENS)
        if club_labelled and not has_dedication(folded):
            return "club"
        return "ground"
    return "club"

def guess_dedication(folded):
    # only what the name itself declares
    if any(w in folded for w in ["naomh", "saint", "st ", "mhuire"]):
        return "saint"
    if any(w in folded for w in ["father", "fr ", "canon", "monsignor"]):
        return "clergy"
    if any(p in folded for p in PATRIOTS):
        return "patriot"
    if "memorial" in folded:
        return "memorial"
    # a non-place capitalised word we can't attribute: person until reviewed
    tokens = [t for t in folded.split()
              if t not in STOPWORDS and t not in SUFFIX_TOKENS
              and t not in ("park", "pairc", "field", "stadium", "grounds")]
    if tokens and len(tokens) <= 2:
        return "person-unattributed"
    return "place-or-other"

# ---- load ----
irish = []
with open("gaa_out/pitches.csv") as f:
    for row in csv.DictReader(f):
        if (51.3 <= float(row["lat"]) <= 55.5
                and -11.0 <= float(row["lon"]) <= -5.3
                and row["name"]):
            irish.append(row)

overrides = {}
try:
    with open("gaa_out/names_reviewed.csv") as f:
        for r in csv.DictReader(f):
            overrides[r["key"]] = {"bucket": r["bucket"],
                                   "dedication": r.get("dedication", "")}
    print("using", len(overrides), "reviewed corrections")
except FileNotFoundError:
    pass

# ---- classify + dedup ----
clusters = {}
records = []
for r in irish:
    key = entity_key(r["name"])
    folded = fold(clean_name(r["name"]))
    if key in overrides:
        bucket = overrides[key]["bucket"]
        dedication = overrides[key]["dedication"]
    else:
        bucket = classify(r["name"])
        dedication = guess_dedication(folded) if bucket == "ground" else ""
    lat, lon = float(r["lat"]), float(r["lon"])
    primary = True
    seeds = clusters.setdefault(key, [])
    for slat, slon in seeds:
        dx = (lon - slon) * math.cos(math.radians(slat)) * 111.32
        dy = (lat - slat) * 110.54
        if math.hypot(dx, dy) <= 2.0:
            primary = False
            break
    if primary:
        seeds.append((lat, lon))
    records.append({"osm_id": r["osm_id"], "lat": lat, "lon": lon,
                    "leisure": r["leisure"], "name": r["name"], "key": key,
                    "bucket": bucket, "dedication": dedication,
                    "primary": primary})

primaries = [rec for rec in records if rec["primary"]]
print("named features:", len(records), "-> unique entities:", len(primaries))
for b in ("ground", "club", "functional"):
    print(" ", b, sum(1 for rec in primaries if rec["bucket"] == b))
print("ground dedications (guessed):")
dcounts = Counter(rec["dedication"] for rec in primaries
                  if rec["bucket"] == "ground")
for d, c in dcounts.most_common():
    print("  ", d, c)

# ---- outputs ----
with open("gaa_out/names_clean.csv", "w", newline="") as f:
    out = csv.DictWriter(f, fieldnames=list(records[0].keys()))
    out.writeheader(); out.writerows(records)

with open("gaa_out/names_review.csv", "w", newline="") as f:
    out = csv.writer(f)
    out.writerow(["key", "name", "bucket", "dedication"])
    for rec in sorted(primaries, key=lambda x: (x["bucket"], x["key"])):
        out.writerow([rec["key"], rec["name"], rec["bucket"],
                      rec["dedication"]])

def word_rows(recs, bucket):
    counts, bigrams = Counter(), Counter()
    for rec in recs:
        if rec["bucket"] != bucket:
            continue
        words = [w for w in fold(clean_name(rec["name"])).split()
                 if len(w) > 1 and w not in STOPWORDS]
        counts.update(words)
        bigrams.update(f"{a} {b}" for a, b in zip(words, words[1:]))
    return counts, bigrams

with open("gaa_out/name_words.csv", "w", newline="") as fw, \
     open("gaa_out/name_bigrams.csv", "w", newline="") as fb:
    ow, ob = csv.writer(fw), csv.writer(fb)
    ow.writerow(["bucket", "word", "count"])
    ob.writerow(["bucket", "phrase", "count"])
    for bucket in ("ground", "club"):
        counts, bigrams = word_rows(primaries, bucket)
        for word, c in counts.most_common():
            ow.writerow([bucket, word, c])
        for phrase, c in bigrams.most_common():
            if c >= 2:
                ob.writerow([bucket, phrase, c])

print("wrote names_clean / names_review / name_words / name_bigrams")

# ---------------------------------------------------------------
# QUESTION 5: IS GAA'S RURAL ORDER REAL?
# Rural GAA previously showed a stronger cardinal effect (R4) than
# rural soccer. Signal or noise? Permutation test: pool both groups,
# shuffle, resplit at the original sizes 10,000 times, and ask how
# often chance alone produces a gap as big as the real one.
# No target for the p-value - computed here for the first time.
# ---------------------------------------------------------------

import random

def r4(bearings):
    # resultant length of the 4-theta test: 0 = chaos, 1 = grid-locked
    n = len(bearings)
    s = sum(math.sin(math.radians(4 * b)) for b in bearings)
    c = sum(math.cos(math.radians(4 * b)) for b in bearings)
    return math.hypot(s, c) / n

# rural GAA bearings: signal sample minus urban
gaa_rural = [float(r["bearing_deg"]) for r in rows if not is_urban(r)]

# rural soccer bearings - note: soccer CSV has no leisure column
soccer_rural = []
with open("soccer_out/soccer_pitches.csv") as f:
    for row in csv.DictReader(f):
        if (float(row["aspect"]) >= 1.2
                and 2000 <= float(row["area_m2"]) <= 20000
                and 51.3 <= float(row["lat"]) <= 55.5
                and -11.0 <= float(row["lon"]) <= -5.3
                and not is_urban(row)):
            soccer_rural.append(float(row["bearing_deg"]))

real_gap = r4(gaa_rural) - r4(soccer_rural)
print("rural GAA n:", len(gaa_rural), "R4:", round(r4(gaa_rural), 4))
print("rural soccer n:", len(soccer_rural), "R4:", round(r4(soccer_rural), 4))
print("real gap:", round(real_gap, 4))

random.seed(1798)                     # reproducible shuffles
pool = gaa_rural + soccer_rural
n_gaa = len(gaa_rural)
hits = 0
TRIALS = 10_000
for _ in range(TRIALS):
    random.shuffle(pool)
    gap = r4(pool[:n_gaa]) - r4(pool[n_gaa:])
    if gap >= real_gap:
        hits += 1

print("permutation p-value:", hits / TRIALS)

# ---------------------------------------------------------------
# QUESTION 6: COUNTY BY COUNTY
# Which counties are ordered, which are chaos, and do the land's
# regions leave their mark? Drumlin belt (NE-SW glacial grain),
# western seaboard (Atlantic wind), and the four GAA provinces.
# Joins county_map.csv to the signal sample. Counties under MIN_N
# are reported but flagged low-n.
# Writes gaa_out/county_stats.csv for the eventual map.
# ---------------------------------------------------------------

MIN_N = 30

county_of = {}
with open("gaa_out/county_map.csv") as f:
    for r in csv.DictReader(f):
        name = "Derry" if r["county"] == "Londonderry" else r["county"]
        county_of[r["osm_id"]] = name

def r4_full(bearings):
    # R and mean axis of the 4-theta test (mean folded to 0-90)
    n = len(bearings)
    s = sum(math.sin(math.radians(4 * b)) for b in bearings)
    c = sum(math.cos(math.radians(4 * b)) for b in bearings)
    R = math.hypot(s, c) / n
    mean = (math.degrees(math.atan2(s, c)) / 4) % 90
    return R, mean

def cardinal_pct(bearings):
    near = sum(1 for b in bearings if min(b % 90, 90 - (b % 90)) <= 15)
    return round(100 * near / len(bearings), 1)

by_county = {}
for r in rows:                          # signal sample only
    county = county_of.get(r["osm_id"])
    if county:
        by_county.setdefault(county, []).append(float(r["bearing_deg"]))

stats = []
for county, bearings in by_county.items():
    R, mean = r4_full(bearings)
    stats.append({"county": county, "n": len(bearings),
                  "R4": round(R, 4), "mean_axis": round(mean, 1),
                  "cardinal_pct": cardinal_pct(bearings),
                  "low_n": len(bearings) < MIN_N})

stats.sort(key=lambda s: -s["R4"])
print("\ncounty orientation table (sorted by R4, * = low n):")
for s in stats:
    flag = "*" if s["low_n"] else " "
    print(f" {flag} {s['county']:<12} n={s['n']:<4} R4={s['R4']:<7}"
          f" mean={s['mean_axis']:<5} cardinal%={s['cardinal_pct']}")

# ---- regional rollups: drumlin belt, western seaboard, provinces ----
def region_line(label, county_set):
    bs = [b for c in county_set for b in by_county.get(c, [])]
    if not bs:
        print(f"{label}: no data")
        return
    R, mean = r4_full(bs)
    print(f"{label:<22} n={len(bs):<5} R4={R:.4f} "
          f"mean axis={mean:<5.1f} cardinal%={cardinal_pct(bs)}")

DRUMLIN = {"Cavan", "Monaghan", "Down", "Leitrim"}
SEABOARD = {"Kerry", "Clare", "Galway", "Mayo", "Sligo", "Donegal"}
PROVINCES = {
    "Ulster": {"Antrim", "Armagh", "Cavan", "Derry", "Donegal", "Down",
               "Fermanagh", "Monaghan", "Tyrone"},
    "Munster": {"Clare", "Cork", "Kerry", "Limerick", "Tipperary",
                "Waterford"},
    "Leinster": {"Carlow", "Dublin", "Kildare", "Kilkenny", "Laois",
                 "Longford", "Louth", "Meath", "Offaly", "Westmeath",
                 "Wexford", "Wicklow"},
    "Connacht": {"Galway", "Leitrim", "Mayo", "Roscommon", "Sligo"},
}
ALL = set(by_county)

print("\nregional rollups:")
region_line("drumlin belt", DRUMLIN)
region_line("rest of island", ALL - DRUMLIN)
region_line("western seaboard", SEABOARD)
region_line("east of the island", ALL - SEABOARD)
print()
for prov, cs in PROVINCES.items():
    region_line(prov, cs)

with open("gaa_out/county_stats.csv", "w", newline="") as f:
    out = csv.DictWriter(f, fieldnames=["county", "n", "R4", "mean_axis",
                                        "cardinal_pct", "low_n"])
    out.writeheader()
    out.writerows(sorted(stats, key=lambda s: s["county"]))
print("wrote gaa_out/county_stats.csv")

# ---------------------------------------------------------------
# WRITE analysis_summary.json
# Every finding as data, so the repo carries results, not just the
# code that could reprint them. Matches the pull scripts' pattern.
# ---------------------------------------------------------------

import time

sunset = {}
for name, decl in [("june", 23.44), ("equinox", 0.0), ("winter", -23.44)]:
    axis = sunset_azimuth(decl) % 180
    sunset[name] = {"axis_deg": round(axis, 1),
                    "within_15deg": count_near_axis(rows, axis)}
sunset["uniform_expectation"] = round(len(rows) * 30 / 180)

twin_labels = ["0-15", "15-30", "30-45", "45-60", "60-75", "75-90"]
twins = {"pairs_within_300m": len(diffs)}
for label, b in zip(twin_labels, bins):
    twins[label] = {"count": b, "pct": round(100 * b / len(diffs), 1)}

n_ad = len(adults)
sizes = {
    "adult_pitches": n_ad,
    "median_length_m": lengths[n_ad // 2],
    "median_width_m": widths[n_ad // 2],
    "pct_short_under_130m": round(100 * short / n_ad, 1),
    "pct_narrow_under_80m": round(100 * narrow / n_ad, 1),
    "pct_undersized_either": round(100 * undersized / n_ad, 1),
    "urban": {"n": len(urban), "mean_length_m": round(mean_length(urban), 1),
              "pct_undersized": pct_undersized(urban)},
    "rural": {"n": len(rural), "mean_length_m": round(mean_length(rural), 1),
              "pct_undersized": pct_undersized(rural)},
}

names_summary = {
    "named_features": len(records),
    "unique_entities": len(primaries),
    "buckets": {b: sum(1 for rec in primaries if rec["bucket"] == b)
                for b in ("ground", "club", "functional")},
    "ground_dedications_guessed": dict(dcounts),
    "note": "dedications pending human review pass (names_review.csv)",
}

permutation = {
    "rural_gaa": {"n": len(gaa_rural), "R4": round(r4(gaa_rural), 4)},
    "rural_soccer": {"n": len(soccer_rural),
                     "R4": round(r4(soccer_rural), 4)},
    "real_gap": round(real_gap, 4),
    "trials": TRIALS, "seed": 1798,
    "p_value": hits / TRIALS,
}

def region_stats(county_set):
    bs = [b for c in county_set for b in by_county.get(c, [])]
    R, mean = r4_full(bs)
    return {"n": len(bs), "R4": round(R, 4),
            "mean_axis": round(mean, 1), "cardinal_pct": cardinal_pct(bs)}

regions = {
    "drumlin_belt": region_stats(DRUMLIN),
    "rest_of_island": region_stats(ALL - DRUMLIN),
    "western_seaboard": region_stats(SEABOARD),
    "east_of_island": region_stats(ALL - SEABOARD),
    "provinces": {p: region_stats(cs) for p, cs in PROVINCES.items()},
}

summary = {
    "project": "Pitch Compass - analyse.py findings",
    "attribution": "Pitches (c) OpenStreetMap contributors, ODbL 1.0. "
                   "County boundaries: Tailte Eireann (CC-BY 4.0), "
                   "OSNI (OGL).",
    "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "signal_sample": len(rows),
    "sunset": sunset,
    "twin_pitches": twins,
    "sizes": sizes,
    "names": names_summary,
    "rural_gap_permutation": permutation,
    "counties": stats,
    "regions": regions,
}

with open("gaa_out/analysis_summary.json", "w") as f:
    json.dump(summary, f, indent=2)
print("\nwrote gaa_out/analysis_summary.json")