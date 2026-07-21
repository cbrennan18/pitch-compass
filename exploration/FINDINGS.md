# Findings — Exploration Phase (complete)

**Pitch Compass** — *Every GAA pitch in Ireland, and which way it points.*

Exploration ran July 2026 in four rounds: orientation and a soccer
control; sunset, twin pitches, sizes and names; county assignment and
regional geography; and a final round of direct tests and robustness
checks. This document freezes the data, methods and findings
the write-up builds on. Everything is reproducible from the scripts in
this directory; all headline numbers were computed by the project's own
`analyse.py` and `analyse_extra.py` against the frozen datasets.

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
The final round adds a coastline derived from the same county boundary
files — no new download — by edge cancellation: every polygon segment is
hashed by its endpoints and those appearing once are exterior, while
internal borders appear twice and cancel; the endpoint hash is snapped to
~100 m (`HASH_PREC = 3`) because the two agencies digitise the shared
borders independently, and a 3 km cross-file scrub drops the ROI–NI land
border. It is validated by known distances — Dingle, Bundoran and Youghal
all under 1 km from the derived coast, Cusack Park in Mullingar 74 km
inland. Headline results are stable across aspect thresholds 1.15–1.4 and
cardinal/sunset tolerances of 10–20°.

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
of its own order on top of the land's — a whisper that does not clear the
project's corrected significance bar (Finding 15).

**6. The folklore's ghost: pitches slightly avoid the midsummer sunset.**
Pitches within 15° of the June-solstice sunset axis (131.8°): 363, vs
~452 uniform (z ≈ 4.8 deficit). The control that matters is winter: its
sunset axis (48.2°) is exactly as diagonal, yet less depleted (427;
equinox 509). Same geometry, different deficit, and the larger avoidance
falls in the season when evening matches are actually played into low
sun (June-vs-winter z ≈ 2.3, p = 0.023 — suggestive, not conclusive, and
short of the corrected bar the deficit itself clears; Finding 15). A faint
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

**10. The counties differ — and the Ice Age shows its hand.** Read one
county at a time, the league table is mostly mirage: bootstrap 95% CIs
(2,000 resamples, seed 1798) show that at n ≈ 30–60 nearly every county's
R₄ reaches down to where pure noise sits at that sample size — only
**Cork** (R₄ = 0.286, n = 272), **Dublin** (0.318, n = 252) and
**Tipperary** (0.331, n = 124) clear their own uniform-noise ceilings.
What survives is regional. The **drumlin belt** (Cavan, Monaghan, Down,
Leitrim — glacial hills with a shared NE–SW grain) is more internally
ordered than the rest of the island (R₄ = 0.172 vs 0.119) around a tilted
axis (58.6° vs 82.6°), cardinal-% collapsing to 23.7 vs 39.7 — and it
clears the project's corrected significance bar (Finding 15). The sharpest
single contrast holds up too: **Longford minus Tyrone**, an R₄ difference
of 0.392, 95% CI [0.084, 0.527], excluding zero. Longford (n = 33,
R₄ = 0.41, ordered around a *diagonal* 49.3° axis, just 9.1% cardinal) and
Cavan (R₄ = 0.234, mean axis 40.5°, the lowest cardinal share in Ireland
at 14.1%) are best read now not as chart-toppers but as illustrations of
the belt — Longford, drumlin country not even in the pre-registered set,
tilting exactly the way the drumlins do, while Tyrone (R₄ = 0.018) points
anywhere. Pitches in drumlin country align with the hills the ice left.

