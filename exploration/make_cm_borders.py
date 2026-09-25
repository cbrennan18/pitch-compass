#!/usr/bin/env python3
"""
Pitch Compass -- docs/data/cm_borders.json (Stage 3A-ii, item C).
Cavan + Monaghan county polygons only, for the Cavan-Monaghan scene's
higher-weight border emphasis. outlines.json's border paths are NOT
individually named (verified: 217 raw stitched segments, no county
field), so a bbox-based emphasis would wrongly catch neighbouring
counties (Leitrim, Fermanagh, Meath, Tyrone all border this pair). This
script instead reads the SAME boundary source assign_counties.py uses
and extracts just these two counties' own rings, simplified.

Method: reuses make_site_data.py's dp_simplify() verbatim. Each county's
polygon (Polygon or MultiPolygon) rings are simplified independently and
kept as separate paths -- no edge-cancellation/stitching needed since
we're not deriving a shared coastline, just two named county outlines.

Licence: Tailte Eireann, Creative Commons Attribution 4.0 (same source
and attribution as assign_counties.py / the county book).

Stdlib only. Writes docs/data/cm_borders.json.
"""
import json, math, glob, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "docs", "data", "cm_borders.json")

LAT0 = 53.4
KX = math.cos(math.radians(LAT0))
TOL_M = 60   # simplification tolerance; these are backdrop lines, not measurement
TOL = TOL_M / 111320

NAME_KEYS = ["COUNTY", "ENGLISH", "COUNTY_NAME", "CountyName", "NAME",
             "County_Name", "COUNTYNAME", "name"]
WANTED = {"Cavan", "Monaghan"}


def county_name(props):
    for k in NAME_KEYS:
        if k in props and props[k]:
            return str(props[k]).title().replace("County ", "").strip()
    return None


def rings_of(geom):
    if geom["type"] == "Polygon":
        for ring in geom["coordinates"]:
            yield ring
    elif geom["type"] == "MultiPolygon":
        for poly in geom["coordinates"]:
            for ring in poly:
                yield ring


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


counties = {}
for path in sorted(glob.glob(os.path.join(HERE, "boundaries", "*.geojson"))):
    gj = json.load(open(path))
    for feat in gj["features"]:
        name = county_name(feat["properties"])
        if name not in WANTED:
            continue
        paths = []
        for ring in rings_of(feat["geometry"]):
            simp = dp_simplify(ring, TOL)
            paths.append([[round(lon, 4), round(lat, 4)] for lon, lat in simp])
        counties[name] = paths

missing = WANTED - set(counties.keys())
if missing:
    raise SystemExit(f"missing counties in boundary files: {missing}")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w") as f:
    json.dump({
        "note": "Cavan and Monaghan county polygons only, Douglas-Peucker simplified "
                f"({TOL_M}m tolerance) -- for the Cavan-Monaghan scene's higher-weight "
                "border emphasis; outlines.json's borders are not individually named.",
        "attribution": "County boundaries: Tailte Eireann, Creative Commons Attribution 4.0",
        "counties": counties,
    }, f, separators=(",", ":"))

size = os.path.getsize(OUT)
for name, paths in counties.items():
    npts = sum(len(p) for p in paths)
    print(f"{name}: {len(paths)} ring(s), {npts} points")
print(f"cm_borders.json: {size} bytes ({size/1024:.1f} KB)")
