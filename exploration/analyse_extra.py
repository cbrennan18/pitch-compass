#!/usr/bin/env python3
# analyse_extra.py - final exploration round for Pitch Compass.
#
# Standalone, stdlib-only. Reads the FROZEN datasets and re-derives an
# island coastline from the county polygons already in boundaries/. Does
# not touch analyse.py, the pull scripts, assign_counties.py, or any
# existing file in gaa_out/. Adds only:
#   gaa_out/extra_summary.json      every new finding as data
#   gaa_out/coastline_segments.csv  derived coast (midpoint + bearing)
#
# Helpers below are re-implemented locally on purpose: each script in this
# repo runs standalone, so the signal filter / axis tools / R4 / cardinal%
# / urban test are duplicated rather than imported.
#
# Data (c) OpenStreetMap contributors, ODbL 1.0. County boundaries:
# Tailte Eireann (CC-BY 4.0) + OSNI (OGL). Coastline is derived from those
# boundaries, no new downloads.
#
# Run from the exploration/ directory:  python3 analyse_extra.py

import csv
import math
import json
import glob
import random
import time

# ===================================================================
# LOCAL HELPERS (deliberate duplication - see analyse.py)
# ===================================================================

def is_signal(row, aspect_min=1.2):
    if row["leisure"] != "pitch":
        return False
    if float(row["aspect"]) < aspect_min:
        return False
    if not (2000 <= float(row["area_m2"]) <= 20000):
        return False
    if not (51.3 <= float(row["lat"]) <= 55.5):
        return False
    if not (-11.0 <= float(row["lon"]) <= -5.3):
        return False
    return True

def axis_diff(a, b):
    d = abs(a - b) % 180
    return min(d, 180 - d)

def r2(bearings):
    # 2-theta resultant: single preferred axis (0 chaos, 1 lockstep)
    n = len(bearings)
    s = sum(math.sin(math.radians(2 * b)) for b in bearings)
    c = sum(math.cos(math.radians(2 * b)) for b in bearings)
    return math.hypot(s, c) / n

def r4(bearings):
    # 4-theta resultant: four-fold cardinal pattern
    n = len(bearings)
    s = sum(math.sin(math.radians(4 * b)) for b in bearings)
    c = sum(math.cos(math.radians(4 * b)) for b in bearings)
    return math.hypot(s, c) / n

def r4_full(bearings):
    n = len(bearings)
    s = sum(math.sin(math.radians(4 * b)) for b in bearings)
    c = sum(math.cos(math.radians(4 * b)) for b in bearings)
    R = math.hypot(s, c) / n
    mean = (math.degrees(math.atan2(s, c)) / 4) % 90
    return R, mean

def cardinal_pct(bearings, tol=15):
    near = sum(1 for b in bearings if min(b % 90, 90 - (b % 90)) <= tol)
    return round(100 * near / len(bearings), 1)

CITIES = [(53.3498, -6.2603), (51.8985, -8.4756), (53.2707, -9.0568),
          (52.6638, -8.6267), (54.5973, -5.9301)]   # Dub Cork Gal Lim Bel

def is_urban(row):
    lat, lon = float(row["lat"]), float(row["lon"])
    for clat, clon in CITIES:
        dx = (lon - clon) * math.cos(math.radians(clat)) * 111.32
        dy = (lat - clat) * 110.54
        if math.hypot(dx, dy) <= 20:
            return True
    return False

def sunset_azimuth(declination_deg):
    d = math.radians(declination_deg)
    lat = math.radians(53.4)
    return 360 - math.degrees(math.acos(math.sin(d) / math.cos(lat)))

def count_near_axis(bearings, axis, tol=15):
    return sum(1 for b in bearings if axis_diff(b, axis) <= tol)

def dist_m(r1, r2):
    dx = (float(r1["lon"]) - float(r2["lon"])) * math.cos(math.radians(53.4)) * 111320
    dy = (float(r1["lat"]) - float(r2["lat"])) * 110540
    return math.hypot(dx, dy)

def rayleigh_p(n, R):
    # standard large-n Rayleigh approximation for a resultant length R
    return math.exp(-n * R * R)

def two_sided_p(z):
    return math.erfc(abs(z) / math.sqrt(2))

# ===================================================================
# LOAD FROZEN DATA
# ===================================================================

ALL_PITCHES = []
with open("gaa_out/pitches.csv") as f:
    for row in csv.DictReader(f):
        ALL_PITCHES.append(row)
