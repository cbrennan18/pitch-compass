#!/usr/bin/env python3
"""
Pitch Compass — soccer control pull.
Irish soccer pitches through the identical bearing pipeline, to test whether
the cardinal/grid alignment found in GAA pitches is GAA lore or just Irish land.
Data (c) OpenStreetMap contributors, ODbL 1.0.

Run:  python3 soccer_control.py     Outputs to ./soccer_out/
Note: this query is area-scoped to the island (Republic + NI), unlike the
global GAA pull — sport=soccer worldwide would be millions of elements.
"""

import json, math, csv, sys, time, urllib.request, urllib.parse
from pathlib import Path

OUT = Path("soccer_out"); OUT.mkdir(exist_ok=True)
MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
QUERY = """[out:json][timeout:600];
area["ISO3166-1"="IE"][admin_level=2]->.roi;
area["ISO3166-2"="GB-NIR"]->.ni;
(
  way["leisure"="pitch"]["sport"~"soccer"](area.roi);
  way["leisure"="pitch"]["sport"~"soccer"](area.ni);
);
out tags geom;"""
UA = "pitch-compass-soccer-control/0.1 (personal research)"
GAA_WORDS = ("gaelic", "hurling", "camogie", "gaa")


def overpass(query):
    data = urllib.parse.urlencode({"data": query}).encode()
    last_err = None
    for url in MIRRORS:
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=660) as r:
                    return json.load(r)
            except Exception as e:  # noqa: BLE001
                last_err = e
                wait = 20 * (attempt + 1)
                print(f"  {url} failed ({e}); retry in {wait}s", file=sys.stderr)
                time.sleep(wait)
    raise SystemExit(f"All mirrors failed: {last_err}")


def project(points):
    lat0 = sum(p[0] for p in points)/len(points)
    lon0 = sum(p[1] for p in points)/len(points)
    k = math.cos(math.radians(lat0))
    return [((lon-lon0)*k*111320.0, (lat-lat0)*110540.0) for lat, lon in points], (lat0, lon0)


def convex_hull(pts):
    pts = sorted(set(pts))
    if len(pts) <= 2: return pts
    def cross(o,a,b): return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    lo, up = [], []
    for p in pts:
        while len(lo)>=2 and cross(lo[-2],lo[-1],p)<=0: lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up)>=2 and cross(up[-2],up[-1],p)<=0: up.pop()
        up.append(p)
    return lo[:-1]+up[:-1]


def min_area_rect(xy):
    hull = convex_hull(xy)
    if len(hull) < 3: return None
    best = None
    n = len(hull)
    for i in range(n):
        x1,y1 = hull[i]; x2,y2 = hull[(i+1)%n]
        ex,ey = x2-x1, y2-y1
        el = math.hypot(ex,ey)
        if el == 0: continue
        ux,uy = ex/el, ey/el; vx,vy = -uy,ux
        us = [px*ux+py*uy for px,py in hull]; vs = [px*vx+py*vy for px,py in hull]
        du,dv = max(us)-min(us), max(vs)-min(vs)
        if best is None or du*dv < best[0]:
            if du >= dv: ax,ay,L,W = ux,uy,du,dv
            else:        ax,ay,L,W = vx,vy,dv,du
            best = (du*dv, math.degrees(math.atan2(ax,ay))%180.0, L, W)
    return best[1:] if best else None


def rayleigh(bs, mult):
    n = len(bs)
    if n == 0: return None
    s = sum(math.sin(math.radians(mult*b)) for b in bs)
    c = sum(math.cos(math.radians(mult*b)) for b in bs)
    R = math.hypot(s,c)/n
    mean = (math.degrees(math.atan2(s,c))/mult) % (360/mult)
    z = n*R*R
    p = math.exp(-z)*(1+(2*z-z*z)/(4*n))
    return dict(n=n, R=round(R,4), mean_deg=round(mean,1), p=p)


def cardinal_pct(bs):
    if not bs: return 0
    return round(100*sum(1 for b in bs if min(b%90, 90-(b%90)) <= 15)/len(bs), 1)


CITIES = [(53.3498,-6.2603),(51.8985,-8.4756),(53.2707,-9.0568),(52.6638,-8.6267),(54.5973,-5.9301)]
def near_city(lat, lon, km=20):
    for cla, clo in CITIES:
        dx = (lon-clo)*math.cos(math.radians(cla))*111.32; dy = (lat-cla)*110.54
        if math.hypot(dx,dy) <= km: return True
    return False


def main():
    print("Pulling Irish soccer pitches (may take a minute or two)...")
    data = overpass(QUERY)
    (OUT/"raw_overpass.json").write_text(json.dumps(data))
    els = [e for e in data.get("elements", []) if e.get("type")=="way" and "geometry" in e]
    print(f"ways with geometry: {len(els)}")

    rows, bearings, urb_b, rur_b = [], [], [], []
    for el in els:
        tags = el.get("tags", {})
        sport = tags.get("sport","").lower()
        if any(w in sport for w in GAA_WORDS):
            continue  # keep the control clean: pure soccer / soccer+non-GAA only
        pts = [(g["lat"], g["lon"]) for g in el["geometry"]]
        if len(pts) < 3: continue
        xy, (lat0, lon0) = project(pts)
        rect = min_area_rect(xy)
        if rect is None: continue
        b, L, W = rect
        aspect = L/W if W>0 else float("inf")
        area = L*W
        rows.append(dict(osm_id=el["id"], lat=round(lat0,6), lon=round(lon0,6),
                         bearing_deg=round(b,1), length_m=round(L,1), width_m=round(W,1),
                         aspect=round(aspect,2), area_m2=round(area), sport=tags.get("sport",""),
                         name=tags.get("name","")))
        # comparable signal filter: full-size-ish, unambiguous orientation
        if aspect >= 1.2 and 2000 <= area <= 20000:
            bearings.append(b)
            (urb_b if near_city(lat0, lon0) else rur_b).append(b)

    with (OUT/"soccer_pitches.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["empty"])
        w.writeheader(); w.writerows(rows)

    summary = {
        "project": "Pitch Compass (soccer control)",
        "attribution": "Data (c) OpenStreetMap contributors, ODbL 1.0 (openstreetmap.org/copyright)",
        "osm_data_timestamp": data.get("osm3s", {}).get("timestamp_osm_base", "unknown"),
        "pulled_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ways_total": len(els), "rows_with_bearing": len(rows),
        "signal_sample": len(bearings),
        "axial_2t": rayleigh(bearings, 2),
        "cardinal_4t": rayleigh(bearings, 4),
        "pct_within_15deg_of_cardinal": cardinal_pct(bearings),
        "urban_4t": rayleigh(urb_b, 4), "urban_cardinal_pct": cardinal_pct(urb_b),
        "rural_4t": rayleigh(rur_b, 4), "rural_cardinal_pct": cardinal_pct(rur_b),
    }
    (OUT/"summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    print("\nDone. Upload soccer_out/summary.json back to the chat.")


if __name__ == "__main__":
    main()