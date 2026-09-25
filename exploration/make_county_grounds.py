#!/usr/bin/env python3
"""
Pitch Compass -- county_grounds.csv (relaunch step 2, item 1).
Base list: Wikipedia's "List of Gaelic Athletic Association stadiums" +
the 32 county main grounds + Croke Park (~44 rows incl. ambiguous seconds).
Coordinates/capacity/lore sourced from Wikipedia (paraphrased, cited by
URL) via WebFetch/WebSearch during this session -- see GROUNDS below,
each row carries its own lore_url.

Bearing comes from the PLAYING-SURFACE polygon, not the stadium outline:
  1. If the stadium's own outline polygon is available (frozen
     gaa_out/raw_overpass.json, leisure=stadium way with ring geometry),
     prefer a leisure=pitch polygon whose centroid falls INSIDE it.
  2. Otherwise, candidates are pitches.csv rows within 150 m of the
     ground's reference point with length_m >= 130; the largest by area
     is picked.
  3. More than one plausible candidate (either test) -> needs_manual.
  4. No candidate at all -> needs_manual, bearing left blank.
match_dist_m and n_candidates are recorded for every row either way.

Stdlib only. Reads exploration/gaa_out/{raw_overpass.json,pitches.csv,
county_map.csv}. Writes exploration/county_grounds.csv. Does not touch
docs/index.html, docs/js/, or exploration/'s existing frozen outputs.
"""
import json, csv, math, os

HERE = os.path.dirname(os.path.abspath(__file__))


def p(*parts):
    return os.path.join(HERE, *parts)


LAT0 = 53.4


def dist_m(lat1, lon1, lat2, lon2):
    dx = (lon2 - lon1) * math.cos(math.radians(LAT0)) * 111320
    dy = (lat2 - lat1) * 110540
    return math.hypot(dx, dy)


def point_in_ring(lon, lat, ring):
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        if (y1 > lat) != (y2 > lat):
            x_cross = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
            if x_cross > lon:
                inside = not inside
    return inside


# ---- load frozen data ----
raw_els = json.load(open(p("gaa_out", "raw_overpass.json")))["elements"]
ways_by_id = {e["id"]: e for e in raw_els if e["type"] == "way"}
pitch_rows = list(csv.DictReader(open(p("gaa_out", "pitches.csv"))))
county_map = {r["osm_id"]: r["county"] for r in csv.DictReader(open(p("gaa_out", "county_map.csv")))}


def outline_ring(way_id):
    """Return [(lon,lat), ...] for a way's geometry, or None if unavailable."""
    e = ways_by_id.get(way_id)
    if not e or "geometry" not in e:
        return None
    return [(g["lon"], g["lat"]) for g in e["geometry"]]


