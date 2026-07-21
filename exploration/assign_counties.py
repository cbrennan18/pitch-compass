#!/usr/bin/env python3
"""
Pitch Compass - assign every Irish pitch to its county, exactly.
Reads official boundary GeoJSONs from boundaries/, ray-casts each
pitch centroid, writes gaa_out/county_map.csv (osm_id,county).

Boundaries: Tailte Eireann (CC-BY 4.0) + OSNI (OGL). Pitches (c) OSM, ODbL.
"""
import json, csv, glob, sys

# candidate property keys for the county name, per agency's schema
NAME_KEYS = ["COUNTY", "ENGLISH", "COUNTY_NAME", "CountyName", "NAME",
             "County_Name", "COUNTYNAME", "name"]

def county_name(props):
    for k in NAME_KEYS:
        if k in props and props[k]:
            return str(props[k]).title().replace("County ", "").strip()
    sys.exit(f"no county-name key found in properties: {list(props)}")

def rings_of(geom):
    # yields every ring (outer + holes) of a Polygon/MultiPolygon
    if geom["type"] == "Polygon":
        for ring in geom["coordinates"]:
            yield ring
    elif geom["type"] == "MultiPolygon":
        for poly in geom["coordinates"]:
            for ring in poly:
                yield ring

def point_in_geom(lon, lat, geom):
    # even-odd ray casting across all rings (holes handled naturally)
    inside = False
    for ring in rings_of(geom):
        for i in range(len(ring) - 1):
            x1, y1 = ring[i][0], ring[i][1]
            x2, y2 = ring[i + 1][0], ring[i + 1][1]
            if (y1 > lat) != (y2 > lat):
                x_cross = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
                if x_cross > lon:
                    inside = not inside
    return inside

def bbox_of(geom):
    xs, ys = [], []
    for ring in rings_of(geom):
        for pt in ring:
            xs.append(pt[0]); ys.append(pt[1])
    return min(xs), min(ys), max(xs), max(ys)

# ---- load boundaries ----
counties = []          # (name, geom, bbox)
files = sorted(glob.glob("boundaries/*.geojson") + glob.glob("boundaries/*.json"))
if not files:
    sys.exit("no files in boundaries/ - download the two GeoJSONs first")
for path in files:
    with open(path) as f:
        gj = json.load(f)
    for feat in gj["features"]:
        geom = feat["geometry"]
        # CRS sanity: degrees, not metres
        probe = next(rings_of(geom))[0]
        if abs(probe[0]) > 180 or abs(probe[1]) > 90:
            sys.exit(f"{path} is in a projected CRS (metres) - "
                     "download the WGS84/lat-lon GeoJSON variant instead")
        counties.append((county_name(feat["properties"]), geom, bbox_of(geom)))
print(f"loaded {len(counties)} county polygons from {len(files)} file(s)")

# ---- assign pitches ----
assigned, unassigned = {}, []
with open("gaa_out/pitches.csv") as f:
    for row in csv.DictReader(f):
        lat, lon = float(row["lat"]), float(row["lon"])
        if not (51.3 <= lat <= 55.5 and -11.0 <= lon <= -5.3):
            continue                      # diaspora: not this question
        hit = None
        for name, geom, (x1, y1, x2, y2) in counties:
            if not (x1 <= lon <= x2 and y1 <= lat <= y2):
                continue                  # cheap bbox reject
            if point_in_geom(lon, lat, geom):
                hit = name
                break
        if hit:
            assigned[row["osm_id"]] = hit
        else:
            unassigned.append((row["osm_id"], lat, lon, row["name"]))

with open("gaa_out/county_map.csv", "w", newline="") as f:
    out = csv.writer(f)
    out.writerow(["osm_id", "county"])
    for osm_id, county in sorted(assigned.items()):
        out.writerow([osm_id, county])

print(f"assigned {len(assigned)} Irish ways; unassigned: {len(unassigned)}")
for u in unassigned[:15]:
    print("  unassigned:", u)

# ---- verification: known grounds must land in known counties ----

CHECKS = {"564099741": "Dublin",        # Croke Park
          "153101670": "Tipperary",     # FBD Semple Stadium
          "288780384": "Limerick"}      # TUS Gaelic Grounds

for osm_id, want in CHECKS.items():
    got = assigned.get(osm_id, "MISSING")
    print(f"check {osm_id}: expected {want}, got {got}",
          "OK" if got == want else "**FAIL**")

from collections import Counter
counts = Counter(assigned.values())
print(f"\n{len(counts)} counties represented:")
for county, n in counts.most_common():
    print(f"  {county}: {n}")