#!/usr/bin/env python3
"""
Pitch Compass — exploratory phase script.
"Every GAA pitch in Ireland, and which way it points."
Data (c) OpenStreetMap contributors, ODbL 1.0.

Stdlib only, no dependencies. Run:  python3 explore_gaa.py
Outputs into ./gaa_out/ :
  raw_overpass.json   full pull, kept for reproducibility
  pitches.csv         one row per way/relation with a computed bearing
  summary.json        counts, tag breakdowns, bearing histogram, signal stats
This script pulls and derives data only. Rendering is a separate step:
make_rose.py draws the compass rose from pitches.csv without re-pulling.
Also prints an ASCII rose + headline stats to stdout.

Method notes:
- Bearing = long axis of the minimum-area rotated rectangle (convex hull +
  rotating calipers), folded to [0, 180). 0 = N-S, 90 = E-W.
- QA fields: length_m, width_m, aspect, area_m2. Aspect near 1.0 means the
  orientation is ambiguous; full GAA pitches should be ~1.5-1.8 and
  ~6,000-15,000 m^2. Nothing is dropped — filter downstream.
- Signal test: circular statistics on DOUBLED angles (standard for axial
  data). R in [0,1]: 0 = uniform chaos, 1 = perfectly aligned.
"""

import json, math, csv, sys, time, urllib.request, urllib.parse
from pathlib import Path

OUT = Path("gaa_out"); OUT.mkdir(exist_ok=True)
MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
SPORT_RE = "gaelic_games|gaelic_football|hurling|camogie"
QUERY = f'[out:json][timeout:300];nwr["sport"~"{SPORT_RE}"];out tags geom;'
UA = "gaa-pitch-compass-exploration/0.1 (personal research)"


def overpass(query):
    data = urllib.parse.urlencode({"data": query}).encode()
    last_err = None
    for url in MIRRORS:
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=360) as r:
                    return json.load(r)
            except Exception as e:  # noqa: BLE001 — exploratory tool, retry everything
                last_err = e
                wait = 15 * (attempt + 1)
                print(f"  {url} failed ({e}); retry in {wait}s", file=sys.stderr)
                time.sleep(wait)
    raise SystemExit(f"All mirrors failed: {last_err}")


# ---------- geometry ----------

def project(points):
    """lat/lon -> local metres (equirectangular; fine at pitch scale)."""
    lat0 = sum(p[0] for p in points) / len(points)
    lon0 = sum(p[1] for p in points) / len(points)
    k = math.cos(math.radians(lat0))
    return [((lon - lon0) * k * 111320.0, (lat - lat0) * 110540.0) for lat, lon in points], (lat0, lon0)