# ---- the 44-row base list ----
# (name, county, role, capacity, lore, lore_url, ref_lat, ref_lon, stadium_way_id)
# role: county_main | county_second | national
GROUNDS = [
 ("Croke Park","Dublin","national",82300,
  "Named after Archbishop Thomas Croke, an early GAA patron; the GAA's headquarters and national stadium since 1913.",
  "https://en.wikipedia.org/wiki/Croke_Park", 53.359879,-6.250778, 564099741),
 ("Semple Stadium","Tipperary","county_main",45690,
  "Named after Tom Semple, captain of the Thurles Blues hurling team in the early 1900s.",
  "https://en.wikipedia.org/wiki/Semple_Stadium", 52.682323,-7.825914, 153101670),
 ("Pairc Ui Chaoimh","Cork","county_main",45000,
  "Named after Pádraig Ó Caoimh, GAA Director-General 1929-1964; rebuilt and reopened in 2017.",
  "https://en.wikipedia.org/wiki/P%C3%A1irc_U%C3%AD_Chaoimh", 51.89972,-8.43519, None),
 ("Gaelic Grounds","Limerick","county_main",44023,
  "Limerick GAA's home ground since 1918, on the banks of the Shannon.",
  "https://en.wikipedia.org/wiki/Gaelic_Grounds", 52.669851,-8.654428, 288780384),
 ("Fitzgerald Stadium","Kerry","county_main",38000,
  "Named after Dick Fitzgerald, Kerry captain and one of the game's first tactical writers.",
  "https://en.wikipedia.org/wiki/Fitzgerald_Stadium", 52.06631,-9.50879, None),
 ("St Tiernach's Park","Monaghan","county_main",29000,
  "Named after Saint Tiarnach, patron saint of Clones; regular host of Ulster finals.",
  "https://en.wikipedia.org/wiki/St_Tiernach%27s_Park", 54.185427,-7.23328, 1006440355),
 ("MacHale Park","Mayo","county_main",27870,
  "Named after Archbishop John MacHale of Tuam, a 19th-century Irish-language advocate.",
  "https://en.wikipedia.org/wiki/MacHale_Park", 53.853697,-9.286459, 237148419),
 ("Nowlan Park","Kilkenny","county_main",27000,
  "Named after James Nowlan, GAA president 1901-1921, a Kilkenny man.",
  "https://en.wikipedia.org/wiki/Nowlan_Park", 52.656522,-7.239953, 153999465),
 ("Pearse Stadium","Galway","county_main",26197,
  "Named after Pádraig Pearse, executed leader of the 1916 Easter Rising.",
  "https://en.wikipedia.org/wiki/Pearse_Stadium", 53.263415,-9.084548, 131056992),
 ("Breffni Park","Cavan","county_main",25030,
  "Named after the historic Kingdom of Breifne, which covered Cavan and Leitrim.",
  "https://en.wikipedia.org/wiki/Breffni_Park", 53.981823,-7.360472, 182944834),
 ("Dr Hyde Park","Roscommon","county_main",23900,
  "Named after Douglas Hyde, first President of Ireland and a founder of the Gaelic League.",
  "https://en.wikipedia.org/wiki/Dr_Hyde_Park", 53.625179,-8.182334, None),
 ("O'Moore Park","Laois","county_main",22000,
  "Named after Rory O'Moore, 17th-century leader of the Irish Confederate Wars.",
  "https://en.wikipedia.org/wiki/O%27Moore_Park", 53.02619,-7.302448, 83939606),
 ("Cusack Park","Clare","county_main",20800,
  "Named after Michael Cusack, a founder of the GAA in 1884; also known in Irish as Páirc Uí Chíosóg.",
  "https://en.wikipedia.org/wiki/Cusack_Park_(Ennis)", 52.846314,-8.978661, None),
 ("Pairc Esler","Down","county_main",20000,
  "Named after John Esler, a Down GAA official; shared with Newry Shamrocks GAC.",
  "https://en.wikipedia.org/wiki/P%C3%A1irc_Esler", 54.163192,-6.334212, 113523274),
 ("Markievicz Park","Sligo","county_main",18558,
  "Named after Constance Markievicz, 1916 Rising participant and first woman elected to Dáil Éireann; built in 1955.",
  "https://en.wikipedia.org/wiki/Markievicz_Park", 54.257531,-8.464456, None),
 ("Celtic Park","Derry","county_main",18500,
  "Also known as Páirc na gCeilteach; Derry GAA's home ground in the city.",
  "https://en.wikipedia.org/wiki/Celtic_Park_(Derry)", 54.993019,-7.333442, 656475469),
 ("Athletic Grounds","Armagh","county_main",18500,
  "A multi-sport venue in Armagh city used by Armagh GAA since the early 20th century.",
  "https://en.wikipedia.org/wiki/Athletic_Grounds_(Armagh)", 54.343846,-6.662464, 575037774),
 ("Wexford Park","Wexford","county_main",18000,
  "Wexford GAA's home ground since 1904, in Wexford town.",
  "https://en.wikipedia.org/wiki/Wexford_Park", 52.33248,-6.47592, None),
 ("Brewster Park","Fermanagh","county_main",18000,
  "Fermanagh GAA's home ground in Enniskillen.",
  "https://en.wikipedia.org/wiki/Brewster_Park", 54.35108,-7.635159, None),
 ("O'Connor Park","Offaly","county_main",18000,
  "Named after Dinny O'Connor, a local GAA benefactor; in Tullamore.",
  "https://en.wikipedia.org/wiki/O%27Connor_Park", 53.280422,-7.489628, 57978618),
 ("Healy Park","Tyrone","county_main",17636,
  "Named after Bishop Eugene O'Doherty's predecessor John Healy; in Omagh.",
  "https://en.wikipedia.org/wiki/Healy_Park", 54.614192,-7.297601, 428490897),
 ("MacCumhaill Park","Donegal","county_main",17500,
  "Named after Fionn mac Cumhaill of Irish mythology; home of the Seán MacCumhaills club, in Ballybofey.",
  "https://en.wikipedia.org/wiki/MacCumhaill_Park", 54.801025,-7.778439, None),
 ("Pairc Ui Rinn","Cork","county_second",16440,
  "Named after Christy Ring, widely regarded as one of hurling's greatest players.",
  "https://en.wikipedia.org/wiki/P%C3%A1irc_U%C3%AD_Rinn", 51.891638,-8.436185, 80457142),
 ("Fraher Field","Waterford","county_second",15000,
  "Named after Pat Fraher, a Waterford GAA administrator; in Dungarvan.",
  "https://en.wikipedia.org/wiki/Fraher_Field", 52.09673,-7.62448, 71801722),
 ("St Conleth's Park","Kildare","county_main",15000,
  "Named after Saint Conleth, patron saint of Kildare; in Newbridge.",
  "https://en.wikipedia.org/wiki/St_Conleth%27s_Park", 53.179804,-6.794725, 105320174),
 ("St Mary's Park","Monaghan","county_second",14000,
  "Home ground of Castleblayney Faughs GFC.",
  "https://en.wikipedia.org/wiki/Castleblayney_Faughs_GFC", 54.112767,-6.730603, None),
 ("Austin Stack Park","Kerry","county_second",14000,
  "Named after Austin Stack, a 1916 Rising participant and Kerry footballer; in Tralee.",
  "https://en.wikipedia.org/wiki/Austin_Stack_Park", 52.269736,-9.693156, 157914146),
 ("Cusack Park","Westmeath","county_main",11500,
  "Named after Michael Cusack, a founder of the GAA; in Mullingar.",
  "https://en.wikipedia.org/wiki/TEG_Cusack_Park", 53.528,-7.337829, 411793025),
 ("Dr Cullen Park","Carlow","county_main",11000,
  "Named after Cardinal Paul Cullen, 19th-century Archbishop of Dublin.",
  "https://en.wikipedia.org/wiki/Dr_Cullen_Park", 52.846879,-6.917007, 90185033),
 ("Walsh Park","Waterford","county_main",11046,
  "Named after Bishop Daniel Cohalan's contemporary; in Waterford city.",
  "https://en.wikipedia.org/wiki/Walsh_Park", 52.254606,-7.128461, 39236986),
 ("Pairc Tailteann","Meath","county_main",11000,
  "Named after the ancient Tailteann Games, said to be held nearby; in Navan.",
  "https://en.wikipedia.org/wiki/P%C3%A1irc_Tailteann", 53.649812,-6.693506, 88740945),
 ("Pairc Sean Mac Diarmada","Leitrim","county_main",9331,
  "Named after Seán Mac Diarmada, a 1916 Rising signatory born in Leitrim.",
  "https://en.wikipedia.org/wiki/P%C3%A1irc_Se%C3%A1n_Mac_Diarmada", 53.947839,-8.076056, 641097746),
 ("Fr Tierney Park","Donegal","county_second",9000,
  "Home of Aodh Ruadh CLG in Ballyshannon.",
  "https://en.wikipedia.org/wiki/Aodh_Ruadh_CLG", 54.497863,-8.191321, None),
 ("St Brendan's Park","Offaly","county_second",8800,
  "Named after Saint Brendan the Navigator; in Birr.",
  "https://en.wikipedia.org/wiki/St_Brendan%27s_Park", 53.09171,-7.908917, 58463378),
 ("Parnell Park","Dublin","county_main",8500,
  "Named after Charles Stewart Parnell, 19th-century Irish nationalist leader; in Donnycarney.",
  "https://en.wikipedia.org/wiki/Parnell_Park", 53.372914,-6.216322, 562581062),
 ("Aughrim County Ground","Wicklow","county_main",7000,
  "Wicklow GAA's home ground on Rednagh Road, Aughrim.",
  "https://en.wikipedia.org/wiki/Aughrim_County_Ground", 52.852661,-6.335358, None),
 ("O'Garney Park","Clare","county_second",7000,
  "Named after the River O'Garney; home of Sixmilebridge GAA club.",
  "https://en.wikipedia.org/wiki/O%27Garney_Park", 52.744719,-8.777783, None),
 ("St Jarlath's Park","Galway","county_second",6700,
  "Named after Saint Jarlath, patron saint of Tuam.",
  "https://en.wikipedia.org/wiki/St_Jarlath%27s_Park", 53.509261,-8.853827, 278221733),
 ("Pearse Park","Longford","county_main",6000,
  "Named after Pádraig Pearse, executed leader of the 1916 Easter Rising.",
  "https://en.wikipedia.org/wiki/Pearse_Park_(Longford)", 53.739326,-7.804909, None),
 ("McKenna Park","Down","county_second",5000,
  "Home ground of St Joseph's Ballycran GAA club.",
  "https://en.wikipedia.org/wiki/McKenna_Park", 54.477497,-5.507483, None),
 ("Pearse Park","Wicklow","county_second",5000,
  "Named after Pádraig Pearse; home of Arklow Geraldines Ballymoney GAA, in Arklow.",
  "https://en.wikipedia.org/wiki/Pearse_Park_(Arklow)", 52.801246,-6.169561, None),
 ("Corrigan Park","Antrim","county_second",3700,
  "Named after John Corrigan (1881-1916), Antrim County Board secretary; in Belfast.",
  "https://en.wikipedia.org/wiki/Corrigan_Park", 54.59237,-5.97736, None),
 ("Casement Park","Antrim","county_main",34578,
  "Named after Roger Casement, executed 1916 figure; traditional Antrim GAA headquarters, closed for "
  "redevelopment since 2013 (capacity is the planned post-redevelopment figure, not a current one).",
  "https://en.wikipedia.org/wiki/Casement_Park", 54.573583,-5.983539, 148543725),
 ("Gaelic Grounds","Louth","county_main",3500,
  "Louth GAA's home ground 1926-2020, in Drogheda; currently under redevelopment. A new stadium "
  "(\"Staid Lu\", 14,000 capacity) is under construction in Dundalk -- a different site -- and not "
  "yet open, so this row's bearing describes a ground the county is in the process of leaving.",
  "https://en.wikipedia.org/wiki/Gaelic_Grounds_(Drogheda)", 53.72361,-6.35944, None),
 ("O'Donnell Park","Donegal","county_second",8200,
  "Named for Cardinal Patrick O'Donnell (1856-1927); home of St Eunan's GAA club, in Letterkenny.",
  "https://en.wikipedia.org/wiki/O%27Donnell_Park", 54.945423,-7.752413, None),
]

