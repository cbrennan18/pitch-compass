#!/usr/bin/env python3
"""
Pitch Compass -- GPF reconciliation (relaunch step 2 follow-up, item 3).
Source: gaapitchfinder_data.csv, GAA Pitch Finder by Ryan McGuinness,
CC BY 4.0, commit 256eb08482b2c385614415db18841f8a43e1f61b.
Credit: "Club and pitch location data from GAA Pitch Finder by Ryan
McGuinness: https://gaapitchfinder.com"

1. Extract GPF's "<County> GAA" rows (island scope: File=='Ireland') --
   the county grounds per GPF.
2. Reconcile against exploration/county_grounds.csv: pair each GPF row
   to its nearest same-county CSV row (by distance, not name string --
   GPF and Wikipedia spell/order names differently), report matches,
   mismatches, and counties with >1 "<County> GAA" row.
3. Re-match: for any pairing where GPF's coordinate differs from the
   CSV row's current reference point by more than 50 m, and the row was
   NOT a human-verified pick (design/verify.md), redo the same
   inside-boundary / 150m-radius(L>=130) match used in
   make_county_grounds.py, using GPF's coordinate as the new reference
   point. Updates county_grounds.csv in place where a cleaner match
   results (in particular, resolves Pairc Esler).

Stdlib only. Reads exploration/gaa_out/{raw_overpass.json,pitches.csv},
exploration/county_grounds.csv, and /tmp/gaapitchfinder/gaapitchfinder_data.csv
(the pinned-commit clone). Writes exploration/county_grounds.csv,
exploration/gpf_reconciliation.md.
"""
import json, csv, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
def p(*parts): return os.path.join(HERE, *parts)

GPF_PATH = "/tmp/gaapitchfinder/gaapitchfinder_data.csv"
GPF_COMMIT = "256eb08482b2c385614415db18841f8a43e1f61b"

LAT0 = 53.4
def dist_m(lat1, lon1, lat2, lon2):
    dx = (lon2 - lon1) * math.cos(math.radians(LAT0)) * 111320
    dy = (lat2 - lat1) * 110540
    return math.hypot(dx, dy)

def point_in_ring(lon, lat, ring):
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]; x2, y2 = ring[(i + 1) % n]
        if (y1 > lat) != (y2 > lat):
            x_cross = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
            if x_cross > lon:
                inside = not inside
    return inside

raw_els = json.load(open(p("gaa_out", "raw_overpass.json")))["elements"]
ways_by_id = {e["id"]: e for e in raw_els if e["type"] == "way"}
pitch_rows = list(csv.DictReader(open(p("gaa_out", "pitches.csv"))))

def outline_ring(way_id):
    e = ways_by_id.get(way_id)
    if not e or "geometry" not in e:
        return None
    return [(g["lon"], g["lat"]) for g in e["geometry"]]

CELL = 0.01
buckets = {}
for i, r in enumerate(pitch_rows):
    key = (round(float(r["lat"]) / CELL), round(float(r["lon"]) / CELL))
    buckets.setdefault(key, []).append(i)

def nearby_candidates(lat, lon, radius_m):
    cy, cx = round(lat / CELL), round(lon / CELL)
    out = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            for i in buckets.get((cy + dy, cx + dx), ()):
                r = pitch_rows[i]
                d = dist_m(lat, lon, float(r["lat"]), float(r["lon"]))
                if d <= radius_m:
                    out.append((d, r))
    return out

def inside_boundary_candidates(way_id):
    ring = outline_ring(way_id)
    if ring is None:
        return None
    hits = []
    for r in pitch_rows:
        if int(r["osm_id"]) == way_id or r["leisure"] not in ("pitch", "sports_centre"):
            continue
        if point_in_ring(float(r["lon"]), float(r["lat"]), ring):
            hits.append(r)
    return hits

