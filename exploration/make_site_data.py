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
#   cast.json          the 2,707 signal pitches with shape, name, county (n==2707)
#   stadiums.json      the 29 county grounds, min-area-rect orientation
#   soccer_bearings.json  the 2,458 soccer guest-cast bearings
#   rose.json          48-bin mirrored axial histograms, GAA + soccer
#   county_stats.json  county_stats.csv verbatim, typed
#   coast.json         island outline, edge-cancelled from the boundaries
#   outlines.json      coast + county borders + per-county bbox
#   charts.json        the numbers the four in-flow charts render
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

cast = []             # [lat, lon, bearing, L, W, name, county, urban]  (Stage 2)
lengths = []          # metre lengths, for the size histogram in charts.json
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
        L = round(float(row["length_m"]))
        W = round(float(row["width_m"]))
        name = row["name"].strip()
        county = county_of.get(row["osm_id"], "")
        urban = 1 if is_urban(float(row["lat"]), float(row["lon"])) else 0
        cast.append([lat, lon, bearing, L, W, name, county, urban])
        lengths.append(float(row["length_m"]))
        gaa_bearings.append(float(row["bearing_deg"]))
        (urban_bearings if urban else rural_bearings).append(float(row["bearing_deg"]))

N = len(cast)
assert N == 2707, f"signal sample is {N}, expected 2707 — check the filter/inputs"

# ---- cast.json — the Stage 2 cast: 2,707 signal pitches with full shape,
#      name and county. Compact arrays + fields header. The four quiz
#      protagonists are pre-located by index so s1's swap is instant. ----
PROTAGONISTS = {  # confirmed author picks (character-first, full-regulation).
    # (name, target bearing) — target disambiguates duplicate club names, e.g.
    # two "St. Faithleach's" in Roscommon (2.9° and 47.5°): we want the wind one.
    "sun":   ("PJ Duke Memorial Park", 41.8),        # Cavan — square to the June sunset line
    "wind":  ("St. Faithleach's", 45.0),             # Roscommon — SW prevailing axis
    "north": ("Pearse Park", 0.0),                   # Longford — true north-south
    "none":  ("Ray Prendergast Memorial Park", 151.8),  # Mayo — doesn't matter
}


def axis_diff(a, b):
    d = abs(a - b) % 180.0
    return min(d, 180.0 - d)


protagonists = {}
for key, (want, target) in PROTAGONISTS.items():
    matches = [(axis_diff(rec[2], target), i) for i, rec in enumerate(cast)
               if rec[5] == want]
    assert matches, f"protagonist '{want}' ({key}) not found in cast"
    protagonists[key] = min(matches)[1]   # closest bearing to the target

with open(os.path.join(OUT, "cast.json"), "w") as f:
    json.dump({
        "fields": ["lat", "lon", "bearing", "L", "W", "name", "county", "urban"],
        "note": "bearing in degrees [0,180); L,W in metres; urban=1 within "
                "20km of Dublin/Cork/Galway/Limerick/Belfast; "
                "county joined from OSM id (Londonderry->Derry)",
        "n": N,
        "protagonists": protagonists,
        "data": cast,
    }, f, separators=(",", ":"))

# ===============================================================
# stadiums.json — the 29 county grounds, regenerated from the frozen
# Overpass pull. leisure=stadium ways/relations, min-area-rectangle
# orientation (verbatim rotating-calipers from explore_gaa.py), kept
# where aspect >= 1.1 and inside the island box. Reproduces the list the
# prototype hard-codes. Fields: [lat, lon, bearing, L, W, name].
# ===============================================================

def _project(points):
    lat0 = sum(p[0] for p in points) / len(points)
    lon0 = sum(p[1] for p in points) / len(points)
    k = math.cos(math.radians(lat0))
    return ([((lon - lon0) * k * 111320.0, (lat - lat0) * 110540.0)
             for lat, lon in points], (lat0, lon0))


