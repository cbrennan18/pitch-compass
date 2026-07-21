# Findings — Exploration Phase (complete)

**Pitch Compass** — *Every GAA pitch in Ireland, and which way it points.*

Exploration ran July 2026 in three rounds: orientation and a soccer
control; sunset, twin pitches, sizes and names; county assignment and
regional geography. This document freezes the data, methods and findings
the write-up builds on. Everything is reproducible from the scripts in
this directory; all headline numbers were computed by the project's own
`analyse.py` against the frozen datasets.

## The question

Is there folk wisdom in how GAA pitches are oriented — avoiding the
setting sun, aligned with the prevailing south-westerlies, true north —
or is it chaos? Nobody had answered this. Either answer was publishable.

## The answer

**There is no GAA compass — the land holds the pen.** Irish GAA pitches
show no preferred playing direction whatsoever. The order that does exist
is modest, and it is not GAA lore: in towns, pitches follow the street
grid; in the countryside they follow the grain of the land — most vividly
in the drumlin belt, where pitches align with hills the ice sheet
moulded. Irish soccer pitches show the same patterns almost number for
number. Two faint fingerprints of the games themselves survive: a small
deficit of pitches along the midsummer-sunset line, and a slightly
stronger rural order in GAA than in soccer — both suggestive, neither
conclusive. And the county grounds run east–west regardless: straight
into the setting sun the folklore warns about.

## Data

**GAA pull** (one-time, global; OSM timestamp 2026-07-15T12:00:52Z):
4,438 elements tagged `sport~gaelic_games|gaelic_football|hurling|
camogie` — 4,312 ways, of which 4,059 are on the island of Ireland.
The **signal sample** — `leisure=pitch`, aspect ≥ 1.2, area
2,000–20,000 m², island bounding box — is **2,707 pitches**, roughly two
per club against the GAA's own figure of ~1,600 clubs on the island.
143 clean diaspora pitches sit outside the box.

**Soccer control** (island-scoped; OSM timestamp 2026-07-15T12:30:29Z):
4,028 ways, identical pipeline and filters, any pitch also tagged
gaelic/hurling/camogie/GAA excluded; signal sample 2,455.

**County boundaries:** Tailte Éireann "Counties — National Statutory
Boundaries" (CC-BY 4.0) for the 26, OSNI "Largescale Boundaries — County
Boundaries" (OGL) for the six. Every one of the 4,059 Irish ways was
assigned to a county by ray-cast point-in-polygon (`assign_counties.py`);
zero unassigned; verified against known grounds (Croke Park → Dublin,
Semple → Tipperary, TUS Gaelic Grounds → Limerick). "Londonderry" in the
OSNI schema is reported as Derry, per GAA convention.

## Method

Each polygon's bearing is the long axis of its minimum-area rotated
rectangle (convex hull + rotating calipers), folded to [0°, 180°);
validated on synthetic pitches to worst-case error 0.41°. Orientation is
axial data, so tests are Rayleigh tests on multiplied angles: 2θ for a
single preferred axis, 4θ for a four-fold cardinal pattern; R ∈ [0,1]
(0 chaos, 1 lockstep). "Cardinal %" is the share of pitches within 15°
of a N–S or E–W axis (uniform expectation 33.3%). Urban means within
20 km of Dublin, Cork, Galway, Limerick or Belfast. The GAA-vs-soccer
rural comparison is a 10,000-trial permutation test (seed 1798). Sunset
azimuths come from the standard declination formula at latitude 53.4°.

## Findings

**1. Pitches point every which way.** No favoured playing direction —
the strong version of every folk theory is dead. 2θ, Ireland, n = 2,707:
R = 0.017, p = 0.44.

**2. Compass-aligned pitches are modestly over-represented.** 4θ:
R = 0.107, p = 3.3×10⁻¹⁴; 38.0% within 15° of a compass axis vs 33.3%
expected.

**3. Town pitches follow the streets; country pitches follow the land.**
Urban (n = 540): R₄ = 0.236, mean axis 0.1° — dead on the grid — 46.3%
cardinal. Rural (n = 2,167): R₄ = 0.096, p = 2.4×10⁻⁹, 36.0% cardinal,
axes tilted to ~75°/165°.

**4. Soccer does the same — so it isn't GAA lore.** Soccer overall
R₄ = 0.089; urban R₄ = 0.192 at mean 3.9°; rural R₄ = 0.060 at mean
73.2° — the same fifteen-degree rural tilt in both codes. The cardinal
effect is Irish land, not GAA culture.

**5. GAA's extra rural order is a whisper, not a verdict.** Rural GAA
R₄ = 0.0957 (n = 2,167) vs rural soccer 0.0598 (n = 1,471); gap 0.0359.
Permutation test, 10,000 shuffles, seed 1798: **p = 0.0549** — just shy
of significance. The honest reading: in the countryside the two codes
are statistically indistinguishable, with a hint that GAA adds a whisper
of its own order on top of the land's.

**6. The folklore's ghost: pitches slightly avoid the midsummer sunset.**
Pitches within 15° of the June-solstice sunset axis (131.8°): 363, vs
~452 uniform (z ≈ 4.8 deficit). The control that matters is winter: its
sunset axis (48.2°) is exactly as diagonal, yet less depleted (427;
equinox 509). Same geometry, different deficit, and the larger avoidance
falls in the season when evening matches are actually played into low
sun (June-vs-winter z ≈ 2.3 — suggestive, not conclusive). A faint
fingerprint of the one piece of folklore everyone cites.

