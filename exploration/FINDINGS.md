# Findings — Exploration Phase

**Pitch Compass** — *Every GAA pitch in Ireland, and which way it points.*

Exploration ran July 2026. This document freezes the data, method, and
findings that the product phase builds on. Everything here is reproducible
from the two scripts in this directory.

## The question

Is there folk wisdom in how GAA pitches are oriented — avoiding the setting
sun, aligned with the prevailing south-westerlies, true north — or is it
chaos? Nobody had answered this. Either answer was publishable.

## The answer

**There is no GAA compass.** Irish GAA pitches show no preferred playing
direction whatsoever. The order that does exist — a modest preference for
compass-aligned pitches over diagonal ones — is not GAA lore: it is
inherited from the street grid in towns and from the grain of the land in
the countryside, and Irish soccer pitches show the same pattern almost
number for number. As a kicker, the county grounds cluster east–west:
straight into the setting sun that the most-cited piece of folklore says
you should avoid.

## Data

One-time global Overpass pull of all elements tagged
`sport~gaelic_games|gaelic_football|hurling|camogie`
(OSM data timestamp 2026-07-15T12:00:52Z): 4,438 elements — 4,312 ways,
37 relations, 89 nodes. Of these, 3,334 are `leisure=pitch`; 854 are
`sports_centre` club-grounds outlines (excluded from orientation analysis
as their shape is not a playing surface); 47 are stadiums.

The **signal sample** applies three filters to isolate real, unambiguous
playing pitches: `leisure=pitch`, aspect ratio ≥ 1.2 (near-square polygons
have no meaningful orientation), and area 2,000–20,000 m² (full and
juvenile pitches; excludes handball alleys, slivers, and grounds
outlines). This yields 2,850 pitches, of which **2,707 are on the island
of Ireland** (lat 51.3–55.5, lon −11.0 to −5.3) and 143 are diaspora —
roughly two clean pitches per GAA club on the island, comfortably above
the coverage bar set before the pull (2,000–4,000).

The control is an identical pipeline over Irish `leisure=pitch` +
`sport~soccer` ways (area-scoped to the Republic and Northern Ireland; OSM
timestamp 2026-07-15T12:30:29Z), with any pitch also tagged
gaelic/hurling/camogie/GAA excluded: 4,028 ways, signal sample 2,455.

## Method

Each polygon's bearing is the long axis of its minimum-area rotated
rectangle (convex hull + rotating calipers), computed in a local
equirectangular projection and folded to [0°, 180°), where 0° = N–S and
90° = E–W. The extractor was validated against synthetic 140×85 m pitches
at Irish latitude across adversarial cases — awkward angles, 1.5 m vertex
jitter, chamfered corners, dense redundant edge vertices, near-fold
wrap — with worst-case error 0.41° and recovered dimensions within 1 m.

Orientation is axial data, so significance tests are Rayleigh tests on
multiplied angles: 2θ detects a single preferred axis ("pitches point
one way"), 4θ detects a four-fold cardinal pattern ("pitches prefer the
compass points over the diagonals"). R ∈ [0,1] is the resultant length:
0 is uniform chaos, 1 is perfect alignment. "Cardinal %" is the share of
pitches within 15° of a N–S or E–W axis; uniform expectation is 33.3%.

## Findings

**1. Pitches point every which way.** There is no favoured playing
direction, which kills the strong version of every folk theory — sun,
wind, north. Axial (2θ) test, Ireland, n = 2,707: R = 0.017, p = 0.44 —
as uniform as it gets at this sample size.

**2. But compass-aligned pitches are a little more common than they
should be.** Pitches running north–south or east–west modestly outnumber
diagonal ones. 4θ test: R = 0.107, p = 3.3×10⁻¹⁴; 38.0% of pitches lie
within 15° of a compass axis versus 33.3% expected. Order exists — but
see below for whose order it is.

**3. Town pitches follow the streets; country pitches follow the land.**
Near the cities, pitches sit almost exactly on the north–south/east–west
grid; out in the country the effect fades and — curiously — tilts about
fifteen degrees off the compass. Urban pitches (within 20 km of Dublin,
Cork, Galway, Limerick or Belfast; n = 540): R₄ = 0.236 with mean
orientation 0.1° and 46.3% cardinal. Rural pitches (n = 2,167) retain a
weaker effect (R₄ = 0.096, p = 2.4×10⁻⁹, 36.0% cardinal) whose preferred
axes sit at ~75°/165°.

**4. Soccer pitches do exactly the same thing — so it isn't GAA lore.**
Irish soccer pitches, measured identically, reproduce the whole pattern:
overall R₄ = 0.089 (p = 2.8×10⁻⁹), 38.6% cardinal; urban R₄ = 0.192 at
mean 3.9°, 45.1% cardinal; rural R₄ = 0.061 at mean **73.2°**, 34.3%
cardinal. Most telling, the rural tilt is identical across the two codes
(73.2° vs 74.6°) — two sports with different histories and different
folklore inheriting the same grain of field boundaries and roads. The
cardinal effect is Irish land, not GAA lore.

**5. The county grounds run into the setting sun.** The one rule everyone
cites — don't make the keeper stare into the west — is the one the big
grounds break: their long axes cluster roughly east–west. Stadiums
(n = 29, aspect ≥ 1.1): R₄ = 0.409, p = 0.007, 55.2% cardinal — Semple
92°, Páirc Uí Rinn 89°, TUS Gaelic Grounds 84°, O'Connor Park 82°, Páirc
Tailteann 73°.

**6. The pattern shifts as you move around the island.** The southeast is
the most ordered corner, the northeast is nearly chaos, and the northwest
leans to axes of its own. Island quadrants around (53.4°N, 7.9°W):
southeast R₄ = 0.151, 43.7% cardinal; southwest R₄ = 0.199; northwest
tilted to ~14°/104°; northeast R₄ = 0.063, p = 0.03, 32.9% cardinal.
County-level analysis awaits a boundaries file (product phase).

**7. Overseas clubs play on other people's grids.** The 143 diaspora
pitches are more grid-bound than Irish ones (R₄ = 0.197, p = 0.004, 48.3%
cardinal) — consistent with clubs abroad playing on municipal grounds laid
out by someone else. One minor genuine code difference: soccer shows a
faint single-axis preference for E–W (2θ R = 0.047, p = 0.004) that GAA
entirely lacks.

## Limitations

OSM coverage is not a census: mapped pitches skew toward well-mapped
areas, and ~2,700 clean pitches against ~1,600 clubs means some grounds
are missing or drawn as outlines only. Bearings measure the polygon as
mapped, not surveyed ground truth. The urban/rural split is a 20 km
five-city proxy, not a land-use classification. The GAA-vs-soccer rural
gap (R₄ 0.096 vs 0.061) looks real but small and has not been tested for
significance between samples. Handball alleys, astro pens and degenerate
polygons are excluded by the size/aspect filters, not by hand; nothing was
manually curated, which is the point.

## Reproducing

`python3 explore_gaa.py` (global GAA pull → `gaa_out/`) and
`python3 soccer_control.py` (Irish soccer control → `soccer_out/`).
Stdlib only; matplotlib optional for the rose PNG. Raw Overpass responses
are saved alongside the derived CSVs for reproducibility. Analysis beyond
the scripts (urban/rural, quadrants, stadiums) is straightforward from
`pitches.csv` / `soccer_pitches.csv` using the same Rayleigh machinery.

## Attribution

Data © OpenStreetMap contributors, ODbL 1.0 —
https://www.openstreetmap.org/copyright. Derived datasets in this
directory are shared under the same licence.