**11. The Atlantic wind gets nothing — and this time it was tested
head-on.** If the prevailing south-westerlies shaped pitches, the seaboard
counties (Kerry, Clare, Galway, Mayo, Sligo, Donegal) should share an
axis. They are instead the least coherent region measured: R₄ = 0.045
(n = 516) vs 0.124 east of them. The final round put the wind on trial
directly. The wind-axis test counts pitches lying *along* the wind (45°)
against those turned *across* it (135°) — two equally diagonal lines, so
the diagonal grid deficit hits both identically and any gap between them
is wind and only wind. There is no gap in any cohort (45-vs-135 z = 0.78
island, 0.58 rural, 1.29 seaboard, 0.20 drumlin); both diagonals are
merely depleted together (island z = −2.28 and −3.41 against uniform — the
grid, not the weather). The drumlin belt is the clean discriminator: a
wind would push 45° over 135°, yet the belt's 45-vs-135 z is ≈ 0.2 — its
tilt is symmetric about the diagonal, the ice's signature, not the wind's.
A derived coastline (edge-cancelled from the county boundaries; see
Method) lets us look from the other side: across pitches < 5 km, 5–15 km
and > 15 km from the sea, the angle between a pitch and its nearest length
of coast is flat in every band — no along-coast shelter bulge, no
facing-the-sea peak. Two small twitches in the 5–15 km ring (a
parallel-to-coast excess, z = 2.28; a 45-vs-135 lean, z = 2.70) fall well
short of the corrected bar and are read as noise. The wind hypothesis
predicted coherence and, tested four ways, found chaos. (Rugged terrain —
every pitch its own valley — remains the charitable reading; either way,
no folklore.)

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

**15. An honesty count: six findings survive the multiple-comparisons
bar.** Run enough tests and something will look significant by chance, so
we counted every hypothesis test in the project — 21 of them — and applied
a Bonferroni correction: a result now has to clear α = 0.05 / 21 = 0.00238,
not 0.05, to count. Six clear it: the island cardinal effect (Finding 2),
its urban and rural halves (Finding 3), the drumlin belt's tilt
(Finding 10), the June-sunset deficit (Finding 6), and the
copy-or-turn-square rule at twin pitches (Finding 7). The three faint
fingerprints stay faint by design — the June-versus-winter sunset gap
(p = 0.023), the extra rural order in GAA over soccer (p = 0.055), and
soccer's lone E–W lean (p = 0.004) all miss the corrected threshold and
are reported as suggestive only, not as verdicts.

## Limitations

OSM coverage is not a census; polygons measure what mappers drew.
Urban/rural is a 20 km five-city proxy. County extremes at n ≈ 30–60
carry wide error bars: bootstrap CIs put nearly every single-county R₄
within reach of uniform noise, and only Cork, Dublin and Tipperary clear
their own noise ceilings — so the regional coherences, not the
single-county superlatives, are the robust findings. The seaboard null may
blend terrain with wind. The rural GAA–soccer gap and the
June-versus-winter sunset contrast are sub-threshold signals, reported as
suggestive; the June-sunset deficit itself clears the corrected bar
(Finding 15). The derived coastline is edge-cancelled from generalised
boundaries, and its cross-file scrub can shave a little genuine coast where
the ROI and NI shorelines pass within 3 km at Lough Foyle and Carlingford
Lough.
Name dedications await the human review pass (110 unattributed people);
club-vs-ground bucketing is a heuristic with known leakage. Sizes may be
conservative if polygons trace grass rather than lines. Nothing was
manually curated except where explicitly stated — which is the point.

## Reproducing

`explore_gaa.py` (global GAA pull → `gaa_out/`), `soccer_control.py`
(Irish soccer control → `soccer_out/`), `assign_counties.py` (county
boundaries in `boundaries/` → `gaa_out/county_map.csv`, self-verifying),
`analyse.py` (all findings from the frozen CSVs → terminal +
`gaa_out/analysis_summary.json`), `analyse_extra.py` (final-round tests —
wind axis, coastline suite, bootstrap CIs, robustness grid,
multiple-comparisons inventory — from the frozen CSVs plus a coastline
derived from the boundaries → terminal + `gaa_out/extra_summary.json`,
`gaa_out/coastline_segments.csv`), `make_rose.py` (roses from either
dataset). Pull and derivation scripts are stdlib-only; matplotlib for
roses only. Raw Overpass responses are committed alongside derived data.

## Attribution

Pitch data © OpenStreetMap contributors, ODbL 1.0 —
openstreetmap.org/copyright. County boundaries: Tailte Éireann
(Creative Commons Attribution 4.0); Ordnance Survey of Northern Ireland
(UK Open Government Licence). Derived datasets in this directory are
shared under the source licences.