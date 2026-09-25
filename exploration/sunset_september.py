#!/usr/bin/env python3
"""
Pitch Compass -- September sunset check (relaunch step 2, item 5).
Reuses the project's existing sunset-azimuth method (analyse_extra.py:
sunset_azimuth(declination), latitude 53.4) and extends it with the
standard day-of-year solar-declination approximation, at the same
precision tier the rest of the project uses (no ephemeris library).
Stdlib only. Report-only script -- no data file output.
"""
import math, datetime

LAT = 53.4


def declination(date):
    n = date.timetuple().tm_yday
    return 23.44 * math.sin(math.radians(360.0 / 365.0 * (n - 81)))


def sunset_azimuth(declination_deg):
    d = math.radians(declination_deg)
    lat = math.radians(LAT)
    return 360 - math.degrees(math.acos(math.sin(d) / math.cos(lat)))


def axis_diff(a, b):
    d = abs(a - b) % 180
    return min(d, 180 - d)


dates = [datetime.date(2026, 9, 1), datetime.date(2026, 9, 15), datetime.date(2026, 9, 30)]

print(f"{'date':<12} {'declination':>11} {'sunset azimuth':>15} {'axis (0-180)':>13} {'|diff to 90|':>13} {'within 15deg of E-W?':>21}")
for d in dates:
    dec = declination(d)
    az = sunset_azimuth(dec) % 360
    axis = az % 180
    diff = axis_diff(axis, 90.0)
    within = "YES" if diff <= 15 else "no"
    print(f"{d.isoformat():<12} {dec:>10.2f}d {az:>14.1f}d {axis:>12.1f}d {diff:>12.1f}d {within:>21}")