BY_OSMID = {r["osm_id"]: r for r in ALL_PITCHES}

signal = [r for r in ALL_PITCHES if is_signal(r)]
sig_bearings = [float(r["bearing_deg"]) for r in signal]
urban = [r for r in signal if is_urban(r)]
rural = [r for r in signal if not is_urban(r)]
urban_b = [float(r["bearing_deg"]) for r in urban]
rural_b = [float(r["bearing_deg"]) for r in rural]

# rural soccer (soccer CSV has no leisure column)
soccer_rows = []
with open("soccer_out/soccer_pitches.csv") as f:
    for row in csv.DictReader(f):
        soccer_rows.append(row)

def soccer_signal(row):
    return (float(row["aspect"]) >= 1.2
            and 2000 <= float(row["area_m2"]) <= 20000
            and 51.3 <= float(row["lat"]) <= 55.5
            and -11.0 <= float(row["lon"]) <= -5.3)

soccer_sig_b = [float(r["bearing_deg"]) for r in soccer_rows if soccer_signal(r)]
soccer_rural_b = [float(r["bearing_deg"]) for r in soccer_rows
                  if soccer_signal(r) and not is_urban(r)]

# county map (Londonderry -> Derry, per GAA convention / analyse.py)
county_of = {}
with open("gaa_out/county_map.csv") as f:
    for r in csv.DictReader(f):
        name = "Derry" if r["county"] == "Londonderry" else r["county"]
        county_of[r["osm_id"]] = name

SEABOARD = {"Kerry", "Clare", "Galway", "Mayo", "Sligo", "Donegal"}
DRUMLIN = {"Cavan", "Monaghan", "Down", "Leitrim"}

def cohort_bearings(county_set):
    return [float(r["bearing_deg"]) for r in signal
            if county_of.get(r["osm_id"]) in county_set]

seaboard_b = cohort_bearings(SEABOARD)
drumlin_b = cohort_bearings(DRUMLIN)

# ===================================================================
# CALIBRATION GATE - reproduce the frozen anchors before anything new
# ===================================================================

print("=" * 64)
print("CALIBRATION GATE (must match frozen anchors)")
print("=" * 64)

anchors = [
    ("signal n", len(signal), 2707, 0),
    ("island R4", round(r4(sig_bearings), 3), 0.107, 3),
    ("urban n", len(urban), 540, 0),
    ("urban R4", round(r4(urban_b), 3), 0.236, 3),
    ("rural n", len(rural), 2167, 0),
    ("rural R4", round(r4(rural_b), 4), 0.0957, 4),
    ("rural soccer n", len(soccer_rural_b), 1471, 0),
    ("rural soccer R4", round(r4(soccer_rural_b), 4), 0.0598, 4),
]

all_ok = True
for label, got, want, dp in anchors:
    ok = (got == want)
    all_ok = all_ok and ok
    print(f"  {label:<18} got={got:<10} want={want:<10} {'OK' if ok else '** MISS **'}")

if not all_ok:
    raise SystemExit("\nCALIBRATION FAILED - refusing to compute new numbers. "
                     "The frozen filters do not reproduce. Stop and investigate.")
print("  --> all anchors reproduced. Proceeding to new analyses.\n")

calibration = {
    "passed": True,
    "anchors": {label: {"got": got, "want": want} for label, got, want, _ in anchors},
}

# ===================================================================
# A. WIND AXIS TEST  (45 deg along the SW wind  vs  135 deg across it)
#    Both are equally diagonal -> the anti-diagonal grid effect hits
#    both identically, so any 45-vs-135 gap is genuine wind signal.
# ===================================================================

def wind_test(bearings, tols=(10, 15, 20)):
    n = len(bearings)
    out = {"n": n, "tolerances": {}}
    for tol in tols:
        c45 = count_near_axis(bearings, 45, tol)
        c135 = count_near_axis(bearings, 135, tol)
        p = 2 * tol / 180.0
        E = n * p
        var = n * p * (1 - p)
        z45 = (c45 - E) / math.sqrt(var)
        z135 = (c135 - E) / math.sqrt(var)
        denom = math.sqrt(c45 + c135) if (c45 + c135) > 0 else float("nan")
        zdiff = (c45 - c135) / denom if (c45 + c135) > 0 else 0.0
        out["tolerances"][str(tol)] = {
            "c45": c45, "c135": c135, "expected_each": round(E, 1),
            "z45_vs_uniform": round(z45, 2), "z135_vs_uniform": round(z135, 2),
            "z_diff_45_minus_135": round(zdiff, 2),
            "p_diff_two_sided": two_sided_p(zdiff),
        }
    return out

