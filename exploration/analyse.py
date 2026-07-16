# analyse.py — second-round exploration for Pitch Compass
# Reads the frozen dataset (gaa_out/pitches.csv), no network.
# Data (c) OpenStreetMap contributors, ODbL 1.0.

import csv
import math

# ---------------------------------------------------------------
# THE SIGNAL FILTER
# Which shapes count as real Irish pitches with a meaningful
# orientation? Everything downstream stands on this definition.
# ---------------------------------------------------------------

rows = []

def is_signal(row):
    if row["leisure"] != "pitch":
        return False
    if float(row["aspect"]) < 1.2:
        return False
    if not (2000 <= float(row["area_m2"]) <= 20000):
        return False
    if not (51.3 <= float(row["lat"]) <= 55.5):
        return False
    if not (-11.0 <= float(row["lon"]) <=-5.3):
        return False
    return True

# ---------------------------------------------------------------
# SHARED ANGLE TOOLS
# Pitch orientations are axes (0-180), not directions (0-360):
# play runs both ways, so 175 degrees and 355 degrees are the same line.
# ---------------------------------------------------------------

def axis_diff(a, b):
    d = abs(a - b) % 180
    return min(d, 180 - d)

# ---------------------------------------------------------------
# QUESTION 1: SUNSET
# Folklore says pitches avoid the setting sun. The sun sets NW in
# June, due W at equinox, SW in winter - so each season defines an
# axis, and we count pitches aligned within 15 degrees of it.
# Key comparison: June vs winter. Both axes are equally diagonal,
# so the grid effect hits both alike - any June-winter gap is the
# folklore's genuine fingerprint.
# ---------------------------------------------------------------

def sunset_azimuth(declination_deg):
    d = math.radians(declination_deg)
    lat = math.radians(53.4)
    return 360 - math.degrees(math.acos(math.sin(d) / math.cos(lat)))

def count_near_axis (rows, axis, tolerence=15):
    count = 0
    for row in rows:
        bearing = float(row["bearing_deg"])
        if axis_diff(bearing, axis) <= tolerence:
            count += 1
    return count


# ---------------------------------------------------------------
# LOAD + FILTER
# ---------------------------------------------------------------

with open("gaa_out/pitches.csv") as f:
    for row in csv.DictReader(f):
        if is_signal(row):
            rows.append(row)

print("signal sample:", len(rows))

# sunset counts by season (declination: +23.44 June, 0 equinox, -23.44 winter)
for name, decl in [("June", 23.44), ("Equinox", 0.0), ("Winter", -23.44)]:
    axis = sunset_azimuth(decl) % 180
    print(name, count_near_axis(rows, axis))

# ---------------------------------------------------------------
# QUESTION 2: TWIN PITCHES
# When a club has two pitches within 300m, does the second copy the
# first's orientation? Expect: heavy parallel + perpendicular, little between.
# ---------------------------------------------------------------

def dist_m(r1, r2):
    dx = (float(r1["lon"]) - float(r2["lon"])) * math.cos(math.radians(53.4)) * 111320
    dy = (float(r1["lat"]) - float(r2["lat"])) * 110540
    return math.hypot(dx, dy)

diffs = []
for i in range(len(rows)):
    for j in range(i + 1, len(rows)):
         if dist_m(rows[i], rows[j]) <= 300:
            b1 = float(rows[i]["bearing_deg"])
            b2 = float(rows[j]["bearing_deg"])
            diffs.append(axis_diff(b1, b2))

print("twin pitches:", len(diffs))

bins = [0, 0, 0, 0, 0, 0]
for d in diffs:
    slot = min(int(d // 15), 5)
    bins[slot] += 1

labels = ["0-15", "15-30", "30-45", "45-60", "60-75", "75-90"]
for label, count in zip(labels, bins):
    print(label, count, round(100 * count / len(diffs), 1))