ROLE_NOTES = {
    ("Casement Park", "Antrim"): "closed since 2013",
    ("Gaelic Grounds", "Louth"): "Louth's home until 2020; new Dundalk stadium not yet open",
}

# human picks from design/verify.md (satellite-verified), applied as direct
# overrides -- these bypass the automatic inside-boundary/150m match below.
# Pairc Esler is deliberately NOT here: verify.md's pick was overridden back
# to "neither" and is re-matched against GPF's own coordinate instead (see
# reconcile_gpf.py).
MANUAL_OVERRIDES = {
    ("Healy Park", "Tyrone"): (54.614019, -7.297323, 165.3, 26.6),
    ("MacCumhaill Park", "Donegal"): (54.801342, -7.779774, 168.9, 95.3),
    ("St Mary's Park", "Monaghan"): (54.1129, -6.731229, 157.3, 44.1),
    ("Fr Tierney Park", "Donegal"): (54.498037, -8.191038, 88.4, 26.9),
    ("Aughrim County Ground", "Wicklow"): (52.85264, -6.335284, 58.4, 5.4),
    ("Pearse Park", "Wicklow"): (52.801251, -6.169363, 111.7, 13.2),
    ("Gaelic Grounds", "Louth"): (53.723656, -6.359451, 97.3, 5.1),
}