wind_cohorts = {
    "all_island": sig_bearings,
    "rural_only": rural_b,
    "western_seaboard": seaboard_b,
    "drumlin_belt": drumlin_b,
}
wind_axis = {name: wind_test(b) for name, b in wind_cohorts.items()}

print("=" * 64)
print("A. WIND AXIS TEST  (45 along-wind  vs  135 across-wind)")
print("=" * 64)
for name, res in wind_axis.items():
    print(f"\n  {name}  (n={res['n']})")
    print("    tol  c45   c135  exp    z45    z135   z(45-135)  p")
    for tol, t in res["tolerances"].items():
        print(f"    {tol:>3}  {t['c45']:<5} {t['c135']:<5} {t['expected_each']:<6} "
              f"{t['z45_vs_uniform']:<6} {t['z135_vs_uniform']:<6} "
              f"{t['z_diff_45_minus_135']:<9} {t['p_diff_two_sided']:.4g}")
print("\n  (drumlin: ~58 tilt sits near the wind's 45; a 45-vs-135 asymmetry")
print("   here separates ice-grain from wind.)\n")

# ===================================================================
# B. COASTLINE SUITE
#    Derive the exterior coastline from the county polygons.
# ===================================================================

def rings_of(geom):
    if geom["type"] == "Polygon":
        for ring in geom["coordinates"]:
            yield ring
    elif geom["type"] == "MultiPolygon":
        for poly in geom["coordinates"]:
            for ring in poly:
                yield ring

# Vertex-snap precision for the cancellation hash. The spec proposed ~5 dp,
# but these boundaries are digitised county-by-county: shared internal borders
# differ by a few metres to ~100 m between the two counties' independent
# generalisation, so exact 5-dp endpoints do NOT match and internal borders
# survive as false "coast" (validated: at 5 dp the nearest "coast" to Longford
# is a segment owned by Longford county itself, 12 km away). Snapping the hash
# to 3 dp (~100 m) makes them cancel while leaving the true coast intact
# (validated: Mullingar 74 km, Athlone 66 km, all coastal checks < 1 km).
HASH_PREC = 3

def exterior_segments(path):
    # segments appearing exactly once within THIS file are exterior;
    # internal county borders appear twice (order-independent) and cancel.
    with open(path) as f:
        gj = json.load(f)
    counts = {}
    example = {}
    for feat in gj["features"]:
        for ring in rings_of(feat["geometry"]):
            for i in range(len(ring) - 1):
                a = (round(ring[i][0], HASH_PREC), round(ring[i][1], HASH_PREC))
                b = (round(ring[i + 1][0], HASH_PREC), round(ring[i + 1][1], HASH_PREC))
                if a == b:
                    continue                      # < ~100 m edge, dropped
                key = frozenset((a, b))           # order-independent
                counts[key] = counts.get(key, 0) + 1
                if key not in example:
                    example[key] = (a, b)         # (lon,lat),(lon,lat)
    return [example[k] for k, v in counts.items() if v == 1]

def seg_mid(s):
    (lon1, lat1), (lon2, lat2) = s
    return ((lon1 + lon2) / 2.0, (lat1 + lat2) / 2.0)    # (lon, lat)

def seg_bearing(s):
    (lon1, lat1), (lon2, lat2) = s
    clat = math.radians((lat1 + lat2) / 2.0)
    east = (lon2 - lon1) * math.cos(clat)
    north = (lat2 - lat1)
    return math.degrees(math.atan2(east, north)) % 180

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

files = sorted(glob.glob("boundaries/*.geojson") + glob.glob("boundaries/*.json"))
if len(files) != 2:
    raise SystemExit(f"expected exactly 2 boundary files, found {len(files)}: {files}")

exts = [exterior_segments(p) for p in files]
mids = [[seg_mid(s) for s in e] for e in exts]

# scrub the ROI/NI land border: drop any exterior segment whose midpoint
# is within 3 km of an exterior midpoint from the OTHER file.
SCRUB_CELL = 0.05
coast = []
kept_per_file = []
for i in range(2):
    other = build_point_buckets(mids[1 - i], SCRUB_CELL)
    kept = [s for s, m in zip(exts[i], mids[i])
            if not near_any_point(m[0], m[1], other, SCRUB_CELL, 3.0)]
    kept_per_file.append(len(kept))
    coast.extend(kept)

