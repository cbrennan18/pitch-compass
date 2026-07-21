# make_site_data.py — precompute LEAN site JSONs for Pitch Compass.
# Stdlib only. No network. Reads the FROZEN exploration outputs and the
# county boundary GeoJSONs; writes small JSONs to docs/data/. Nothing in
# gaa_out/ or soccer_out/ is touched or rewritten.
#
# Location-independent: paths resolve relative to this file, so it runs
# correctly from the repo root (python3 exploration/make_site_data.py) or
# from inside exploration/.
#
# Inputs (frozen):
#   gaa_out/pitches.csv            GAA signal sample source (explore_gaa.py)
#   soccer_out/soccer_pitches.csv  soccer control (soccer_control.py)
#   gaa_out/county_map.csv         osm_id -> county (assign_counties.py)
#   gaa_out/county_stats.csv       per-county orientation (analyse.py)
#   gaa_out/analysis_summary.json  frozen findings (analyse.py)
#   gaa_out/extra_summary.json     frozen final-round findings (analyse_extra.py)
#   boundaries/*.geojson           county polygons (Tailte Eireann + OSNI)
#
# Outputs (written to docs/data/):
#   pitches.json       one record per signal pitch (n == 2707)
#   rose.json          48-bin mirrored axial histograms, GAA + soccer
#   county_stats.json  county_stats.csv verbatim, typed
#   coast.json         island outline, edge-cancelled from the boundaries
#   meta.json          headline numbers the prose will cite
#
# The signal filter, urban rule and coastline edge-cancellation below are
# reproduced verbatim from analyse.py / analyse_extra.py — the frozen
# definitions everything downstream stands on.
#
# Pitches (c) OpenStreetMap contributors, ODbL 1.0. County boundaries:
# Tailte Eireann (CC-BY 4.0), OSNI (OGL).

import csv
import glob
import json
import math
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "docs", "data")


def ipath(*parts):
    return os.path.join(HERE, *parts)


os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------
# THE SIGNAL FILTER  (verbatim from analyse.py:33)
# ---------------------------------------------------------------

LAT_MIN, LAT_MAX = 51.3, 55.5
LON_MIN, LON_MAX = -11.0, -5.3


def is_signal_gaa(row):
    if row["leisure"] != "pitch":
        return False
    if float(row["aspect"]) < 1.2:
        return False
    if not (2000 <= float(row["area_m2"]) <= 20000):
        return False
    if not (LAT_MIN <= float(row["lat"]) <= LAT_MAX):
        return False
    if not (LON_MIN <= float(row["lon"]) <= LON_MAX):
        return False
    return True


def is_signal_soccer(row):
    # soccer CSV has no leisure column (pitch-only pull).
    # NB: this reads the CSV's ROUNDED area_m2/aspect and yields 2458, whereas
    # soccer_control.py's pull-time count (2455) filtered on unrounded geometry;
    # three pitches sit exactly on the 2000 m2 / 1.20 aspect boundaries and round
    # across it. The CSV is the published dataset, so 2458 is the reproducible
    # number and matches make_rose.py. (GAA matches to the pitch: analyse.py also
    # reads the rounded CSV.) FINDINGS.md is frozen and not touched.
    if float(row["aspect"]) < 1.2:
        return False
    if not (2000 <= float(row["area_m2"]) <= 20000):
        return False
    if not (LAT_MIN <= float(row["lat"]) <= LAT_MAX):
        return False
    if not (LON_MIN <= float(row["lon"]) <= LON_MAX):
        return False
    return True


# urban = within 20 km of the five big cities  (verbatim from analyse.py:165)
CITIES = [(53.3498, -6.2603), (51.8985, -8.4756), (53.2707, -9.0568),
          (52.6638, -8.6267), (54.5973, -5.9301)]