# ---- spatial bucketing of pitches.csv for the 150m-radius fallback ----
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


def inside_boundary_candidates(way_id, exclude_id):
    ring = outline_ring(way_id)
    if ring is None:
        return None  # no polygon available
    hits = []
    for r in pitch_rows:
        if int(r["osm_id"]) == way_id or (exclude_id and int(r["osm_id"]) == exclude_id):
            continue
        if r["leisure"] not in ("pitch", "sports_centre"):
            continue
        if point_in_ring(float(r["lon"]), float(r["lat"]), ring):
            hits.append(r)
    return hits


out_rows = []
for name, county, role, cap, lore, lore_url, rlat, rlon, way_id in GROUNDS:
    bearing = ""
    bearing_source = "needs_manual"
    match_dist_m = ""
    n_candidates = 0
    plat, plon = rlat, rlon  # fall back to the ground's own reference point

    override = MANUAL_OVERRIDES.get((name, county))
    if override:
        plat, plon, bearing, match_dist_m = override
        bearing_source = "verified_satellite"
        n_candidates = 1
    else:
        inside = inside_boundary_candidates(way_id, None) if way_id else None
        if inside:
            n_candidates = len(inside)
            if len(inside) == 1:
                r = inside[0]
                bearing = r["bearing_deg"]
                bearing_source = "matched_inside_boundary"
                match_dist_m = round(dist_m(rlat, rlon, float(r["lat"]), float(r["lon"])), 1)
                plat, plon = float(r["lat"]), float(r["lon"])
            # >1 inside candidate: leave needs_manual, n_candidates already set
        else:
            cands = nearby_candidates(rlat, rlon, 150)
            plausible = [(d, r) for d, r in cands if float(r["length_m"]) >= 130]
            n_candidates = len(plausible)
            if len(plausible) == 1:
                d, r = plausible[0]
                bearing = r["bearing_deg"]
                bearing_source = "matched_150m_radius"
                match_dist_m = round(d, 1)
                plat, plon = float(r["lat"]), float(r["lon"])
            elif len(plausible) > 1:
                # pick the largest by area for informational lat/lon, but still needs_manual
                d, r = max(plausible, key=lambda dr: float(dr[1]["length_m"]) * float(dr[1]["width_m"]))
                match_dist_m = round(d, 1)

    out_rows.append({
        "name": name, "county": county, "role": role,
        "role_note": ROLE_NOTES.get((name, county), ""),
        "lat": round(plat, 6), "lon": round(plon, 6),
        "pitch_bearing": bearing, "bearing_source": bearing_source,
        "match_dist_m": match_dist_m, "n_candidates": n_candidates,
        "capacity": cap, "lore": lore, "lore_url": lore_url,
    })