# spatial index of coast segments by midpoint cell for nearest queries
COAST_CELL = 0.1
seg_buckets = {}
for idx, s in enumerate(coast):
    mlon, mlat = seg_mid(s)
    seg_buckets.setdefault((int(math.floor(mlon / COAST_CELL)),
                            int(math.floor(mlat / COAST_CELL))), []).append(idx)

def pt_seg_km(plon, plat, s):
    # point-to-segment distance, local planar plane centred on the pitch
    (lon1, lat1), (lon2, lat2) = s
    k = math.cos(math.radians(plat)) * 111.32
    ax = (lon1 - plon) * k; ay = (lat1 - plat) * 110.54
    bx = (lon2 - plon) * k; by = (lat2 - plat) * 110.54
    dx = bx - ax; dy = by - ay
    L2 = dx * dx + dy * dy
    if L2 == 0.0:
        return math.hypot(ax, ay)
    t = -(ax * dx + ay * dy) / L2
    t = max(0.0, min(1.0, t))
    cx = ax + t * dx; cy = ay + t * dy
    return math.hypot(cx, cy)

def nearest_coast(plon, plat):
    pcx = int(math.floor(plon / COAST_CELL))
    pcy = int(math.floor(plat / COAST_CELL))
    cell_km = min(COAST_CELL * 110.54,
                  COAST_CELL * math.cos(math.radians(plat)) * 111.32)
    best, besti, ring = None, -1, 0
    while True:
        for cx in range(pcx - ring, pcx + ring + 1):
            for cy in range(pcy - ring, pcy + ring + 1):
                if max(abs(cx - pcx), abs(cy - pcy)) != ring:
                    continue                       # only the ring's shell
                for idx in seg_buckets.get((cx, cy), []):
                    d = pt_seg_km(plon, plat, coast[idx])
                    if best is None or d < best:
                        best, besti = d, idx
        # ring R+1 has minimum possible distance >= ring*cell_km
        if best is not None and ring * cell_km > best:
            break
        ring += 1
        if ring > 3000:
            break
    return best, besti

# ---- B.3 VALIDATE: known-distance checks (the binding validation) ----
print("=" * 64)
print("B. COASTLINE SUITE")
print("=" * 64)
total_segments = len(coast)
print(f"  exterior segments kept: {total_segments} "
      f"(per file: {kept_per_file[0]} + {kept_per_file[1]}; "
      f"before scrub: {len(exts[0])} + {len(exts[1])})")

def check_pitch(label, osm_id, kind, bound):
    r = BY_OSMID.get(str(osm_id))
    if r is None:
        return {"label": label, "osm_id": osm_id, "found": False, "passed": False}
    d, idx = nearest_coast(float(r["lon"]), float(r["lat"]))
    passed = (d < bound) if kind == "lt" else (d > bound)
    return {"label": label, "osm_id": osm_id, "name": r["name"],
            "lat": float(r["lat"]), "lon": float(r["lon"]),
            "dist_km": round(d, 2), "kind": kind, "bound_km": bound,
            "found": True, "passed": passed}

coastal_checks = [
    check_pitch("Dingle / Pairc an Asaigh", 925165261, "lt", 2.0),
    check_pitch("Bundoran", 234425863, "lt", 2.0),
    check_pitch("Youghal GAA Club", 1475352696, "lt", 2.0),
]
# deep-inland: Mullingar (Cusack Park); fall back to Longford if <40 km
inland_check = check_pitch("Mullingar / Cusack Park", 411793025, "gt", 40.0)
if not inland_check["passed"]:
    fb = check_pitch("Longford (fallback)", 177841568, "gt", 40.0)
    print(f"  inland Mullingar landed at {inland_check.get('dist_km')} km "
          f"(< 40); using Longford fallback")
    inland_check = fb

print("  known-distance checks (binding validation):")
for c in coastal_checks + [inland_check]:
    tag = "OK" if c["passed"] else "** FAIL **"
    print(f"    {c['label']:<26} osm_id={c['osm_id']:<11} "
          f"dist={c.get('dist_km')} km  ({c['kind']} {c['bound_km']})  {tag}")