def run_match(rlat, rlon, way_id):
    """Same algorithm as make_county_grounds.py. Returns
    (bearing, source, match_dist_m, n_candidates, plat, plon)."""
    inside = inside_boundary_candidates(way_id) if way_id else None
    if inside:
        if len(inside) == 1:
            r = inside[0]
            d = dist_m(rlat, rlon, float(r["lat"]), float(r["lon"]))
            return (r["bearing_deg"], "matched_inside_boundary", round(d, 1), 1,
                    float(r["lat"]), float(r["lon"]))
        return ("", "needs_manual", "", len(inside), rlat, rlon)
    cands = nearby_candidates(rlat, rlon, 150)
    if way_id:
        cands = [(d, r) for d, r in cands if int(r["osm_id"]) != way_id]
    plausible = [(d, r) for d, r in cands if float(r["length_m"]) >= 130]
    if len(plausible) == 1:
        d, r = plausible[0]
        return (r["bearing_deg"], "matched_150m_radius", round(d, 1), 1,
                float(r["lat"]), float(r["lon"]))
    if len(plausible) > 1:
        d, r = max(plausible, key=lambda dr: float(dr[1]["length_m"]) * float(dr[1]["width_m"]))
        return ("", "needs_manual", round(d, 1), len(plausible), rlat, rlon)
    return ("", "needs_manual", "", 0, rlat, rlon)


# way_id lookup -- parsed directly from make_county_grounds.py's GROUNDS
# table (not re-transcribed by hand) so this can't drift out of sync.
import re as _re
_src = open(p("make_county_grounds.py")).read()
_pattern = _re.compile(r'\("([^"]+)","([^"]+)","[a-z_]+",\d+,.*?, (\d+|None)\),', _re.S)
WAY_IDS = {(n, c): int(w) for n, c, w in _pattern.findall(_src) if w != "None"}

# rows resolved by human satellite verification -- never overridden by GPF re-match
VERIFIED = {
    ("Healy Park", "Tyrone"), ("MacCumhaill Park", "Donegal"),
    ("St Mary's Park", "Monaghan"), ("Fr Tierney Park", "Donegal"),
    ("Aughrim County Ground", "Wicklow"), ("Pearse Park", "Wicklow"),
    ("Gaelic Grounds", "Louth"),
}

MOVE_THRESHOLD_M = 50

# ---- load GPF, island scope ----
gpf_all = list(csv.DictReader(open(GPF_PATH)))
gpf = [r for r in gpf_all if r["File"] == "Ireland"]

ALL32 = {"Antrim","Armagh","Carlow","Cavan","Clare","Cork","Derry","Donegal","Down",
         "Dublin","Fermanagh","Galway","Kerry","Kildare","Kilkenny","Laois","Leitrim",
         "Limerick","Longford","Louth","Mayo","Meath","Monaghan","Offaly","Roscommon",
         "Sligo","Tipperary","Tyrone","Waterford","Westmeath","Wexford","Wicklow"}

gpf_county_grounds = [r for r in gpf if r["County"] in ALL32 and r["Club"].strip() == f"{r['County']} GAA"]

cg_rows = list(csv.DictReader(open(p("county_grounds.csv"))))

# ---- pair each GPF row to its nearest same-county CSV row ----
report_lines = []
report_lines.append(f"# GPF reconciliation\n")
report_lines.append(f"Source: gaapitchfinder_data.csv @ commit `{GPF_COMMIT}`, CC BY 4.0.\n")
report_lines.append(f"Club and pitch location data from GAA Pitch Finder by Ryan McGuinness: "
                     f"https://gaapitchfinder.com\n")
report_lines.append(f"\n{len(gpf_county_grounds)} GPF rows match the `<County> GAA` pattern "
                     f"(island scope, `File=='Ireland'`).\n")

from collections import defaultdict
by_county = defaultdict(list)
for r in gpf_county_grounds:
    by_county[r["County"]].append(r)

report_lines.append("\n## Per-county match table\n")
report_lines.append("| County | GPF ground(s) | CSV county_main | Distance | Notes |\n")
report_lines.append("|---|---|---|---|---|\n")

updates = []  # (name, county, new_bearing, new_source, new_dist, new_n, new_lat, new_lon, old_bearing)
multi_county = []