cols = ["name", "county", "role", "role_note", "lat", "lon", "pitch_bearing", "bearing_source",
        "match_dist_m", "n_candidates", "capacity", "lore", "lore_url"]
with open(p("county_grounds.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(out_rows)

# ---- report ----
verified = [r for r in out_rows if r["bearing_source"] != "needs_manual"]
needs_manual = [r for r in out_rows if r["bearing_source"] == "needs_manual"]


def axis_diff(a, b):
    d = abs(a - b) % 180
    return min(d, 180 - d)


ew = sum(1 for r in verified if axis_diff(float(r["pitch_bearing"]), 90) <= 30)
ns = sum(1 for r in verified if axis_diff(float(r["pitch_bearing"]), 0) <= 30)
diag = len(verified) - ew - ns

print(f"county_grounds.csv: {len(out_rows)} rows written")
print(f"verified (bearing matched): {len(verified)} / needs_manual: {len(needs_manual)}")
print(f"\nE-W (within 30 deg of 90):  {ew} ({ew/len(verified)*100:.1f}%)")
print(f"N-S (within 30 deg of 0):   {ns} ({ns/len(verified)*100:.1f}%)")
print(f"diagonal (neither):        {diag} ({diag/len(verified)*100:.1f}%)")
print(f"\nneeds_manual rows:")
for r in needs_manual:
    print(f"  {r['name']} ({r['county']}, {r['role']}) -- n_candidates={r['n_candidates']} match_dist_m={r['match_dist_m']}")