def _convex_hull(pts):
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])
    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _min_area_rect(pts_xy):
    hull = _convex_hull(pts_xy)
    if len(hull) < 3:
        return None
    best = None
    n = len(hull)
    for i in range(n):
        x1, y1 = hull[i]; x2, y2 = hull[(i + 1) % n]
        ex, ey = x2 - x1, y2 - y1
        elen = math.hypot(ex, ey)
        if elen == 0:
            continue
        ux, uy = ex / elen, ey / elen
        vx, vy = -uy, ux
        us = [px * ux + py * uy for px, py in hull]
        vs = [px * vx + py * vy for px, py in hull]
        du, dv = max(us) - min(us), max(vs) - min(vs)
        area = du * dv
        if best is None or area < best[0]:
            if du >= dv:
                ax, ay, length, width = ux, uy, du, dv
            else:
                ax, ay, length, width = vx, vy, dv, du
            bearing = math.degrees(math.atan2(ax, ay)) % 180.0
            best = (area, bearing, length, width)
    if best is None:
        return None
    return best[1], best[2], best[3]


def _feature_points(el):
    if el["type"] == "way" and "geometry" in el:
        return [(g["lat"], g["lon"]) for g in el["geometry"]]
    if el["type"] == "relation" and "members" in el:
        pts = []
        for m in el["members"]:
            if m.get("role") in ("outer", "") and "geometry" in m:
                pts += [(g["lat"], g["lon"]) for g in m["geometry"]]
        return pts
    return []


raw = json.load(open(ipath("gaa_out", "raw_overpass.json")))
raw_els = raw["elements"] if isinstance(raw, dict) else raw
stadiums = []
for el in raw_els:
    if el.get("tags", {}).get("leisure") != "stadium":
        continue
    if el["type"] == "node":
        continue
    pts = _feature_points(el)
    if len(pts) < 3:
        continue
    xy, (lat0, lon0) = _project(pts)
    rect = _min_area_rect(xy)
    if rect is None:
        continue
    bearing, L, W = rect
    if W <= 0 or L / W < 1.1:
        continue
    if not (LAT_MIN <= lat0 <= LAT_MAX and LON_MIN <= lon0 <= LON_MAX):
        continue
    stadiums.append([round(lat0, 4), round(lon0, 4), round(bearing, 1),
                     round(L), round(W), el["tags"].get("name", "")])

assert len(stadiums) == 29, f"stadiums is {len(stadiums)}, expected 29"