def convex_hull(pts):
    pts = sorted(set(pts))
    if len(pts) <= 2:
        return pts
    def cross(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def min_area_rect(pts_xy):
    """Rotating calipers over hull edges. Returns (bearing_deg 0-180, length_m, width_m)."""
    hull = convex_hull(pts_xy)
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
        ux, uy = ex / elen, ey / elen          # edge direction
        vx, vy = -uy, ux                        # normal
        us = [px * ux + py * uy for px, py in hull]
        vs = [px * vx + py * vy for px, py in hull]
        du, dv = max(us) - min(us), max(vs) - min(vs)
        area = du * dv
        if best is None or area < best[0]:
            # long axis vector in ENU
            if du >= dv:
                ax, ay, length, width = ux, uy, du, dv
            else:
                ax, ay, length, width = vx, vy, dv, du
            bearing = math.degrees(math.atan2(ax, ay)) % 180.0
            best = (area, bearing, length, width)
    if best is None:
        return None
    _, bearing, length, width = best
    return bearing, length, width


def feature_points(el):
    """Extract (lat, lon) outline points from an Overpass element with geometry."""
    if el["type"] == "way" and "geometry" in el:
        return [(g["lat"], g["lon"]) for g in el["geometry"]]
    if el["type"] == "relation" and "members" in el:
        pts = []
        for m in el["members"]:
            if m.get("role") in ("outer", "") and "geometry" in m:
                pts += [(g["lat"], g["lon"]) for g in m["geometry"]]
        return pts
    return []


# ---------- signal stats (axial data: double the angles) ----------

def axial_stats(bearings):
    if not bearings:
        return {}
    s = sum(math.sin(math.radians(2 * b)) for b in bearings)
    c = sum(math.cos(math.radians(2 * b)) for b in bearings)
    n = len(bearings)
    R = math.hypot(s, c) / n
    mean = (math.degrees(math.atan2(s, c)) / 2.0) % 180.0
    # Rayleigh test p-value (large-sample approx)
    z = n * R * R
    p = math.exp(-z) * (1 + (2*z - z*z) / (4*n))
    return {"n": n, "mean_orientation_deg": round(mean, 1),
            "R": round(R, 4), "rayleigh_p": p}


def ascii_rose(bearings, bins=12):
    width = 40
    counts = [0] * bins
    for b in bearings:
        counts[int(b // (180 / bins)) % bins] += 1
    top = max(counts) or 1
    lines = []
    for i, cnt in enumerate(counts):
        lo, hi = i * 180 // bins, (i + 1) * 180 // bins
        bar = "#" * round(cnt / top * width)
        lines.append(f"{lo:3d}-{hi:3d}deg |{bar:<{width}}| {cnt}")
    return "\n".join(lines)


def main():
    print("Stage A/B: pulling all GAA-tagged elements (one query, ~seconds)...")
    data = overpass(QUERY)
    (OUT / "raw_overpass.json").write_text(json.dumps(data))
    els = data.get("elements", [])

    by_type = {}
    leisure_counts, sport_counts = {}, {}
    rows, bearings = [], []
    for el in els:
        by_type[el["type"]] = by_type.get(el["type"], 0) + 1
        tags = el.get("tags", {})
        leisure_counts[tags.get("leisure", "<none>")] = leisure_counts.get(tags.get("leisure", "<none>"), 0) + 1
        sport_counts[tags.get("sport", "<none>")] = sport_counts.get(tags.get("sport", "<none>"), 0) + 1
        if el["type"] == "node":
            continue
        pts = feature_points(el)
        if len(pts) < 3:
            continue
        xy, (lat0, lon0) = project(pts)
        rect = min_area_rect(xy)
        if rect is None:
            continue
        bearing, length, width = rect
        aspect = length / width if width > 0 else float("inf")
        rows.append({
            "osm_type": el["type"], "osm_id": el["id"],
            "lat": round(lat0, 6), "lon": round(lon0, 6),
            "bearing_deg": round(bearing, 1),
            "length_m": round(length, 1), "width_m": round(width, 1),
            "aspect": round(aspect, 2), "area_m2": round(length * width),
            "leisure": tags.get("leisure", ""), "sport": tags.get("sport", ""),
            "name": tags.get("name", ""),
        })
        # signal sample: pitch-like polygons only (unambiguous orientation, plausible size)
        if tags.get("leisure") == "pitch" and aspect >= 1.2 and 2000 <= length * width <= 20000:
            bearings.append(bearing)

    with (OUT / "pitches.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["empty"])
        w.writeheader(); w.writerows(rows)

    stats = axial_stats(bearings)
    hist = [0] * 12
    for b in bearings:
        hist[int(b // 15) % 12] += 1
    summary = {
        "project": "Pitch Compass",
        "attribution": "Data (c) OpenStreetMap contributors, ODbL 1.0 (openstreetmap.org/copyright)",
        "osm_data_timestamp": data.get("osm3s", {}).get("timestamp_osm_base", "unknown"),
        "pulled_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_elements": len(els), "by_type": by_type,
        "leisure_breakdown": leisure_counts, "sport_breakdown": sport_counts,
        "polygons_with_bearing": len(rows),
        "signal_sample_size (leisure=pitch, aspect>=1.2, 2k-20k m2)": len(bearings),
        "bearing_hist_15deg_bins": hist, "axial_stats": stats,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))

    print(f"\nTotal elements: {len(els)}  by type: {by_type}")
    print(f"Polygons with a bearing: {len(rows)}; signal sample: {len(bearings)}")
    print(f"leisure=* breakdown: {leisure_counts}")
    print(f"\nAxial stats (0=N-S, 90=E-W): {stats}")
    print("\n" + ascii_rose(bearings))

    print("\nDone. Draw the rose with: python3 make_rose.py  (reads gaa_out/pitches.csv, no re-pull)")
    print("Upload gaa_out/summary.json (and rose.png) back to the chat for analysis.")


if __name__ == "__main__":
    main()