def is_urban(lat, lon):
    for clat, clon in CITIES:
        dx = (lon - clon) * math.cos(math.radians(clat)) * 111.32  # km
        dy = (lat - clat) * 110.54
        if math.hypot(dx, dy) <= 20:
            return True
    return False


# ---------------------------------------------------------------
# AXIAL STATS  (4-theta / 2-theta resultant; verbatim math)
# ---------------------------------------------------------------

def axial_R(bearings, fold):
    n = len(bearings)
    s = sum(math.sin(math.radians(fold * b)) for b in bearings)
    c = sum(math.cos(math.radians(fold * b)) for b in bearings)
    R = math.hypot(s, c) / n
    mean = (math.degrees(math.atan2(s, c)) / fold) % (360.0 / fold)
    return R, mean


def cardinal_pct(bearings):
    near = sum(1 for b in bearings if min(b % 90, 90 - (b % 90)) <= 15)
    return round(100 * near / len(bearings), 1)


# ===============================================================
# LOAD SIGNAL SAMPLE + COUNTY JOIN
# ===============================================================

county_of = {}
with open(ipath("gaa_out", "county_map.csv")) as f:
    for r in csv.DictReader(f):
        name = "Derry" if r["county"] == "Londonderry" else r["county"]
        county_of[r["osm_id"]] = name

pitches = []          # [lat, lon, bearing, county, urban]
gaa_bearings = []
urban_bearings = []
rural_bearings = []
with open(ipath("gaa_out", "pitches.csv")) as f:
    for row in csv.DictReader(f):
        if not is_signal_gaa(row):
            continue
        lat = round(float(row["lat"]), 4)
        lon = round(float(row["lon"]), 4)
        bearing = round(float(row["bearing_deg"]), 1)
        county = county_of.get(row["osm_id"], "")
        urban = 1 if is_urban(float(row["lat"]), float(row["lon"])) else 0
        pitches.append([lat, lon, bearing, county, urban])
        gaa_bearings.append(float(row["bearing_deg"]))
        (urban_bearings if urban else rural_bearings).append(float(row["bearing_deg"]))

N = len(pitches)
assert N == 2707, f"signal sample is {N}, expected 2707 — check the filter/inputs"

# ---- pitches.json (array-of-arrays with a fields header) ----
with open(os.path.join(OUT, "pitches.json"), "w") as f:
    json.dump({
        "fields": ["lat", "lon", "bearing", "county", "urban"],
        "note": "bearing in degrees [0,180); urban=1 within 20km of "
                "Dublin/Cork/Galway/Limerick/Belfast",
        "n": N,
        "data": pitches,
    }, f, separators=(",", ":"))

# ===============================================================
# rose.json — 48-bin mirrored axial histograms (bin counts only)
# 48 bins of 7.5 deg over [0,360), N-zero clockwise, mirrored: each
# bearing b counts at b and b+180 (matches make_rose.py's axial rose).
# ===============================================================

