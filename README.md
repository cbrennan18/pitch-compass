# Pitch Compass

**Every GAA pitch in Ireland, and which way it points.**

Ask anyone at a club and they'll tell you why the pitch faces the way it
does. It's angled so the goalkeeper isn't blinded by the setting sun. It
runs with the prevailing south-westerlies. It points true north, the way
the old crowd insisted. Everyone has heard a version of it; nobody had
ever checked. So we measured the orientation of every GAA pitch in
Ireland — 2,707 of them — to find out whether any of it is true.

## The short answer

None of it is. GAA pitches point every which way — there is no favoured
direction at all. There *is* a faint pattern: pitches are a little more
likely to line up north–south or east–west than diagonally. But that turns
out not to be GAA wisdom either. In towns, pitches simply follow the
streets around them. In the countryside the pattern fades and tilts with
the grain of the land — and Irish soccer pitches, measured the same way,
show exactly the same thing. The compass belongs to the country, not to
the code. And in a final twist, the big county grounds mostly run
east–west: straight into the setting sun the folklore warns about.

The full workings — data, method, statistics, and honest caveats — are in
[`exploration/FINDINGS.md`](exploration/FINDINGS.md).

## What's here

`exploration/` holds the two scripts that pulled and measured the pitches
(one for GAA, one for the soccer control group), the derived datasets, and
the findings. Everything is reproducible: the scripts are plain Python
with no dependencies, and the raw data snapshots are kept alongside the
results.

## Status

Exploration complete, findings frozen (July 2026). Next: turning the
answer into something you can see — county-by-county compass roses and
the full write-up, at cbrennan.ie/pitch-compass.

## Data

Pitch geometry from OpenStreetMap via the Overpass API.
Data © OpenStreetMap contributors, ODbL 1.0 —
https://www.openstreetmap.org/copyright. Derived datasets in this
repository are shared under the same licence.