for county in sorted(by_county):
    gpf_grounds = by_county[county]
    csv_rows = [r for r in cg_rows if r["county"] == county]
    csv_main = next((r for r in csv_rows if r["role"] == "county_main"), None)

    if len(gpf_grounds) > 1:
        multi_county.append((county, [g["Pitch"] for g in gpf_grounds]))

    for g in gpf_grounds:
        glat, glon = float(g["Latitude"]), float(g["Longitude"])
        # pair to nearest CSV row in the same county (any role)
        if csv_rows:
            scored = sorted(csv_rows, key=lambda c: dist_m(glat, glon, float(c["lat"]), float(c["lon"])))
            nearest = scored[0]
            d = dist_m(glat, glon, float(nearest["lat"]), float(nearest["lon"]))
        else:
            nearest, d = None, None

        is_main = nearest is csv_main
        notes = []
        if not nearest:
            notes.append("NO CSV ROW FOR COUNTY")
        elif d > MOVE_THRESHOLD_M:
            key = (nearest["name"], nearest["county"])
            if key in VERIFIED:
                notes.append(f">{MOVE_THRESHOLD_M}m but satellite-verified -- not re-matched")
            else:
                way_id = WAY_IDS.get(key)
                new_bearing, new_source, new_dist, new_n, new_lat, new_lon = run_match(glat, glon, way_id)
                old_bearing = nearest["pitch_bearing"]
                changed = new_bearing != "" and str(new_bearing) != str(old_bearing)
                if new_source != "needs_manual":
                    notes.append(f"re-matched via GPF coord: {new_source}, bearing "
                                 f"{old_bearing or '(none)'} -> {new_bearing}"
                                 f"{' (changed)' if changed else ' (unchanged)'}")
                    updates.append((nearest["name"], nearest["county"], new_bearing, new_source,
                                    new_dist, new_n, new_lat, new_lon, old_bearing))
                else:
                    notes.append(f"re-matched via GPF coord: still needs_manual "
                                 f"(n_candidates={new_n})")
        dtxt = f"{d:.0f}m" if d is not None else "--"
        report_lines.append(f"| {county} | {g['Pitch']}{' *' if not is_main else ''} | "
                            f"{nearest['name'] if nearest else '(none)'} | {dtxt} | "
                            f"{'; '.join(notes) if notes else 'OK'} |\n")

report_lines.append("\n`*` = this GPF row's nearest CSV match is not that county's `county_main`.\n")

report_lines.append("\n## Counties with more than one `<County> GAA` row in GPF\n")
for county, pitches in multi_county:
    report_lines.append(f"- **{county}**: {', '.join(pitches)}\n")

report_lines.append("\n## Known mismatches worth flagging\n")
report_lines.append("- **Dublin**: GPF ties `Dublin GAA` to both Parnell Park and Croke Park. "
                     "Per your instruction, Croke Park stays `role=national`, Parnell Park is "
                     "`county_main` -- not double-counted as two Dublin county grounds.\n")
report_lines.append("- **Donegal**: GPF lists three `Donegal GAA` grounds (MacCumhaill Park, "
                     "O'Donnell Park, Fr Tierney Park); county_grounds.csv now carries all three "
                     "(main + two seconds), matching GPF.\n")
report_lines.append("- **Antrim**: GPF ties `Antrim GAA` to Casement Park, matching your "
                     "principal-venue rule (Casement = county_main despite closure since 2013).\n")
report_lines.append("- **Louth**: GPF still lists the old Drogheda Gaelic Grounds as "
                     "`Louth GAA`'s ground -- no sign of the Dundalk move in GPF's data either, "
                     "consistent with your \"home until 2020, new stadium not yet open\" framing.\n")

with open(p("gpf_reconciliation.md"), "w") as f:
    f.writelines(report_lines)

# ---- apply updates to county_grounds.csv ----
if updates:
    by_key = {(u[0], u[1]): u for u in updates}
    for r in cg_rows:
        key = (r["name"], r["county"])
        if key in by_key:
            _, _, bearing, source, dist, n, lat, lon, _ = by_key[key]
            r["pitch_bearing"] = bearing
            r["bearing_source"] = source
            r["match_dist_m"] = dist
            r["n_candidates"] = n
            r["lat"] = round(lat, 6)
            r["lon"] = round(lon, 6)
    cols = list(cg_rows[0].keys())
    with open(p("county_grounds.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(cg_rows)

print(f"GPF county-ground rows (island scope): {len(gpf_county_grounds)}")
print(f"counties with >1 GPF row: {len(multi_county)}")
print(f"rows re-matched via GPF coordinate and updated: {len(updates)}")
for u in updates:
    print(f"  {u[0]} ({u[1]}): {u[8]} -> {u[2]} [{u[3]}]")
print(f"\nwrote gpf_reconciliation.md and updated county_grounds.csv")
