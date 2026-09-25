#!/usr/bin/env python3
"""
Pitch Compass -- docs/data/dublin_streets.json (Stage 3A, item 3).
Street layer for the tightened Dublin close-up: OSM highway ways
(primary/secondary/tertiary/residential/unclassified) inside a ~6 km box
centred on Croke Park/Drumcondra, simplified and quantised.

Query pulled live: 2026-09-25 (pin this date whenever the pull is redone --
Overpass is not a frozen local file the way exploration/gaa_out/ is).

Bbox chosen over an 8 km alternative after a live comparison (see the
Stage 3A build report): 6 km keeps 86% of in-box pitches at >=6px true-
shape length at 390px width (only 14% need the symbolic fallback) vs 31%
at 8 km (69% would need it, defeating the point of tightening the zoom),
and 8 km's street file can't get under 150 KB without materially coarser
simplification (207 KB even at 30 m tolerance) -- both push toward 6 km,
not just the size budget alone.

Method: reuses make_site_data.py's dp_simplify() verbatim (stdlib,
already proven on the coastline/borders). Tolerance and min-length were
tuned against a real pull, not guessed -- see the build report for the
comparison table.

Licence: OpenStreetMap contributors, ODbL 1.0 -- same credit as
gaa_out/pitches.csv.

Stdlib only. Writes docs/data/dublin_streets.json.
"""
import json, math, os, sys, time, urllib.request, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "docs", "data", "dublin_streets.json")

QUERY_DATE = "2026-09-25"   # pin: update this whenever the pull is redone
LAT_MIN, LAT_MAX, LON_MIN, LON_MAX = 53.3429, 53.3971, -6.2852, -6.1948   # 6 km box
LAT0 = 53.4
KX = math.cos(math.radians(LAT0))

TOL_M = 15       # Douglas-Peucker tolerance
MIN_LEN_M = 20    # drop ways shorter than this (post length, pre-simplify)
DP = 4            # decimal places (~11 m precision)

MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
UA = "pitch-compass-dublin-streets/0.1 (personal research)"
HIGHWAY_RE = "^(primary|secondary|tertiary|residential|unclassified)$"
QUERY = (f'[out:json][timeout:60];'
         f'way["highway"~"{HIGHWAY_RE}"]'
         f'({LAT_MIN},{LON_MIN},{LAT_MAX},{LON_MAX});out geom;')


def overpass(query):
    data = urllib.parse.urlencode({"data": query}).encode()
    last_err = None
    for url in MIRRORS:
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=90) as r:
                    return json.load(r)
            except Exception as e:
                last_err = e
                wait = 15 * (attempt + 1)
                print(f"  {url} failed ({e}); retry in {wait}s", file=sys.stderr)
                time.sleep(wait)
    raise SystemExit(f"All mirrors failed: {last_err}")


def dist_m(lon1, lat1, lon2, lat2):
    dx = (lon2 - lon1) * KX * 111320
    dy = (lat2 - lat1) * 110540
    return math.hypot(dx, dy)


def dp_simplify(pts, tol):
    """Verbatim from make_site_data.py -- pts are [lon,lat], tol in
    KX-scaled local-projection units (not metres directly)."""
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


print(f"pulling OSM highway ways in the Dublin 6km box (query date {QUERY_DATE})...")
raw = overpass(QUERY)
els = raw["elements"]
print(f"raw ways: {len(els)}")

tol_local = TOL_M / 111320
paths = []
for e in els:
    geom = e.get("geometry")
    if not geom or len(geom) < 2:
        continue
    pts = [(g["lon"], g["lat"]) for g in geom]
    wlen = sum(dist_m(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
               for i in range(len(pts) - 1))
    if wlen < MIN_LEN_M:
        continue
    simp = dp_simplify(pts, tol_local)
    paths.append([[round(lon, DP), round(lat, DP)] for lon, lat in simp])

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w") as f:
    json.dump({
        "note": "OSM highway ways (primary/secondary/tertiary/residential/unclassified) "
                "in a ~6km box around Croke Park/Drumcondra, Douglas-Peucker simplified "
                f"({TOL_M}m tolerance, ways under {MIN_LEN_M}m dropped, {DP}dp precision)",
        "bbox": [LAT_MIN, LAT_MAX, LON_MIN, LON_MAX],
        "query_date": QUERY_DATE,
        "attribution": "Data (c) OpenStreetMap contributors, ODbL 1.0 -- openstreetmap.org/copyright",
        "n_ways": len(paths),
        "data": paths,
    }, f, separators=(",", ":"))

size = os.path.getsize(OUT)
print(f"ways kept after {MIN_LEN_M}m drop + simplify: {len(paths)}")
print(f"dublin_streets.json: {size} bytes ({size/1024:.1f} KB)")
