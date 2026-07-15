#!/usr/bin/env python3
"""
Pitch Compass — draw a compass rose from a frozen dataset. No network.

Reads a pitches CSV produced by explore_gaa.py or soccer_control.py,
applies the standard signal filter (island of Ireland, aspect >= 1.2,
2,000-20,000 m2), and writes a mirrored axial rose PNG alongside it.

Usage (from exploration/):
  python3 make_rose.py                                    # GAA default
  python3 make_rose.py gaa_out/pitches.csv "GAA pitches"
  python3 make_rose.py soccer_out/soccer_pitches.csv "Soccer pitches (control)"

Data (c) OpenStreetMap contributors, ODbL 1.0.
"""
import csv, math, sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("gaa_out/pitches.csv")
label = sys.argv[2] if len(sys.argv) > 2 else "GAA pitches"
out_path = csv_path.parent / "rose.png"

rows = csv.DictReader(open(csv_path))
bearings = []
for r in rows:
    try:
        lat, lon = float(r["lat"]), float(r["lon"])
        aspect, area, b = float(r["aspect"]), float(r["area_m2"]), float(r["bearing_deg"])
    except (ValueError, KeyError):
        continue
    # soccer CSV has no leisure column (pitch-only pull); GAA CSV does
    if r.get("leisure", "pitch") != "pitch":
        continue
    if (aspect >= 1.2 and 2000 <= area <= 20000
            and 51.3 <= lat <= 55.5 and -11.0 <= lon <= -5.3):
        bearings.append(b)

print(f"Ireland signal sample: {len(bearings)} pitches from {csv_path}")
theta = [math.radians(b) for b in bearings] + [math.radians(b + 180) for b in bearings]
ax = plt.subplot(projection="polar")
ax.set_theta_zero_location("N")
ax.set_theta_direction(-1)
ax.hist(theta, bins=48)
ax.set_title(f"{label}, island of Ireland (n={len(bearings)})\n"
             "mirrored axial rose — Data (c) OpenStreetMap contributors")
plt.savefig(out_path, dpi=150, bbox_inches="tight")
print(f"Wrote {out_path}")