**7. Orientation at a club is binary: copy or turn square.** Of 1,346
neighbour-pairs of pitches within 300 m, 50.1% are parallel (within 15°)
and 34.1% perpendicular — 84% at the two extremes vs 33% by chance; the
middle bins hold 2–6% each. A club's orientation is decided once, by
whoever levelled the first field, then inherited or rotated 90° to fit
the site. This is the mechanism: folklore is not consulted per pitch,
because orientation is not chosen per pitch.

**8. Two in five pitches are under regulation, and town squeezes them.**
Of 2,380 adult-scale pitches (length ≥ 100 m): medians 141.2 × 83.3 m;
18.7% under 130 m long, 36.3% under 80 m wide, **39.1% undersized on at
least one dimension** — width is what gets sacrificed. Urban (n = 465):
mean length 134.7 m, 47.7% undersized. Rural (n = 1,915): 140.2 m,
37.0%. Caveat: OSM polygons may trace the mown grass rather than the
marked lines.

**9. Ireland names its grounds for the sacred dead and its clubs for
defiance.** 1,333 named Irish features dedupe to 1,288 unique entities:
992 club names, 194 ground names, 102 functional labels. Ground-name
dedications (heuristic, pending the human review pass): 30 saints,
13 patriots, 12 memorials, 7 clergy, 110 as-yet-unattributed people —
the Walsh Parks and Kelly Parks whose stories (player, priest, patriot,
or the man who gave the field) string-matching cannot know. Club
epithets, deduped: Gaels 19, Óg 14, Rovers 10, Emmets 8, Shamrocks 8,
Harps 5 — Robert Emmet leads the patriots across all naming. "Park"
outnumbers "Páirc" roughly three to one.

**10. The counties differ — and the Ice Age shows its hand.** Most
internally ordered county: **Longford** (n = 33, R₄ = 0.41), ordered
around a *diagonal* axis (49.3°) with just 9.1% of pitches cardinal.
Most chaotic: **Tyrone** (R₄ = 0.018 — pitches point anywhere). The
**drumlin belt** (Cavan, Monaghan, Down, Leitrim — glacial hills with a
shared NE–SW grain) is more internally ordered than the rest of the
island (R₄ = 0.172 vs 0.119) around a tilted axis (58.6° vs 82.6°),
with cardinal-% collapsing to 23.7 vs 39.7. Cavan is the thesis in one
row: R₄ = 0.234, mean axis 40.5°, and the lowest cardinal share in
Ireland (14.1%). Longford — drumlin country not even included in the
pre-registered set — topping the table is the pattern volunteering
itself. Pitches in drumlin country align with the hills the ice left.

**11. The Atlantic wind gets nothing.** If the prevailing
south-westerlies shaped pitches, the seaboard counties (Kerry, Clare,
Galway, Mayo, Sligo, Donegal) should share an axis. They are instead the
least coherent region measured: R₄ = 0.045 (n = 516) vs 0.124 east of
them. The wind hypothesis predicted coherence and found chaos. (Rugged
terrain — every pitch its own valley — is the charitable alternative
reading; either way, no folklore.)

**12. Four provinces, four relationships with the compass.** Munster the
most ordered (R₄ = 0.255, 41.8% cardinal — Tipperary and Cork driving
it); Leinster grid-locked (mean axis 1.4°, 42.7% cardinal — Dublin's
pull); Ulster tilted off-compass (mean 61.0°, 28.3% cardinal — the
drumlins again); Connacht near-chaos (R₄ = 0.062).

**13. The county grounds run into the setting sun.** Stadiums (n = 29):
R₄ = 0.409, 55.2% cardinal, long axes clustering east–west — Semple 92°,
Páirc Uí Rinn 89°, TUS Gaelic Grounds 84°, O'Connor Park 82°, Páirc
Tailteann 73°. The one rule everyone cites is the one the cathedrals
break.

**14. Overseas clubs play on other people's grids.** Diaspora pitches
(n = 143): R₄ = 0.197, 48.3% cardinal — municipal grounds, someone
else's grid. One minor genuine code difference: soccer has a faint
single-axis preference for E–W (2θ R = 0.047, p = 0.004) that GAA lacks.

## Limitations

OSM coverage is not a census; polygons measure what mappers drew.
Urban/rural is a 20 km five-city proxy. County extremes at n ≈ 30–50
carry wide error bars — regional coherences are the robust findings,
single-county superlatives should be quoted with their n. The seaboard
null may blend terrain with wind. The sunset deficit and the rural
GAA–soccer gap are both sub-threshold signals, reported as suggestive.
Name dedications await the human review pass (110 unattributed people);
club-vs-ground bucketing is a heuristic with known leakage. Sizes may be
conservative if polygons trace grass rather than lines. Nothing was
manually curated except where explicitly stated — which is the point.

## Reproducing

`explore_gaa.py` (global GAA pull → `gaa_out/`), `soccer_control.py`
(Irish soccer control → `soccer_out/`), `assign_counties.py` (county
boundaries in `boundaries/` → `gaa_out/county_map.csv`, self-verifying),
`analyse.py` (all findings from the frozen CSVs → terminal +
`gaa_out/analysis_summary.json`), `make_rose.py` (roses from either
dataset). Pull and derivation scripts are stdlib-only; matplotlib for
roses only. Raw Overpass responses are committed alongside derived data.

## Attribution

Pitch data © OpenStreetMap contributors, ODbL 1.0 —
openstreetmap.org/copyright. County boundaries: Tailte Éireann
(Creative Commons Attribution 4.0); Ordnance Survey of Northern Ireland
(UK Open Government Licence). Derived datasets in this directory are
shared under the source licences.