def mirrored_rose(bearings, nbins=48):
    width = 360.0 / nbins
    hist = [0] * nbins
    for b in bearings:
        for a in (b % 360.0, (b + 180.0) % 360.0):
            hist[min(int(a // width), nbins - 1)] += 1
    return hist


soccer_bearings = []
with open(ipath("soccer_out", "soccer_pitches.csv")) as f:
    for row in csv.DictReader(f):
        if is_signal_soccer(row):
            soccer_bearings.append(float(row["bearing_deg"]))

with open(os.path.join(OUT, "rose.json"), "w") as f:
    json.dump({
        "bins": 48,
        "bin_width_deg": 7.5,
        "zero": "north",
        "direction": "clockwise",
        "mirrored": True,
        "gaa": {"n": len(gaa_bearings), "hist": mirrored_rose(gaa_bearings)},
        "soccer": {"n": len(soccer_bearings), "hist": mirrored_rose(soccer_bearings)},
    }, f, separators=(",", ":"))

# ===============================================================
# county_stats.json — county_stats.csv verbatim, typed
# ===============================================================

counties = []
with open(ipath("gaa_out", "county_stats.csv")) as f:
    for r in csv.DictReader(f):
        counties.append({
            "county": r["county"],
            "n": int(r["n"]),
            "R4": float(r["R4"]),
            "mean_axis": float(r["mean_axis"]),
            "cardinal_pct": float(r["cardinal_pct"]),
            "low_n": r["low_n"].strip().lower() == "true",
        })
with open(os.path.join(OUT, "county_stats.json"), "w") as f:
    json.dump(counties, f, separators=(",", ":"))

# ===============================================================
# coast.json — island outline, edge-cancelled from the county polygons
# Method verbatim from analyse_extra.py (HASH_PREC=3, 3km cross-file
# border scrub), then stitched into polylines, gap-bridged at the two
# sea-lough mouths, Douglas-Peucker simplified, quantised to 3 dp.
# ===============================================================

HASH_PREC = 3


def rings_of(geom):
    if geom["type"] == "Polygon":
        for ring in geom["coordinates"]:
            yield ring
    elif geom["type"] == "MultiPolygon":
        for poly in geom["coordinates"]:
            for ring in poly:
                yield ring


def exterior_segments(path):
    with open(path) as f:
        gj = json.load(f)
    counts, example = {}, {}
    for feat in gj["features"]:
        for ring in rings_of(feat["geometry"]):
            for i in range(len(ring) - 1):
                a = (round(ring[i][0], HASH_PREC), round(ring[i][1], HASH_PREC))
                b = (round(ring[i + 1][0], HASH_PREC), round(ring[i + 1][1], HASH_PREC))
                if a == b:
                    continue
                key = frozenset((a, b))
                counts[key] = counts.get(key, 0) + 1
                if key not in example:
                    example[key] = (a, b)
    return [example[k] for k, v in counts.items() if v == 1]


def seg_mid(s):
    (lon1, lat1), (lon2, lat2) = s
    return ((lon1 + lon2) / 2.0, (lat1 + lat2) / 2.0)


def km_between(lon1, lat1, lon2, lat2):
    clat = math.radians((lat1 + lat2) / 2.0)
    dx = (lon2 - lon1) * math.cos(clat) * 111.32
    dy = (lat2 - lat1) * 110.54
    return math.hypot(dx, dy)


def build_point_buckets(points, cell):
    b = {}
    for lon, lat in points:
        b.setdefault((round(lon / cell), round(lat / cell)), []).append((lon, lat))
    return b


def near_any_point(lon, lat, buckets, cell, thresh_km):
    cx, cy = round(lon / cell), round(lat / cell)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for plon, plat in buckets.get((cx + dx, cy + dy), []):
                if km_between(lon, lat, plon, plat) <= thresh_km:
                    return True
    return False


bfiles = sorted(glob.glob(ipath("boundaries", "*.geojson")) +
                glob.glob(ipath("boundaries", "*.json")))
if len(bfiles) != 2:
    raise SystemExit(f"expected exactly 2 boundary files, found {len(bfiles)}")

exts = [exterior_segments(p) for p in bfiles]
mids = [[seg_mid(s) for s in e] for e in exts]

SCRUB_CELL = 0.05
segments = []
for i in range(2):
    other = build_point_buckets(mids[1 - i], SCRUB_CELL)
    kept = [s for s, m in zip(exts[i], mids[i])
            if not near_any_point(m[0], m[1], other, SCRUB_CELL, 3.0)]
    segments.extend(kept)

# ---- stitch segments into polylines by shared (snapped) endpoints ----
from collections import defaultdict

adj = defaultdict(list)
for a, b in segments:
    adj[a].append(b)
    adj[b].append(a)

used = set()          # consumed undirected edges


def take_edge(a, b):
    used.add(frozenset((a, b)))


def edge_used(a, b):
    return frozenset((a, b)) in used


def bearing_to(p, q):
    return math.atan2((q[0] - p[0]) * math.cos(math.radians(53.4)),
                      (q[1] - p[1]))


def walk_from(prev, cur):
    # follow the coast, at junctions continuing as straight as possible
    chain = [prev, cur]
    while True:
        cands = [n for n in adj[cur] if n != prev and not edge_used(cur, n)]
        if not cands:
            cands = [n for n in adj[cur] if not edge_used(cur, n)]
        if not cands:
            break
        incoming = bearing_to(prev, cur)
        best, bturn = None, None
        for n in cands:
            turn = abs((bearing_to(cur, n) - incoming + math.pi) % (2 * math.pi) - math.pi)
            if bturn is None or turn < bturn:
                best, bturn = n, turn
        take_edge(cur, best)
        chain.append(best)
        prev, cur = cur, best
    return chain


chains = []
# start walks at genuine endpoints (degree 1), then any leftover rings
for s in [p for p, ns in adj.items() if len(ns) == 1]:
    for n in list(adj[s]):
        if not edge_used(s, n):
            take_edge(s, n)
            chains.append(walk_from(s, n))
for a, b in segments:
    if not edge_used(a, b):
        take_edge(a, b)
        chains.append(walk_from(a, b))

# ---- drop tiny chains first (keeps bridging fast: only big coasts remain) --
LAT0 = 53.4
KX = math.cos(math.radians(LAT0))          # lon->x scaling for planar work


def chain_extent_km(ch):
    xs = [p[0] * KX for p in ch]
    ys = [p[1] for p in ch]
    return math.hypot((max(xs) - min(xs)) * 111.32, (max(ys) - min(ys)) * 110.54)


chains = [c for c in chains if len(c) >= 4 and chain_extent_km(c) >= 8.0]

# ---- bridge small gaps (Lough Foyle / Carlingford) between chain ends ----
BRIDGE_KM = 6.0


def endpoints(ch):
    return ch[0], ch[-1]


changed = True
while changed and len(chains) > 1:
    changed = False
    best = None
    for i in range(len(chains)):
        for j in range(i + 1, len(chains)):
            for ei, pi in enumerate(endpoints(chains[i])):
                for ej, pj in enumerate(endpoints(chains[j])):
                    d = km_between(pi[0], pi[1], pj[0], pj[1])
                    if d <= BRIDGE_KM and (best is None or d < best[0]):
                        best = (d, i, j, ei, ej)
    if best:
        _, i, j, ei, ej = best
        ci = chains[i][::-1] if ei == 0 else chains[i]
        cj = chains[j] if ej == 0 else chains[j][::-1]
        merged = ci + cj
        chains = [c for k, c in enumerate(chains) if k not in (i, j)]
        chains.append(merged)
        changed = True

# ---- Douglas-Peucker simplify (iterative), planar scaled coords ----
def dp_simplify(pts, tol):
    if len(pts) < 3:
        return pts[:]
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        lo, hi = stack.pop()
        ax, ay = pts[lo][0] * KX, pts[lo][1]
        bx, by = pts[hi][0] * KX, pts[hi][1]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        dmax, idx = -1.0, -1
        for k in range(lo + 1, hi):
            px, py = pts[k][0] * KX, pts[k][1]
            if L2 == 0.0:
                dist = math.hypot(px - ax, py - ay)
            else:
                t = ((px - ax) * dx + (py - ay) * dy) / L2
                t = max(0.0, min(1.0, t))
                cx, cy = ax + t * dx, ay + t * dy
                dist = math.hypot(px - cx, py - cy)
            if dist > dmax:
                dmax, idx = dist, k
        if dmax > tol and idx != -1:
            keep[idx] = True
            stack.append((lo, idx))
            stack.append((idx, hi))
    return [pts[k] for k in range(len(pts)) if keep[k]]


TOL_DEG = 0.0035   # ~ 390 m; tuned to keep coast.json well under 80 KB
paths = []
for ch in sorted(chains, key=chain_extent_km, reverse=True):
    simp = dp_simplify(ch, TOL_DEG)
    paths.append([[round(lon, 3), round(lat, 3)] for lon, lat in simp])

all_pts = [p for path in paths for p in path]
minlon = min(p[0] for p in all_pts)
maxlon = max(p[0] for p in all_pts)
minlat = min(p[1] for p in all_pts)
maxlat = max(p[1] for p in all_pts)

with open(os.path.join(OUT, "coast.json"), "w") as f:
    json.dump({
        "note": "island coastline, edge-cancelled from the county boundaries "
                "(Tailte Eireann + OSNI); simplified for display",
        "ref_lat": LAT0,
        "bbox": [round(minlon, 3), round(minlat, 3),
                 round(maxlon, 3), round(maxlat, 3)],
        "paths": paths,
    }, f, separators=(",", ":"))

coast_points = sum(len(p) for p in paths)

# ===============================================================
# meta.json — the headline numbers the prose will cite.
# Values are copied from the frozen summaries where they exist; the
# island / urban / rural resultants are recomputed here from the signal
# sample (same math as analyse.py) and cross-checked against the frozen
# p-values below.
# ===============================================================

asum = json.load(open(ipath("gaa_out", "analysis_summary.json")))
esum = json.load(open(ipath("gaa_out", "extra_summary.json")))


def find_p(substr):
    for t in esum["multiple_comparisons"]["tests"]:
        if substr in t["test"]:
            return t["p"]
    return None


R2, mean2 = axial_R(gaa_bearings, 2)
R4, mean4 = axial_R(gaa_bearings, 4)
uR4, umean = axial_R(urban_bearings, 4)
rR4, rmean = axial_R(rural_bearings, 4)

mc = esum["multiple_comparisons"]
regions = asum["regions"]

meta = {
    "project": "Pitch Compass",
    "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "signal_n": N,
    "soccer_signal_n": len(soccer_bearings),
    "island": {
        "twotheta_R": round(R2, 3),
        "twotheta_p": find_p("2-theta island"),
        "fourtheta_R": round(R4, 3),
        "fourtheta_p": find_p("4-theta island"),
        "cardinal_pct": cardinal_pct(gaa_bearings),
        "cardinal_expected_pct": 33.3,
    },
    "urban": {
        "n": len(urban_bearings), "R4": round(uR4, 3),
        "mean_axis": round(umean, 1), "cardinal_pct": cardinal_pct(urban_bearings),
    },
    "rural": {
        "n": len(rural_bearings), "R4": round(rR4, 3),
        "mean_axis": round(rmean, 1), "cardinal_pct": cardinal_pct(rural_bearings),
    },
    "sunset": asum["sunset"],
    "twins": {
        "pairs_within_300m": asum["twin_pitches"]["pairs_within_300m"],
        "parallel_pct": asum["twin_pitches"]["0-15"]["pct"],
        "perpendicular_pct": asum["twin_pitches"]["75-90"]["pct"],
    },
    "sizes": asum["sizes"],
    "rural_gap_permutation": asum["rural_gap_permutation"],
    "drumlin_belt": regions["drumlin_belt"],
    "rest_of_island": regions["rest_of_island"],
    "western_seaboard": regions["western_seaboard"],
    "stadiums": {"n": 29, "R4": 0.409, "cardinal_pct": 55.2,
                 "note": "county grounds run east-west; see FINDINGS 13"},
    "multiple_comparisons": {
        "n_tests": mc["n_tests"],
        "bonferroni_alpha": round(mc["bonferroni_alpha"], 5),
        "survivors": 6,
    },
    "attribution": {
        "pitches": "Pitch data (c) OpenStreetMap contributors, ODbL 1.0 "
                   "(openstreetmap.org/copyright)",
        "boundaries": "County boundaries: Tailte Eireann (CC-BY 4.0); "
                      "Ordnance Survey of Northern Ireland (UK OGL)",
        "note": "Derived datasets shared under the source licences.",
    },
}
with open(os.path.join(OUT, "meta.json"), "w") as f:
    json.dump(meta, f, indent=1)

# ===============================================================
# VERIFICATION BLOCK — eyeball against FINDINGS.md
# ===============================================================

def size(name):
    return os.path.getsize(os.path.join(OUT, name))


print("=" * 60)
print("PITCH COMPASS — make_site_data.py verification")
print("=" * 60)
print(f"signal sample (GAA):        {N}            (FINDINGS: 2707)")
print(f"soccer signal sample:       {len(soccer_bearings)}            "
      f"(make_rose convention; FINDINGS pull-time 2455, +3 rounding-boundary)")
print(f"urban / rural split:        {len(urban_bearings)} / {len(rural_bearings)}"
      f"       (FINDINGS: 540 / 2167)")
print("-" * 60)
print(f"island 2-theta  R={round(R2,3):<6} p={find_p('2-theta island'):.3g}"
      f"   (FINDINGS: R=0.017, p=0.44)")
print(f"island 4-theta  R={round(R4,3):<6} p={find_p('4-theta island'):.3g}"
      f"  (FINDINGS: R=0.107, p=3.3e-14)")
print(f"island cardinal %:          {cardinal_pct(gaa_bearings)}"
      f"           (FINDINGS: 38.0)")
print(f"urban  R4={round(uR4,3):<6} mean={round(umean,1):<5} cardinal%={cardinal_pct(urban_bearings)}"
      f"   (FINDINGS: 0.236 / 0.1 / 46.3)")
print(f"rural  R4={round(rR4,3):<6} mean={round(rmean,1):<5} cardinal%={cardinal_pct(rural_bearings)}"
      f"   (FINDINGS: 0.096 / ~75 / 36.0)")
print("-" * 60)
sn = asum["sunset"]
print(f"sunset June/equinox/winter: {sn['june']['within_15deg']}"
      f" / {sn['equinox']['within_15deg']} / {sn['winter']['within_15deg']}"
      f"  (uniform ~{sn['uniform_expectation']}) (FINDINGS: 363/509/427)")
tw = asum["twin_pitches"]
print(f"twins: pairs={tw['pairs_within_300m']} parallel={tw['0-15']['pct']}%"
      f" perp={tw['75-90']['pct']}%   (FINDINGS: 1346 / 50.1 / 34.1)")
sz = asum["sizes"]
print(f"sizes: adult={sz['adult_pitches']} median {sz['median_length_m']}"
      f"x{sz['median_width_m']} m, {sz['pct_undersized_either']}% undersized"
      f"  (FINDINGS: 2380 / 141.2x83.3 / 39.1)")
perm = asum["rural_gap_permutation"]
print(f"rural GAA-vs-soccer gap p:  {perm['p_value']}"
      f"        (FINDINGS: 0.0549)")
db = regions["drumlin_belt"]
print(f"drumlin belt: R4={db['R4']} mean={db['mean_axis']} cardinal%={db['cardinal_pct']}"
      f"  (FINDINGS: 0.172 / 58.6 / 23.7)")
print(f"multiple comparisons: {mc['n_tests']} tests, "
      f"alpha={round(mc['bonferroni_alpha'],5)}, 6 survive")
print("-" * 60)
print(f"pitches.json:      {N} records, {size('pitches.json'):>7} bytes")
print(f"rose.json:         GAA {len(gaa_bearings)} + soccer {len(soccer_bearings)},"
      f" {size('rose.json'):>7} bytes")
print(f"county_stats.json: {len(counties)} counties, {size('county_stats.json'):>7} bytes")
print(f"coast.json:        {len(paths)} paths, {coast_points} points,"
      f" {size('coast.json'):>7} bytes")
print(f"meta.json:         {size('meta.json'):>7} bytes")
print("=" * 60)
print(f"wrote {OUT}/")
