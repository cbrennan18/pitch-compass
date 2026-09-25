#!/usr/bin/env python3
"""
Pitch Compass -- docs/data/towns.json for the explorer (relaunch step 2,
item 3). GeoNames "cities1000" dump (populated places, pop >= 1000,
worldwide), CC-BY 4.0 (download.geonames.org/export/dump), filtered to
the island bbox, top ~250 by population. County assigned by the SAME
point-in-polygon method as the pitch data (assign_counties.py's
boundaries/, Londonderry->Derry), not GeoNames' own admin field, so the
county label matches the rest of the site. Stdlib only.

Licence note for the methods box (not applied to the page in this step):
"Town locations: GeoNames.org, Creative Commons Attribution 4.0."
"""
import csv, json, glob, os

HERE = os.path.dirname(os.path.abspath(__file__))
GEONAMES_TXT = "/tmp/geonames/cities1000.txt"
OUT = os.path.join(HERE, "..", "docs", "data", "towns.json")

LAT_MIN, LAT_MAX = 51.3, 55.5
LON_MIN, LON_MAX = -11.0, -5.3

NAME_KEYS = ["COUNTY", "ENGLISH", "COUNTY_NAME", "CountyName", "NAME",
             "County_Name", "COUNTYNAME", "name"]


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


def point_in_geom(lon, lat, geom):
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


counties = []
for path in sorted(glob.glob(os.path.join(HERE, "boundaries", "*.geojson"))):
    gj = json.load(open(path))
    for feat in gj["features"]:
        geom = feat["geometry"]
        counties.append((county_name(feat["properties"]), geom, bbox_of(geom)))


def assign_county(lat, lon):
    for name, geom, (x1, y1, x2, y2) in counties:
        if not (x1 <= lon <= x2 and y1 <= lat <= y2):
            continue
        if point_in_geom(lon, lat, geom):
            return "Derry" if name == "Londonderry" else name
    return None


FEATURE_CODES_KEEP = {"PPL", "PPLA", "PPLA2", "PPLA3", "PPLA4", "PPLC", "PPLG"}

candidates = []
with open(GEONAMES_TXT, encoding="utf-8") as f:
    for line in f:
        cols = line.rstrip("\n").split("\t")
        if len(cols) < 15:
            continue
        name = cols[1]
        lat, lon = float(cols[4]), float(cols[5])
        feat_code = cols[7]
        country = cols[8]
        pop = int(cols[14]) if cols[14] else 0
        if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
            continue
        if country not in ("IE", "GB"):
            continue
        if feat_code not in FEATURE_CODES_KEEP:
            continue
        candidates.append((name, lat, lon, pop))

candidates.sort(key=lambda c: c[3], reverse=True)

# the bbox clips a sliver of Scotland (Kintyre, near Antrim); a county
# match against the 32 island polygons is the real "is this Ireland"
# test, so unassigned candidates are dropped rather than kept as null
towns, unassigned = [], 0
for name, lat, lon, pop in candidates:
    if len(towns) >= 250:
        break
    county = assign_county(lat, lon)
    if county is None:
        unassigned += 1
        continue
    towns.append({"name": name, "county": county, "lat": round(lat, 4),
                  "lon": round(lon, 4), "population": pop})

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w") as f:
    json.dump({
        "note": "GeoNames.org cities1000 dump, CC-BY 4.0 (download.geonames.org/export/dump); "
                "top towns/cities on the island by population; county assigned by the same "
                "point-in-polygon method as the pitch data (not GeoNames' own admin field)",
        "source": "https://www.geonames.org/",
        "licence": "Creative Commons Attribution 4.0 (CC-BY 4.0)",
        "n": len(towns),
        "data": towns,
    }, f, separators=(",", ":"))

size = os.path.getsize(OUT)
print(f"candidates in bbox (IE/GB, populated-place codes): {len(candidates)}")
print(f"towns.json: {len(towns)} towns written, {unassigned} with no county match")
print(f"file size: {size} bytes ({size/1024:.1f} KB)")
print("\ntop 10 by population:")
for t in towns[:10]:
    print(f"  {t['name']:<20} {t['county'] or '?':<12} pop={t['population']}")
print("\nsmallest 5 in the top 250 (population floor):")
for t in towns[-5:]:
    print(f"  {t['name']:<20} {t['county'] or '?':<12} pop={t['population']}")