validation_passed = all(c["passed"] for c in coastal_checks + [inland_check])
plausible_count = (5000 <= total_segments <= 200000)
print(f"  segment-count plausibility (5k-200k, informational; the OSNI "
      f"largescale file is ungeneralised so the count runs high): "
      f"{'OK' if plausible_count else 'CHECK'}")
if not validation_passed:
    print("  ** WARNING: coastline validation FAILED - coast-cohort numbers "
          "below are not trustworthy. **")
print()

# ---- per-pitch distance + nearest-segment bearing; distance cohorts ----
dist_cohorts = {"<5km": [], "5-15km": [], ">15km": []}
for r in signal:
    plon, plat = float(r["lon"]), float(r["lat"])
    d, idx = nearest_coast(plon, plat)
    cb = seg_bearing(coast[idx])
    pb = float(r["bearing_deg"])
    rec = {"pb": pb, "cb": cb, "d": d}
    if d < 5:
        dist_cohorts["<5km"].append(rec)
    elif d <= 15:
        dist_cohorts["5-15km"].append(rec)
    else:
        dist_cohorts[">15km"].append(rec)

BIN_LABELS = ["0-15", "15-30", "30-45", "45-60", "60-75", "75-90"]

def coast_relative(recs):
    # axis_diff(pitch bearing, local coast bearing) in six 15-deg bins.
    # parallel bulge (0-15) = shelter / along-coast; perpendicular (75-90)
    # = facing the sea. Also a binomial z on the parallel (0-15) excess.
    n = len(recs)
    bins = [0] * 6
    for rec in recs:
        d = axis_diff(rec["pb"], rec["cb"])
        bins[min(int(d // 15), 5)] += 1
    p_par = 15.0 / 90.0                    # uniform expectation for one bin
    E = n * p_par
    var = n * p_par * (1 - p_par)
    z_par = (bins[0] - E) / math.sqrt(var) if var > 0 else 0.0
    return {
        "n": n,
        "bins": {lab: {"count": c, "pct": round(100 * c / n, 1) if n else 0.0}
                 for lab, c in zip(BIN_LABELS, bins)},
        "parallel_0_15": bins[0], "perpendicular_75_90": bins[5],
        "parallel_expected_uniform": round(E, 1),
        "z_parallel_excess": round(z_par, 2),
        "p_parallel_two_sided": two_sided_p(z_par),
    }

coast_wind = {}
coast_align = {}
print("  distance-to-coast cohorts:")
for label, recs in dist_cohorts.items():
    bearings = [rec["pb"] for rec in recs]
    coast_wind[label] = wind_test(bearings) if bearings else {"n": 0}
    coast_align[label] = coast_relative(recs) if recs else {"n": 0}
    print(f"\n    [{label}]  n={len(recs)}")
    if recs:
        ca = coast_align[label]
        print("      coast-relative alignment (pitch vs local coast bearing):")
        for lab in BIN_LABELS:
            b = ca["bins"][lab]
            print(f"        {lab:>6}: {b['count']:<5} ({b['pct']}%)")
        print(f"      parallel(0-15) z={ca['z_parallel_excess']} "
              f"p={ca['p_parallel_two_sided']:.4g}  "
              f"[expected {ca['parallel_expected_uniform']}]")
        cw15 = coast_wind[label]["tolerances"]["15"]
        print(f"      wind(tol15): c45={cw15['c45']} c135={cw15['c135']} "
              f"z(45-135)={cw15['z_diff_45_minus_135']} "
              f"p={cw15['p_diff_two_sided']:.4g}")
print()

# ---- write coastline_segments.csv (for the eventual map visuals) ----
with open("gaa_out/coastline_segments.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["mid_lat", "mid_lon", "bearing_deg"])
    for s in coast:
        mlon, mlat = seg_mid(s)
        w.writerow([round(mlat, 6), round(mlon, 6), round(seg_bearing(s), 1)])
print(f"  wrote gaa_out/coastline_segments.csv ({total_segments} rows)\n")

coastline = {
    "total_segments": total_segments,
    "segments_per_file": {files[0]: kept_per_file[0], files[1]: kept_per_file[1]},
    "segments_before_scrub": {files[0]: len(exts[0]), files[1]: len(exts[1])},
    "validation": {
        "passed": validation_passed,
        "count_plausible": plausible_count,
        "coastal_checks": coastal_checks,
        "inland_check": inland_check,
        "note": "known-distance checks are the binding validation; the "
                "segment count is informational (thousands to low tens of "
                "thousands is healthy at ~20 m generalisation).",
    },
    "distance_cohorts": {
        label: {
            "n": len(recs),
            "wind": coast_wind[label],
            "coast_relative_alignment": coast_align[label],
        } for label, recs in dist_cohorts.items()
    },
    "hash_precision_dp": HASH_PREC,
    "edge_cases_noted": [
        "spec proposed a 5-dp cancellation hash; these boundaries are digitised "
        "county-by-county and shared internal borders differ by a few metres to "
        "~100 m, so at 5 dp they did NOT cancel and leaked in as false coast "
        "(Longford read 12 km from a segment owned by Longford itself). Snapping "
        "the hash to 3 dp (~100 m) makes them cancel; the true coast is unchanged "
        "at this resolution and all distance checks pass.",
        "near Lough Foyle / Carlingford Lough real ROI and NI coasts pass "
        "within 3 km, so the cross-file border scrub may remove a little genuine "
        "coast there.",
        "offshore islands are separate polygons and correctly add real coast.",
        "the OSNI largescale NI file is ungeneralised, so it contributes most "
        "segments; the segment count runs high but the distance checks are the "
        "binding validation.",
    ],
}

# ===================================================================
# C. BOOTSTRAP CONFIDENCE INTERVALS
# ===================================================================

random.seed(1798)

by_county = {}
for r in signal:
    c = county_of.get(r["osm_id"])
    if c:
        by_county.setdefault(c, []).append(float(r["bearing_deg"]))

def boot_r4_ci(bearings, B=2000):
    n = len(bearings)
    stats = sorted(r4([bearings[random.randrange(n)] for _ in range(n)])
                   for _ in range(B))
    return stats[int(0.025 * B)], stats[int(0.975 * B)]

def noise_ceiling(n, sims=500):
    vals = sorted(r4([random.uniform(0, 180) for _ in range(n)])
                  for _ in range(sims))
    return vals[int(0.95 * sims)]

print("=" * 64)
print("C. BOOTSTRAP CONFIDENCE INTERVALS (n>=30, 2000 resamples, seed 1798)")
print("=" * 64)
print("  county        n    R4      CI_low  CI_high  noise95  under_noise")
ci_rows = []
for county in sorted(by_county):
    bearings = by_county[county]
    n = len(bearings)
    if n < 30:
        continue
    R = r4(bearings)
    lo, hi = boot_r4_ci(bearings)
    ceil = noise_ceiling(n)
    under = lo <= ceil          # CI overlaps the uniform-noise level for this n
    ci_rows.append({"county": county, "n": n, "R4": round(R, 4),
                    "ci_low": round(lo, 4), "ci_high": round(hi, 4),
                    "noise_ceiling_95": round(ceil, 4), "ci_overlaps_noise": under})
    print(f"  {county:<12} {n:<4} {round(R,4):<7} {round(lo,4):<7} "
          f"{round(hi,4):<8} {round(ceil,4):<8} {'yes' if under else 'no'}")

# Longford - Tyrone R4 difference
diff_ci = None
if "Longford" in by_county and "Tyrone" in by_county:
    lf, ty = by_county["Longford"], by_county["Tyrone"]
    real_diff = r4(lf) - r4(ty)
    diffs = sorted(
        r4([lf[random.randrange(len(lf))] for _ in range(len(lf))]) -
        r4([ty[random.randrange(len(ty))] for _ in range(len(ty))])
        for _ in range(2000))
    dlo, dhi = diffs[int(0.025 * 2000)], diffs[int(0.975 * 2000)]
    diff_ci = {"longford_n": len(lf), "tyrone_n": len(ty),
               "r4_diff": round(real_diff, 4),
               "ci_low": round(dlo, 4), "ci_high": round(dhi, 4),
               "excludes_zero": (dlo > 0 or dhi < 0)}
    print(f"\n  Longford - Tyrone R4 diff = {round(real_diff,4)} "
          f"95% CI [{round(dlo,4)}, {round(dhi,4)}]  "
          f"{'excludes 0' if diff_ci['excludes_zero'] else 'includes 0'}")
print()

bootstrap_ci = {"seed": 1798, "resamples": 2000, "noise_sims": 500,
                "counties": ci_rows, "longford_minus_tyrone": diff_ci,
                "note": "ci_overlaps_noise=yes means the county's R4 CI reaches "
                        "down to the 95th-pctile R4 of pure uniform noise at its "
                        "n - its order is not distinguishable from chance."}

# ===================================================================
# D. ROBUSTNESS GRID
# ===================================================================

SUNSET_AXES = [("June", sunset_azimuth(23.44) % 180),
               ("Equinox", sunset_azimuth(0.0) % 180),
               ("Winter", sunset_azimuth(-23.44) % 180)]

def signal_for_aspect(aspect_min):
    rows = [r for r in ALL_PITCHES if is_signal(r, aspect_min)]
    b = [float(r["bearing_deg"]) for r in rows]
    ub = [float(r["bearing_deg"]) for r in rows if is_urban(r)]
    rb = [float(r["bearing_deg"]) for r in rows if not is_urban(r)]
    return b, ub, rb

def grid_row(aspect_min, tol):
    b, ub, rb = signal_for_aspect(aspect_min)
    row = {
        "aspect_min": aspect_min, "tol": tol, "n": len(b),
        "island_R4": round(r4(b), 4),
        "cardinal_pct": cardinal_pct(b, tol),
        "urban_R4": round(r4(ub), 4), "urban_n": len(ub),
        "rural_R4": round(r4(rb), 4), "rural_n": len(rb),
        "sunset": {name: count_near_axis(b, axis, tol) for name, axis in SUNSET_AXES},
    }
    return row

grid = [grid_row(1.2, 15)]                                   # baseline
for a in (1.15, 1.3, 1.4):                                   # vary aspect, tol=15
    grid.append(grid_row(a, 15))
for t in (10, 20):                                           # vary tol, aspect=1.2
    grid.append(grid_row(1.2, t))

print("=" * 64)
print("D. ROBUSTNESS GRID (vary one dimension from aspect 1.2 / tol 15)")
print("=" * 64)
print("  asp   tol  n     islR4  card%  urbR4  rurR4  June Equ Win")
for row in grid:
    s = row["sunset"]
    tag = "  <- baseline" if (row["aspect_min"] == 1.2 and row["tol"] == 15) else ""
    print(f"  {row['aspect_min']:<5} {row['tol']:<4} {row['n']:<5} "
          f"{row['island_R4']:<6} {row['cardinal_pct']:<6} {row['urban_R4']:<6} "
          f"{row['rural_R4']:<6} {s['June']:<4} {s['Equinox']:<3} {s['Winter']:<3}{tag}")
print("  (R4 columns are tolerance-invariant; they repeat down the tol rows.)\n")

robustness_grid = {
    "baseline": {"aspect_min": 1.2, "tol": 15},
    "rows": grid,
    "note": "headline findings hold if island R4, urban>rural R4 ordering, and "
            "the June<Winter<Equinox sunset ordering persist across rows.",
}

# ===================================================================
# E. MULTIPLE-COMPARISONS NOTE  (honesty inventory - count ALL tests,
#    including this round's wind and coastline cohort tests)
# ===================================================================

tests = []
def add_test(name, p, note=""):
    tests.append({"test": name, "p": p, "note": note})

# --- project (frozen) inferential tests ---
add_test("2-theta island: single preferred playing direction",
         rayleigh_p(len(sig_bearings), r2(sig_bearings)))
add_test("4-theta island: cardinal (compass) alignment",
         rayleigh_p(len(sig_bearings), r4(sig_bearings)))
add_test("4-theta urban vs uniform",
         rayleigh_p(len(urban_b), r4(urban_b)))
add_test("4-theta rural vs uniform",
         rayleigh_p(len(rural_b), r4(rural_b)))
add_test("4-theta drumlin belt vs uniform",
         rayleigh_p(len(drumlin_b), r4(drumlin_b)))
add_test("4-theta western seaboard vs uniform",
         rayleigh_p(len(seaboard_b), r4(seaboard_b)))
add_test("soccer 2-theta E-W preference",
         rayleigh_p(len(soccer_sig_b), r2(soccer_sig_b)))
add_test("rural GAA vs soccer R4 gap (permutation, 10k, seed 1798)",
         0.0549, "frozen result from analyse.py")

# sunset tests (computed live from the signal sample, tol 15)
n = len(sig_bearings)
june_axis = sunset_azimuth(23.44) % 180
winter_axis = sunset_azimuth(-23.44) % 180
c_june = count_near_axis(sig_bearings, june_axis, 15)
c_winter = count_near_axis(sig_bearings, winter_axis, 15)
p_ss = 1.0 / 6.0
E_ss = n * p_ss
z_june = (c_june - E_ss) / math.sqrt(n * p_ss * (1 - p_ss))
z_jw = (c_june - c_winter) / math.sqrt(c_june + c_winter)
add_test("sunset: June-sunset-axis deficit vs uniform (binomial z)",
         two_sided_p(z_june), f"z={round(z_june,2)}")
add_test("sunset: June vs Winter axis (equally diagonal control)",
         two_sided_p(z_jw), f"z={round(z_jw,2)}")

# twin pitches: parallel/perp concentration vs uniform (computed live)
diffs = []
for i in range(len(signal)):
    ri = signal[i]
    for j in range(i + 1, len(signal)):
        if dist_m(ri, signal[j]) <= 300:
            diffs.append(axis_diff(float(ri["bearing_deg"]),
                                   float(signal[j]["bearing_deg"])))
n_pairs = len(diffs)
extremes = sum(1 for d in diffs if d <= 15 or d > 75)     # parallel or perp
p_ext = 30.0 / 90.0                                        # two 15-deg bins
z_twin = (extremes - n_pairs * p_ext) / math.sqrt(n_pairs * p_ext * (1 - p_ext))
add_test("twin pitches: parallel/perpendicular concentration vs uniform",
         two_sided_p(z_twin), f"n_pairs={n_pairs}, z={round(z_twin,1)}")

# --- this round's new tests (adjustment 2: count them all) ---
for name in ("all_island", "rural_only", "western_seaboard", "drumlin_belt"):
    p = wind_axis[name]["tolerances"]["15"]["p_diff_two_sided"]
    add_test(f"wind 45-vs-135 asymmetry - {name} (tol 15)", p,
             "tol 10/20 are sensitivity checks on the same hypothesis")
for label in ("<5km", "5-15km", ">15km"):
    if coast_wind[label].get("n", 0):
        p = coast_wind[label]["tolerances"]["15"]["p_diff_two_sided"]
        add_test(f"coastline wind 45-vs-135 - {label} (tol 15)", p)
for label in ("<5km", "5-15km", ">15km"):
    if coast_align[label].get("n", 0):
        p = coast_align[label]["p_parallel_two_sided"]
        add_test(f"coastline coast-relative parallel excess - {label}", p)

k = len(tests)
alpha = 0.05
bonf = alpha / k

print("=" * 64)
print("E. MULTIPLE-COMPARISONS NOTE (honesty inventory)")
print("=" * 64)
print(f"  distinct hypothesis tests enumerated: {k}")
print(f"  Bonferroni-adjusted alpha: 0.05 / {k} = {bonf:.5f}\n")
print("  test                                                          p         survives")
survivors = []
for t in tests:
    surv = t["p"] < bonf
    if surv:
        survivors.append(t["test"])
    ptxt = f"{t['p']:.3g}"
    print(f"  {t['test'][:58]:<58} {ptxt:<9} {'YES' if surv else 'no'}")
print(f"\n  {len(survivors)} of {k} survive Bonferroni at alpha={bonf:.5f}:")
for s in survivors:
    print(f"    - {s}")
print("\n  (Tolerance/robustness variants are folded into their parent hypothesis,")
print("   not counted separately.)\n")

multiple_comparisons = {
    "n_tests": k, "alpha": alpha, "bonferroni_alpha": bonf,
    "tests": tests, "survivors": survivors,
    "note": "counts all inferential tests including this round's wind and "
            "coastline cohort tests; tolerance variants folded into parents.",
}

# ===================================================================
# WRITE extra_summary.json
# ===================================================================

summary = {
    "project": "Pitch Compass - analyse_extra.py (final exploration round)",
    "attribution": "Pitches (c) OpenStreetMap contributors, ODbL 1.0. "
                   "County boundaries: Tailte Eireann (CC-BY 4.0), OSNI (OGL). "
                   "Coastline derived from those boundaries (no new downloads).",
    "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "calibration": calibration,
    "wind_axis": wind_axis,
    "coastline": coastline,
    "bootstrap_ci": bootstrap_ci,
    "robustness_grid": robustness_grid,
    "multiple_comparisons": multiple_comparisons,
}

with open("gaa_out/extra_summary.json", "w") as f:
    json.dump(summary, f, indent=2)
print("wrote gaa_out/extra_summary.json")