with open(os.path.join(OUT, "stadiums.json"), "w") as f:
    json.dump({
        "fields": ["lat", "lon", "bearing", "L", "W", "name"],
        "note": "leisure=stadium, min-area-rect orientation, aspect>=1.1, "
                "island box; the 29 county grounds",
        "n": len(stadiums),
        "data": stadiums,
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

# ---- soccer_bearings.json — the guest cast: bearings only (1 dp) ----
assert len(soccer_bearings) == 2458, \
    f"soccer signal is {len(soccer_bearings)}, expected 2458"
with open(os.path.join(OUT, "soccer_bearings.json"), "w") as f:
    json.dump({
        "note": "soccer signal sample, bearings in degrees [0,180), 1 dp; "
                "the guest rose needs nothing else",
        "n": len(soccer_bearings),
        "bearings": [round(b, 1) for b in soccer_bearings],
    }, f, separators=(",", ":"))

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


def file_segments(path):
    """Return (exterior, internal): edges appearing once are the file's
    outer boundary (coast + land border); edges appearing twice are the
    internal county-vs-county borders within that file."""
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
    exterior = [example[k] for k, v in counts.items() if v == 1]
    internal = [example[k] for k, v in counts.items() if v == 2]
    return exterior, internal


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


from collections import defaultdict

LAT0 = 53.4
KX = math.cos(math.radians(LAT0))          # lon->x scaling for planar work


def chain_extent_km(ch):
    xs = [p[0] * KX for p in ch]
    ys = [p[1] for p in ch]
    return math.hypot((max(xs) - min(xs)) * 111.32, (max(ys) - min(ys)) * 110.54)


def bearing_to(p, q):
    return math.atan2((q[0] - p[0]) * math.cos(math.radians(53.4)),
                      (q[1] - p[1]))


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


def build_paths(segments, tol, drop_min_km=8.0, bridge_km=6.0):
    """Stitch undirected snapped segments into polylines (straightest
    continuation at junctions), drop slivers, optionally bridge small end
    gaps, Douglas-Peucker simplify, quantise to 3 dp. Local state only."""
    adj = defaultdict(list)
    for a, b in segments:
        adj[a].append(b)
        adj[b].append(a)
    used = set()

    def take_edge(a, b):
        used.add(frozenset((a, b)))

    def edge_used(a, b):
        return frozenset((a, b)) in used

    def walk_from(prev, cur):
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
    for s in [p for p, ns in adj.items() if len(ns) == 1]:
        for n in list(adj[s]):
            if not edge_used(s, n):
                take_edge(s, n)
                chains.append(walk_from(s, n))
    for a, b in segments:
        if not edge_used(a, b):
            take_edge(a, b)
            chains.append(walk_from(a, b))

    chains = [c for c in chains if len(c) >= 4 and chain_extent_km(c) >= drop_min_km]

    if bridge_km > 0:
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
                            if d <= bridge_km and (best is None or d < best[0]):
                                best = (d, i, j, ei, ej)
            if best:
                _, i, j, ei, ej = best
                ci = chains[i][::-1] if ei == 0 else chains[i]
                cj = chains[j] if ej == 0 else chains[j][::-1]
                merged = ci + cj
                chains = [c for k, c in enumerate(chains) if k not in (i, j)]
                chains.append(merged)
                changed = True

    paths = []
    for ch in sorted(chains, key=chain_extent_km, reverse=True):
        simp = dp_simplify(ch, tol)
        paths.append([[round(lon, 3), round(lat, 3)] for lon, lat in simp])
    return paths


def paths_bbox(paths):
    all_pts = [p for path in paths for p in path]
    return [round(min(p[0] for p in all_pts), 3), round(min(p[1] for p in all_pts), 3),
            round(max(p[0] for p in all_pts), 3), round(max(p[1] for p in all_pts), 3)]


bfiles = sorted(glob.glob(ipath("boundaries", "*.geojson")) +
                glob.glob(ipath("boundaries", "*.json")))
if len(bfiles) != 2:
    raise SystemExit(f"expected exactly 2 boundary files, found {len(bfiles)}")

fseg = [file_segments(p) for p in bfiles]           # [(exterior, internal), ...]
exts = [e for e, _ in fseg]
mids = [[seg_mid(s) for s in e] for e in exts]

# ---- coast: exterior edges, ROI/NI land border scrubbed off ----
SCRUB_CELL = 0.05
coast_segments = []
border_segments = []            # internal county borders + the ROI/NI land border
for i in range(2):
    other = build_point_buckets(mids[1 - i], SCRUB_CELL)
    for s, m in zip(exts[i], mids[i]):
        if near_any_point(m[0], m[1], other, SCRUB_CELL, 3.0):
            border_segments.append(s)     # near the other file -> land border
        else:
            coast_segments.append(s)      # true coastline
    border_segments.extend(fseg[i][1])    # this file's internal county borders

# dedup border segments (the ROI/NI border is contributed by both files)
_seen = set()
_border_dedup = []
for a, b in border_segments:
    k = frozenset((a, b))
    if k not in _seen:
        _seen.add(k)
        _border_dedup.append((a, b))
border_segments = _border_dedup

TOL_COAST = 0.0035    # ~390 m; coast stays finer (measurement-grade)
TOL_BORDER = 0.012    # ~1.3 km; borders coarsen aggressively (backdrop only)

paths = build_paths(coast_segments, TOL_COAST, drop_min_km=8.0, bridge_km=6.0)
border_paths = build_paths(border_segments, TOL_BORDER, drop_min_km=1.0, bridge_km=0.0)

# ---- per-county bbox (from the polygons), for the explorer zoom ----
def norm_county(props):
    raw_name = props.get("COUNTY") or props.get("CountyName") or props.get("ENGLISH") or ""
    name = raw_name.title()
    return "Derry" if name == "Londonderry" else name


county_bbox = {}
for path in bfiles:
    with open(path) as f:
        gj = json.load(f)
    for feat in gj["features"]:
        name = norm_county(feat["properties"])
        if not name:
            continue
        lons, lats = [], []
        for ring in rings_of(feat["geometry"]):
            for lon, lat in ring:
                lons.append(lon); lats.append(lat)
        bb = [round(min(lons), 3), round(min(lats), 3),
              round(max(lons), 3), round(max(lats), 3)]
        if name in county_bbox:   # merge if a county spans multiple features
            o = county_bbox[name]
            bb = [min(bb[0], o[0]), min(bb[1], o[1]), max(bb[2], o[2]), max(bb[3], o[3])]
        county_bbox[name] = bb

assert len(county_bbox) == 32, f"county bboxes: {len(county_bbox)}, expected 32"

# ---- coast.json (island only; unchanged shape, kept for continuity) ----
with open(os.path.join(OUT, "coast.json"), "w") as f:
    json.dump({
        "note": "island coastline, edge-cancelled from the county boundaries "
                "(Tailte Eireann + OSNI); simplified for display",
        "ref_lat": LAT0,
        "bbox": paths_bbox(paths),
        "paths": paths,
    }, f, separators=(",", ":"))

# ---- outlines.json (Stage 2: coast + county borders + per-county bbox) ----
with open(os.path.join(OUT, "outlines.json"), "w") as f:
    json.dump({
        "note": "island coast (fine) + internal county borders (coarse backdrop), "
                "edge-cancelled from Tailte Eireann + OSNI; per-county bbox for zoom",
        "ref_lat": LAT0,
        "bbox": paths_bbox(paths),
        "coast": paths,
        "borders": border_paths,
        "counties": county_bbox,
    }, f, separators=(",", ":"))

coast_points = sum(len(p) for p in paths)
border_points = sum(len(p) for p in border_paths)

# ===============================================================
# charts.json — the numbers the four in-flow charts (f1-f4) render.
# All values read from frozen outputs; nothing invented here.
#   f1 sunset deficit · f2 twin-pair angles · f3 sizes · f4 names
# ===============================================================

_asum = json.load(open(ipath("gaa_out", "analysis_summary.json")))

# f3: length histogram over ADULT pitches (length >= 100 m) — the SAME
# population the 18.7%/39.1% stats are computed on (analyse.py:130), so the
# chart's <130 m mass reads consistently with its printed percentages.
HIST_LO, HIST_HI, HIST_W = 100, 180, 10
adult_lengths = [Lm for Lm in lengths if Lm >= 100.0]
nbin = (HIST_HI - HIST_LO) // HIST_W + 1       # bins + one overflow (>=180)
size_hist = [0] * nbin
for Lm in adult_lengths:
    if Lm >= HIST_HI:
        size_hist[-1] += 1
    else:
        size_hist[int((Lm - HIST_LO) // HIST_W)] += 1
size_edges = ["%d" % (HIST_LO + k * HIST_W)
              for k in range((HIST_HI - HIST_LO) // HIST_W)] + ["%d+" % HIST_HI]

# f4: epithet leaderboard — DEDUPED club-word counts. name_words.csv is built
# from analyse.py's unique entities (primaries; 1333 named -> 1288 deduped), so
# these ARE the deduped machine figures. FINDINGS quotes Rovers 10 / Emmets 8;
# the current pipeline yields 11 / 9 (verified by re-running analyse.py's names
# section in isolation) -> FINDINGS needs a one-line erratum on a future touch.
EPITHETS = ["gaels", "og", "rovers", "emmets", "shamrocks", "harps"]
word_count = {}
with open(ipath("gaa_out", "name_words.csv")) as f:
    for r in csv.DictReader(f):
        if r["bucket"] == "club":
            word_count[r["word"]] = int(r["count"])
epithet_leaderboard = [[w, word_count.get(w, 0)] for w in EPITHETS]

charts = {
    "sunset": {
        "june": _asum["sunset"]["june"]["within_15deg"],
        "equinox": _asum["sunset"]["equinox"]["within_15deg"],
        "winter": _asum["sunset"]["winter"]["within_15deg"],
        "uniform": _asum["sunset"]["uniform_expectation"],
        "june_axis": _asum["sunset"]["june"]["axis_deg"],
        "note": "counts within 15 deg of each season's sunset axis",
    },
    "twins": {
        "bins": ["0-15", "15-30", "30-45", "45-60", "60-75", "75-90"],
        "counts": [_asum["twin_pitches"][b]["count"]
                   for b in ("0-15", "15-30", "30-45", "45-60", "60-75", "75-90")],
        "pct": [_asum["twin_pitches"][b]["pct"]
                for b in ("0-15", "15-30", "30-45", "45-60", "60-75", "75-90")],
        "pairs_within_300m": _asum["twin_pitches"]["pairs_within_300m"],
    },
    "sizes": {
        "population": "adult pitches, length >= 100 m",
        "adult_n": len(adult_lengths),
        "edges": size_edges,
        "hist": size_hist,
        "line_130m": 130,
        "pct_short_under_130m": _asum["sizes"]["pct_short_under_130m"],
        "pct_narrow_under_80m": _asum["sizes"]["pct_narrow_under_80m"],
        "pct_undersized_either": _asum["sizes"]["pct_undersized_either"],
        "median_length_m": _asum["sizes"]["median_length_m"],
        "median_width_m": _asum["sizes"]["median_width_m"],
    },
    "names": {
        "dedications": _asum["names"]["ground_dedications_guessed"],
        "epithets": epithet_leaderboard,
        "epithets_note": "deduped unique-entity club-word counts; FINDINGS' "
                         "Rovers 10/Emmets 8 is a drafting erratum (pipeline: 11/9); "
                         "dedications still pending the human review pass",
    },
}
with open(os.path.join(OUT, "charts.json"), "w") as f:
    json.dump(charts, f, separators=(",", ":"))

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
print(f"stadiums (county grounds):  {len(stadiums)}              (expected 29)")
print(f"county bboxes:              {len(county_bbox)}              (expected 32)")
print(f"canonical counts 2707/29/2458/32: "
      f"{'OK' if (N, len(stadiums), len(soccer_bearings), len(county_bbox)) == (2707, 29, 2458, 32) else 'MISMATCH'}")
print(f"urban / rural split:        {len(urban_bearings)} / {len(rural_bearings)}"
      f"       (FINDINGS: 540 / 2167)")
prot = ", ".join(f"{k}={cast[v][5]}" for k, v in protagonists.items())
print(f"protagonists:               {prot}")
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
ep = ", ".join(f"{w} {c}" for w, c in epithet_leaderboard)
print(f"names epithets (deduped, chart uses these): {ep}")
print("   NB FINDINGS says Rovers 10 / Emmets 8 — drafting erratum; pipeline: 11 / 9")
print("-" * 60)
print("FILE SIZES  (budget: cast <170KB, outlines <120KB target / 150KB cap)")
print(f"cast.json:           {N} records,      {size('cast.json'):>7} bytes"
      f"   ({size('cast.json')/1024:.1f} KB, budget 170)")
print(f"stadiums.json:       {len(stadiums)} grounds,       {size('stadiums.json'):>7} bytes")
print(f"soccer_bearings.json:{len(soccer_bearings)} bearings,   {size('soccer_bearings.json'):>7} bytes")
print(f"rose.json:           GAA {len(gaa_bearings)} + soccer {len(soccer_bearings)},"
      f" {size('rose.json'):>7} bytes")
print(f"county_stats.json:   {len(counties)} counties,     {size('county_stats.json'):>7} bytes")
print(f"coast.json:          {len(paths)} paths, {coast_points} pts,   {size('coast.json'):>7} bytes")
print(f"outlines.json:       coast {len(paths)}p/{coast_points}pt + borders "
      f"{len(border_paths)}p/{border_points}pt + 32 bbox, {size('outlines.json'):>7} bytes"
      f"   ({size('outlines.json')/1024:.1f} KB, budget 120 / cap 150)")
print(f"charts.json:         4 series,        {size('charts.json'):>7} bytes")
print(f"meta.json:           {size('meta.json'):>7} bytes")
print("=" * 60)
print(f"wrote {OUT}/")
