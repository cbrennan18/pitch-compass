/* Pitch Compass — the floodlit stage engine (Stage 3A-ii: real-device
 * fixes after phone testing — resize/flicker fix, settled-scene caching,
 * camera moves instead of hard cuts, sun sweep cut. See index.html and
 * the Stage 3A / 3A-ii build reports).
 *
 * ONE sticky stage, one canvas. Every pitch holds a per-scene target
 * [x,y,scale,alpha]; scroll drives an eased interpolation between
 * consecutive scenes. Scenes are DESCRIPTORS with an optional overlay
 * (ctx,w,t) hook — the rose mirror, the soccer guest rose and the
 * on-canvas labels are overlays, not special-cased scene indices. This
 * generalises the v4 prototype's hand-wired mW dispatch.
 *
 * Scenes (9, but only 7 have their own scroll card — see SCENE_CARD near
 * sceneState() for how 5/7 share a neighbour's card as a camera move):
 *   0 protagonist · 1 island · 2 rose · 3 soccer guest · 4 town/country
 *   5 Dublin wide (camera-only) · 6 Dublin 6km · 7 back-to-island
 *   (camera-only) · 8 Cavan–Monaghan (last; holds here)
 *
 * Chalk on grass; amber is now used nowhere (the sun sweep, its only
 * remaining use, was cut in 3A-ii). Data © OpenStreetMap contributors
 * (ODbL 1.0); see /data
 * and the methods box.
 */
(() => {
  "use strict";
  // One sticky stage since Stage 3A (was two, sharing one engine — the
  // array-based canvas handling is kept as-is since it works unchanged for
  // one canvas too, not because a second stage is expected back).
  const canvases = Array.from(document.querySelectorAll(".stage-canvas"));
  if (!canvases.length) return;
  const ctxs = canvases.map(c => c.getContext("2d"));
  let ctx = ctxs[0];
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const CHALK = "#f4f1e4";   // AMBER removed Stage 3A-ii: its only use (the sun sweep) was cut
  const CHALK_FAINT = "rgba(244,241,228,.62)";
  const CHALK_LINE = "rgba(244,241,228,.28)";
  const SERIF = "Charter, Georgia, 'Times New Roman', serif";
  const ALPHA_SKIP = 0.05;   // device-gate fix #9 (was 0.02)

  let VW = 0, VH = 0;
  let P = [];            // pitch objects {b,L,W,name,urban,gx,gy}
  let SOCCER = [];       // soccer guest bearings (numbers)
  let OUTLINES = null;   // {coast:[[ [lon,lat],... ]], borders:[...]}
  let DUBLIN_STREETS = null;   // lazy-loaded, Dublin scene only (item 3)
  let dublinStreetsRequested = false;
  let CM_BORDERS = null;       // lazy-loaded, Cavan scene only (Stage 3A-ii, item C)
  let cmBordersRequested = false;
  let FIT = {};          // stored map fitters: island / dublin / cavan
  let protagonists = {}; // {sun,wind,north,none} -> index into P
  let protagIdx = 0;     // current protagonist (quiz-selected)

  // ---------- geometry (equirectangular, ref lat 53.4) ----------
  const K = Math.cos(53.4 * Math.PI / 180);
  const toXY = (lat, lon) => [lon * K, -lat];

  // bandH/bandY0 (Stage 3A, item 1): optional vertical band to CONTAIN-fit
  // and centre within, instead of the full viewport. Defaults preserve
  // existing behaviour for every caller except the portrait island fit,
  // which passes bandH = VH*0.62 so the island sits in the upper band and
  // the card below doesn't overlap it. The scale itself is computed
  // against bandH (not VH), so this can never clip -- it's still a
  // contain-fit, just contained within a smaller box.
  function fitter(latMin, latMax, lonMin, lonMax, pad, bandH, bandY0) {
    bandH = bandH || VH; bandY0 = bandY0 || 0;
    const [x0] = toXY(latMax, lonMin), [, y0] = toXY(latMax, lonMin);
    const [x1] = toXY(latMin, lonMax), [, y1] = toXY(latMin, lonMax);
    const s = Math.min((VW - 2 * pad) / (x1 - x0), (bandH - 2 * pad) / (y1 - y0));
    const ox = (VW - s * (x1 - x0)) / 2, oy = bandY0 + (bandH - s * (y1 - y0)) / 2;
    return {
      pos: p => [ox + (p.gx - x0) * s, oy + (p.gy - y0) * s],
      posLL: (lon, lat) => [ox + (lon * K - x0) * s, oy + (-lat - y0) * s],
      pxPerM: s / 111320,
    };
  }

  // deterministic per-pitch jitter in [0,1)
  const hash = (i, salt) => ((i * 2654435761 + salt * 40503) >>> 16 & 255) / 255;

  // ---------- scene target arrays ----------
  // Stage 3A-ii: sun sweep (was 7) cut; two camera-only keyframes (Dublin-
  // wide, back-to-island) added for item C -- 0..8 now, 9 scenes total,
  // but still only 7 cards (see SCENE_CARD near sceneState()).
  const N = 9;
  let S = [];            // S[i] = Float32Array(P.length*4)
  let mirror = null;     // rose fold mirror positions (2 per pitch)
  let guestMirror = null;   // GAA disc's mirror ghost, in the soccer-guest scene
  let soccerRose = null; // precomputed soccer guest rose [x,y] per bearing
  let soccerMirror = null;  // soccer disc's mirror ghost (device-gate fix #1)
  let roseCentre = null; // {cx,cy,R} of the centred rose (for the sun sweep)
  let guestCentre = null, soccerCentre = null;   // {cx,cy,R} of scene 3's two discs
  // town/country petal roses: 6 AXIS-bins of 30deg covering [0,180) — each
  // pitch's bearing falls in exactly one, so shares sum to 1. Bin 0 (centred
  // 0/180) and bin 3 (centred 90/270) are exactly make_site_data.py's own
  // cardinal_pct population ("within 15deg of a multiple of 90"), so the
  // petal shape and the cardinal-emphasis brightening share one definition.
  let townPetal = null, countryPetal = null;
  let townGi = [], countryGi = [];   // subset-local -> global P index, for ghosts
  const EMPH_FULL = 1.0, EMPH_FAINT = 0.45;   // cardinal-emphasis alpha ratio

  function axisBinOf(bDeg) {
    const m = ((bDeg % 180) + 180) % 180;      // normalise to [0,180)
    return Math.floor((m + 15) / 30) % 6;       // bins centred 0/30/60/90/120/150
  }
  function withinCardinalAxis(bDeg) {
    const bin = axisBinOf(bDeg);
    return bin === 0 || bin === 3;
  }

  // Petal rose for a subset of P (array of global indices). Petal length is
  // LINEAR in bin share (matches the main rose's convention elsewhere in the
  // piece); refR is the uniform-expectation radius for the dashed reference
  // ring (item 2's honesty anchor, same device as f1's dashed uniform line).
  // Each pitch draws at its TRUE bearing angle (no invented angular jitter —
  // real bearings already spread across the bin); radius is jittered within
  // [0, petalR] in the same "ring near the edge" style as the main rose.
  // ghost[] mirrors each dot to bearing+180 (axial data is a line, not a
  // ray) — same convention as the main rose's `mirror` array.
  function buildPetalRose(cx, cy, R, giList) {
    const n = giList.length;
    const axisCount = new Array(6).fill(0);
    giList.forEach(gi => axisCount[axisBinOf(P[gi].b)]++);
    const petalR = axisCount.map(c => R * (c / n));
    const refR = R / 6;   // uniform expectation: 1/6 share per axis-bin
    const pos = new Array(n), ghost = new Array(n);
    giList.forEach((gi, k) => {
      const p = P[gi];
      const rOut = petalR[axisBinOf(p.b)];
      const rr = rOut * (0.70 + 0.28 * hash(gi, 5));
      const a = (p.b - 90) * Math.PI / 180;
      pos[k] = [cx + rr * Math.cos(a), cy + rr * Math.sin(a)];
      ghost[k] = [cx - rr * Math.cos(a), cy - rr * Math.sin(a)];
    });
    return { cx, cy, R, refR, petalR, pos, ghost };
  }

  function setTarget(arr, i, x, y, s, a) { arr.set([x, y, s, a], i * 4); }

  function buildScenes() {
    S = Array.from({ length: N }, () => new Float32Array(P.length * 4));

    // Stage 3A, item 1: one portrait test, used everywhere below instead of
    // scene 4's old ad-hoc VW<640 check. Landscape/desktop branches are
    // untouched verbatim.
    const isPortrait = VH > VW * 1.2;

    // 0 — protagonist: the chosen named pitch alone, large; the rest hidden
    const prot = P[protagIdx];
    const psc = Math.min(VW, VH) * 0.5 / prot.L;
    P.forEach((p, i) => setTarget(S[0], i, VW / 2, VH * 0.42,
      p === prot ? psc : 0.02, p === prot ? 1 : 0));

    // 1 — island: the cast on the island, coast + county borders drawn faint
    //     underneath (the "unaided" conceit retired — author's call).
    //     Portrait: DON'T fit to height (that clips coast) — still a
    //     contain-fit, just contained within the upper ~62% of the
    //     viewport, so the card below doesn't sit on top of it.
    const isl = isPortrait
      ? fitter(51.35, 55.45, -10.6, -5.4, 24, VH * 0.62, 0)
      : fitter(51.35, 55.45, -10.6, -5.4, 24);
    FIT.island = isl;
    P.forEach((p, i) => { const [x, y] = isl.pos(p);
      setTarget(S[1], i, x, y, isl.pxPerM, 1); });

    // 2 — rose: every bearing folded onto one compass, centred
    const cx = VW / 2, cy = VH / 2, R = Math.min(VW, VH) * 0.34;
    roseCentre = { cx, cy, R };
    mirror = new Float32Array(P.length * 2);
    P.forEach((p, i) => {
      const a = (p.b - 90) * Math.PI / 180;
      const r = R * (0.70 + 0.28 * hash(i, 1));
      setTarget(S[2], i, cx + r * Math.cos(a), cy + r * Math.sin(a), 0.09, 1);
      mirror[i * 2] = cx - r * Math.cos(a);
      mirror[i * 2 + 1] = cy - r * Math.sin(a);
    });

    // 3 — soccer guest: the GAA rose slides left and shrinks; a second rose
    //     (the 2,458 soccer bearings) forms beside it as an overlay. Both
    //     discs get a mirror ghost too (device-gate fix #1 — this scene's
    //     GAA disc was half-folded same as scenes 2/7 were).
    //     Portrait: stack vertically (GAA top, soccer bottom) instead of
    //     side-by-side — same margin/label-budget pattern as scene 4's
    //     stacked petals, sized to fill whatever space that leaves.
    let gcx, gcy, gR, scx, scy;
    if (isPortrait) {
      // Stage 3A-ii fix: two stacked circles need 4 radii of vertical space
      // (2 diameters), not 2 -- this divided by 2, so gR could come out
      // width-bound (169px) even when the real two-circle footprint (4*gR)
      // didn't fit the actual height, overflowing at anything under ~820px
      // (confirmed clipped at 664/667/750, barely fit at 844 by luck). The
      // petal-stack formula below (scene 4) already divides by 4 correctly;
      // this now matches it.
      // MARK_MARGIN: drawRoseMark ticks (ROSE_MARK_PX=12) extend a few px
      // beyond a mark's own jittered radius (max 0.98*gR) -- without this,
      // gR sized to exactly fill VH still let mark tips poke 1-3px past
      // the edge at the tightest heights (confirmed at 375x667). A flat
      // pixel budget, not a fraction of gR, so it holds at every size.
      const MARK_MARGIN = 8;
      const topM = 20, gapM = 44, botM = 20 + MARK_MARGIN, labelH = 30;
      const bandH = (VH - topM - gapM - botM - 2 * labelH) / 4;
      gR = Math.max(40, Math.min((VW - 2 * 26) / 2, bandH));
      gcx = scx = VW / 2;
      gcy = topM + labelH + gR;
      scy = gcy + gR + gapM + labelH + gR;
    } else {
      gcx = VW * 0.30; gcy = VH * 0.5; gR = Math.min(VW, VH) * 0.24;
      scx = VW * 0.70; scy = VH * 0.5;
    }
    guestCentre = { cx: gcx, cy: gcy, R: gR };
    guestMirror = new Float32Array(P.length * 2);
    P.forEach((p, i) => {
      const a = (p.b - 90) * Math.PI / 180;
      const r = gR * (0.70 + 0.28 * hash(i, 1));
      setTarget(S[3], i, gcx + r * Math.cos(a), gcy + r * Math.sin(a), 0.075, 1);
      guestMirror[i * 2] = gcx - r * Math.cos(a);
      guestMirror[i * 2 + 1] = gcy - r * Math.sin(a);
    });
    soccerCentre = { cx: scx, cy: scy, R: gR };
    soccerRose = new Float32Array(SOCCER.length * 2);
    soccerMirror = new Float32Array(SOCCER.length * 2);
    SOCCER.forEach((b, i) => {
      const a = (b - 90) * Math.PI / 180;
      const r = gR * (0.70 + 0.28 * hash(i, 7));
      soccerRose[i * 2] = scx + r * Math.cos(a);
      soccerRose[i * 2 + 1] = scy + r * Math.sin(a);
      soccerMirror[i * 2] = scx - r * Math.cos(a);
      soccerMirror[i * 2 + 1] = scy - r * Math.sin(a);
    });

    // 4 — town vs country: two BINNED PETAL ROSES (gate-fail fix #2). 12 bins
    //     of 30deg, phase-shifted so bin centres land on 0/30/60/.../330 —
    //     the four centred on 0/90/180/270 are exactly the pipeline's own
    //     "within 15deg of a cardinal" definition (cardinal_pct in
    //     make_site_data.py), so the petal shape and the cardinal-emphasis
    //     brightening below share ONE definition, not two invented ones.
    //     Petal length is LINEAR in bin share (same convention as the main
    //     rose elsewhere in the piece) with a dashed reference ring at the
    //     uniform-expectation radius (R_max/12) — the same honesty device
    //     f1's sunset chart already uses, so a spike past the ring reads as
    //     "more than chance," not just "longer."
    townGi = []; countryGi = [];
    P.forEach((p, i) => (p.urban ? townGi : countryGi).push(i));
    // device-gate fix #4: was Math.min(VW,VH)*0.20 (~90px blobs) side by
    // side always — unreadable, and the caption clipped at both edges on
    // narrow viewports. Now stacked vertically (town above country) below
    // TOWNCOUNTRY_STACK_BELOW_PX, and in both layouts the radius is DERIVED
    // from the actual space needed for the labels/gap/caption margins
    // (rather than a fixed fraction of VW/VH that happened to fit on the
    // one viewport it was eyeballed against) — so it's provably ~2x+
    // larger with no overlap or clipping across viewport shapes, not just
    // the common ones. Verified numerically across 10 representative
    // viewports (phone/tablet, portrait/landscape, incl. short-landscape
    // extremes) — see the build report.
    // Stage 3A: gate on the shared isPortrait flag, not a width-only
    // threshold — was VW < 640, now consistent with scenes 1/3 above.
    const TC_SIDE_M = 26, TC_TOP_M = 14, TC_LABEL_H = 24, TC_CAP_H = 50, TC_BOT_M = 14;
    const stacked = isPortrait;
    let tcx, tcy, ccx, ccy, petalR4;
    if (stacked) {
      const gapM = 20;
      const rByW = (VW - 2 * TC_SIDE_M) / 2;
      const rByH = (VH - TC_TOP_M - 2 * TC_LABEL_H - gapM - TC_CAP_H - TC_BOT_M) / 4;
      petalR4 = Math.max(30, Math.min(rByW, rByH));
      tcx = ccx = VW / 2;
      tcy = TC_TOP_M + TC_LABEL_H + petalR4;
      ccy = tcy + petalR4 + gapM + TC_LABEL_H + petalR4;
    } else {
      const gapM = 30;
      const rByW = (VW - 2 * TC_SIDE_M - gapM) / 4;
      const rByH = Math.min(VH / 2 - TC_TOP_M - TC_LABEL_H, VH / 2 - TC_CAP_H - TC_BOT_M);
      petalR4 = Math.max(30, Math.min(rByW, rByH));
      tcx = VW / 2 - petalR4 - gapM / 2; ccx = VW / 2 + petalR4 + gapM / 2;
      tcy = ccy = VH / 2;
    }
    townPetal = buildPetalRose(tcx, tcy, petalR4, townGi);
    countryPetal = buildPetalRose(ccx, ccy, petalR4, countryGi);
    let ti = 0, ci = 0;
    P.forEach((p, i) => {
      const [x, y] = p.urban ? townPetal.pos[ti++] : countryPetal.pos[ci++];
      // cardinal emphasis: full chalk within 15deg of N/S/E/W, faint otherwise
      const alpha = withinCardinalAxis(p.b) ? EMPH_FULL : EMPH_FAINT;
      setTarget(S[4], i, x, y, 0.06, alpha);
    });

    // Stage 3A-ii, item C: camera MOVES instead of hard cuts. Dublin-wide
    // (5) and back-to-island (7) are extra CAMERA keyframes -- they get a
    // real target array like every other scene, but no card of their own
    // (see SCENE_CARD below): island -> Dublin-wide -> Dublin-6km reads as
    // one continuous zoom across the scroll distance that used to be a
    // single hard cut, and Dublin-6km -> back-to-island -> Cavan reads as
    // zoom-out-then-in instead of a second hard cut.

    // 5 — Dublin WIDE: the whole county fit (outlines.json's own Dublin
    // bbox), pitches as symbols (not true shape -- 252 pitches county-wide
    // would be sub-pixel dots at this zoom anyway; a fixed-length symbol
    // reads as "there's a pitch here" the way the close-ups already do).
    const dubWide = fitter(53.178, 53.635, -6.547, -5.996, 20);
    FIT.dublinWide = dubWide;
    P.forEach((p, i) => { const [x, y] = dubWide.pos(p);
      setTarget(S[5], i, x, y, dubWide.pxPerM, withinCardinalAxis(p.b) ? EMPH_FULL : EMPH_FAINT); });

    // 6 — Dublin 6km (unchanged from Stage 3A): true shape via drawPitch
    // wherever a pitch clears DUBLIN_TRUE_SHAPE_MIN_PX, streets underneath.
    const dub = fitter(53.3429, 53.3971, -6.2852, -6.1948, 22);
    FIT.dublin = dub;
    P.forEach((p, i) => { const [x, y] = dub.pos(p);
      setTarget(S[6], i, x, y, dub.pxPerM, withinCardinalAxis(p.b) ? EMPH_FULL : EMPH_FAINT); });

    // 7 — back-to-island: literally scene 1's island framing again (same
    // fitter, same positions) -- the camera zooming out to the same
    // geographic frame it started from, before zooming into Cavan.
    P.forEach((p, i) => S[7].set(S[1].subarray(i * 4, i * 4 + 4), i * 4));

    // 8 — Cavan-Monaghan (drumlin comb). Last scene now. Cardinal emphasis
    // (same axis test as item 2) reuses the alpha channel, same mechanism.
    const cav = fitter(53.92, 54.28, -7.45, -6.78, 22);
    FIT.cavan = cav;
    P.forEach((p, i) => { const [x, y] = cav.pos(p);
      setTarget(S[8], i, x, y, cav.pxPerM, withinCardinalAxis(p.b) ? EMPH_FULL : EMPH_FAINT); });
  }

  // ---------- pitch renderer: LOD stroke -> rect -> line markings ----------
  function drawPitch(p, x, y, s, alpha, col) {
    const l = p.L * s, w = p.W * s;
    ctx.save(); ctx.translate(x, y); ctx.rotate(p.b * Math.PI / 180);
    ctx.globalAlpha = alpha; ctx.strokeStyle = col;
    if (l < 3.5) {
      ctx.lineWidth = 1.1;
      ctx.beginPath();
      ctx.moveTo(0, -Math.max(l, 2) / 2); ctx.lineTo(0, Math.max(l, 2) / 2);
      ctx.stroke();
    } else {
      ctx.lineWidth = Math.min(1.5, .8 + l / 220);
      ctx.strokeRect(-w / 2, -l / 2, w, l);
      if (l > 56) {
        ctx.globalAlpha = alpha * .35;
        ctx.beginPath(); ctx.moveTo(-w / 2, 0); ctx.lineTo(w / 2, 0); ctx.stroke();
        if (l > 140) {         // the two 20 m lines, when really close
          const q = l * (20 / 145);
          ctx.beginPath();
          ctx.moveTo(-w / 2, -l / 2 + q); ctx.lineTo(w / 2, -l / 2 + q);
          ctx.moveTo(-w / 2, l / 2 - q); ctx.lineTo(w / 2, l / 2 - q); ctx.stroke();
        }
      }
    }
    ctx.restore();
  }

  // Dublin/Cavan close-ups only (gate-fail fix #3): a single stroke with a
  // minimum length floor, not the true-scale rect — at close-up zoom a small
  // rectangle blobs, a line reads an angle. Bearing stays exact; length
  // becomes symbolic. Flat thin line weight (not scaled by the artificial
  // length) + reduced alpha: measured density in these boxes is 130
  // (Dublin) / 91 (Cavan) pitches on one screen, so full-weight strokes in
  // real clusters read as solid mush — dialled back so individual strokes
  // stay legible where pitches sit close together.
  const MIN_STROKE_PX = 18;
  const CLOSEUP_LINE_ALPHA = 0.6;
  const CLOSEUP_LINE_WIDTH = 1;
  // Stage 3A, item 3: the decision threshold for Dublin's true-shape vs
  // symbolic fallback (see dublinTrueShape in renderFrame) -- distinct from
  // MIN_STROKE_PX above, which is the symbolic renderer's OWN floor once
  // that fallback is in use, not the choice of whether to use it.
  const DUBLIN_TRUE_SHAPE_MIN_PX = 6;
  function drawPitchSymbolic(p, x, y, s, alpha) {
    const l = Math.max(p.L * s, MIN_STROKE_PX);
    ctx.save(); ctx.translate(x, y); ctx.rotate(p.b * Math.PI / 180);
    ctx.globalAlpha = alpha * CLOSEUP_LINE_ALPHA;
    ctx.strokeStyle = CHALK; ctx.lineWidth = CLOSEUP_LINE_WIDTH;
    ctx.beginPath(); ctx.moveTo(0, -l / 2); ctx.lineTo(0, l / 2); ctx.stroke();
    ctx.restore();
  }

  // Rose-context mark (device-gate fixes #1/#2): every folded-compass scene
  // (main rose, soccer guest, sun sweep) draws EVERY dot — GAA primary, GAA
  // mirror ghost, soccer primary, soccer mirror ghost — with this ONE
  // renderer. A rose is a folded diagram, not a spatial map: true L/W
  // doesn't belong here (that's what made the GAA disc a "smooth solid
  // mass" of true-scale rects while the soccer guest, which has no L/W,
  // came out as unrelated tick marks). Fixed length/width/alpha, angle =
  // true bearing — position (already jittered by radius) carries the
  // density signal, mark geometry carries nothing but direction, and it's
  // now IDENTICAL for both codebases so the two discs are a fair comparison.
  const ROSE_MARK_PX = 12, ROSE_MARK_ALPHA = 0.6, ROSE_MARK_WIDTH = 1;
  function drawRoseMark(bDeg, x, y, alpha) {
    if (alpha < ALPHA_SKIP) return;
    ctx.save(); ctx.translate(x, y); ctx.rotate(bDeg * Math.PI / 180);
    ctx.globalAlpha = alpha * ROSE_MARK_ALPHA;
    ctx.strokeStyle = CHALK; ctx.lineWidth = ROSE_MARK_WIDTH;
    ctx.beginPath(); ctx.moveTo(0, -ROSE_MARK_PX / 2); ctx.lineTo(0, ROSE_MARK_PX / 2); ctx.stroke();
    ctx.restore();
  }

  function label(text, x, y, col, size, italic) {
    ctx.fillStyle = col || CHALK;
    ctx.font = (italic === false ? "" : "italic ") + (size || 15) + "px " + SERIF;
    ctx.textAlign = "center";
    ctx.fillText(text, x, y);
  }

  // Word-wrapped, centred label (device-gate fix #4) — canvas has no native
  // text wrap, and the town/country caption was a single fillText call that
  // clipped at both viewport edges on narrow screens. Greedy-wraps to
  // maxWidth via measureText, one fillText per line.
  function wrapLabel(text, cx, y, maxWidth, col, size, lineH) {
    ctx.fillStyle = col || CHALK_FAINT;
    ctx.font = "italic " + (size || 12) + "px " + SERIF;
    ctx.textAlign = "center";
    const words = text.split(" ");
    const lines = [];
    let line = "";
    for (const word of words) {
      const test = line ? line + " " + word : word;
      if (line && ctx.measureText(test).width > maxWidth) { lines.push(line); line = word; }
      else line = test;
    }
    if (line) lines.push(line);
    lines.forEach((l, i) => ctx.fillText(l, cx, y + i * (lineH || (size || 12) + 4)));
  }

  // faint chalk coast + county borders, projected through a stored fitter,
  // drawn UNDER the cast (island / Dublin / Cavan close-ups)
  function strokePaths(paths, fit, w, weight) {
    ctx.beginPath();
    for (const path of paths) {
      for (let k = 0; k < path.length; k++) {
        const [x, y] = fit.posLL(path[k][0], path[k][1]);
        k ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
      }
    }
    ctx.strokeStyle = CHALK; ctx.globalAlpha = w; ctx.lineWidth = weight;
    ctx.stroke();
  }
  function drawOutlines(fit, w) {
    if (!OUTLINES || !fit) return;
    ctx.save();
    strokePaths(OUTLINES.borders, fit, w * 0.22, 1);   // internal borders, faintest
    strokePaths(OUTLINES.coast, fit, w * 0.42, 1);     // coast a touch stronger
    ctx.restore();
  }

  // Stage 3A-ii, item C: Cavan + Monaghan drawn at higher weight than the
  // faint island borders already under them (outlines.json's borders
  // aren't individually named, so a bbox emphasis would also catch
  // Leitrim/Fermanagh/Meath/Tyrone -- this uses a small named file
  // instead, docs/data/cm_borders.json, generated from the same boundary
  // source assign_counties.py reads). Labelled so there's a sense of
  // where the close-up actually is, per the phone-test note.
  function drawCMBorders(w) {
    if (!CM_BORDERS || !FIT.cavan) return;
    ctx.save();
    for (const name of ["Cavan", "Monaghan"]) {
      const paths = CM_BORDERS[name];
      if (!paths) continue;
      strokePaths(paths, FIT.cavan, w * 0.85, 1.6);
      // label near the ring's own centroid (simple point average -- these
      // are single simplified rings, not multi-part, so this stays inside
      // the county for both)
      let sx = 0, sy = 0, n = 0;
      for (const [lon, lat] of paths[0]) { sx += lon; sy += lat; n++; }
      const [lx, ly] = FIT.cavan.posLL(sx / n, sy / n);
      ctx.globalAlpha = w;
      label(name, lx, ly, CHALK, 15, false);
    }
    ctx.restore();
  }
  // device-gate fix #10: on the very first approach (scene0 protagonist ->
  // scene1 island), the island outline used to ramp in on the raw t of that
  // whole approach window — starting the instant the island card entered
  // its ARRIVE_PX zone, while the protagonist card was still comfortably
  // readable. Delayed so the outline only starts appearing in the LAST
  // (1-OUTLINE_DELAY) share of that approach, once the island is genuinely
  // forming. Scoped to exactly the (i===1, a===0) case — Dublin/Cavan's
  // already-approved outline timing (2B-i) is untouched.
  const OUTLINE_DELAY = 0.55;
  function outlineWeight(i, a, t) {   // triangular around owning scene i
    if (i === 1 && a === 0) {
      return Math.max(0, Math.min(1, (t - OUTLINE_DELAY) / (1 - OUTLINE_DELAY)));
    }
    return a === i - 1 ? t : (a === i ? 1 - t : 0);
  }

  // N/S/E/W around a centred rose, chalk-faint (item 4; radius fixed for
  // device-gate fix #6 — letters were partly occluded by the rose's own
  // outer marks. A flat pixel margin outside R clears any petal/mark that
  // reaches close to R, unlike the old 6%-of-R factor which shrank to
  // nothing on a small rose.)
  const COMPASS_MARGIN_PX = 16;
  function drawCompass(cx, cy, R, w) {
    const r = R * 1.15 + COMPASS_MARGIN_PX;
    const pts = [["N", 0, -1], ["S", 0, 1], ["E", 1, 0], ["W", -1, 0]];
    ctx.save(); ctx.globalAlpha = w * 0.72;
    for (const [t, dx, dy] of pts) label(t, cx + dx * r, cy + dy * r + 5, CHALK_FAINT, 14, false);
    ctx.restore();
  }

  // ---------- overlays, keyed to their owning scene ----------
  // Each returns nothing; called with weight w in (0,1] and local ease t.
  function ovProtagonist(w) {
    const p = P[protagIdx];
    const y = VH * 0.42 + Math.min(VW, VH) * 0.31;
    const place = p.county ? p.name + ", " + p.county : (p.name || "Unnamed");
    ctx.save(); ctx.globalAlpha = w;
    label(place, VW / 2, y, CHALK, 15);
    label(p.L + " m × " + p.W + " m · bearing " + p.b + "°", VW / 2, y + 22,
      CHALK_FAINT, 13);
    ctx.restore();
  }
  // The full axial ring: primary cast (drawn by the main per-pitch loop,
  // unchanged true-LOD rendering) + its mirror ghost (axial data is a line,
  // not a ray — every bearing counts at b AND b+180). Device-gate fix #1:
  // this is now CALLED for every scene that shows a complete rose (2 and 7
  // — see the overlay dispatch below), not scene 2 only, so no scene shows
  // a half-folded "C". The function itself is untouched: scene 7's disc is
  // a literal copy of scene 2's (S[7] = S[2]), so reusing it as-is keeps
  // both scenes visually identical, not just individually complete.
  function ovMirror(w, cur) {
    for (let i = 0; i < P.length; i++) {
      drawPitch(P[i], mirror[i * 2], mirror[i * 2 + 1], 0.09,
        cur[i * 4 + 3] * w * 0.7, CHALK);
    }
    if (roseCentre) drawCompass(roseCentre.cx, roseCentre.cy, roseCentre.R, w);
  }
  // Device-gate fix #2: GAA and soccer now share ONE mark renderer
  // (drawRoseMark) for every dot in this scene — primary GAA (drawn by the
  // main per-pitch loop, guestRoseMode), GAA's mirror ghost, primary
  // soccer, and soccer's mirror ghost. Only the bearing DATA differs between the two
  // discs now; a reader comparing "smooth mass" vs "spiky bristles" was
  // comparing two different renderers, not two different datasets. No
  // bearing value, for either cast, is touched here — this is render-only.
  function ovSoccer(w, cur, gaaGate) {
    ctx.save();
    // GAA disc's mirror ghost (own centre/radius — this scene shrinks and
    // relocates the GAA disc left of centre, same convention as scene 2/7).
    for (let i = 0; i < P.length; i++) {
      drawRoseMark(P[i].b, guestMirror[i * 2], guestMirror[i * 2 + 1],
        cur[i * 4 + 3] * w * gaaGate * 0.7);
    }
    // Soccer disc: primary + mirror ghost, identical geometry to the GAA disc.
    for (let i = 0; i < SOCCER.length; i++) {
      drawRoseMark(SOCCER[i], soccerRose[i * 2], soccerRose[i * 2 + 1], w);
      drawRoseMark(SOCCER[i], soccerMirror[i * 2], soccerMirror[i * 2 + 1], w * 0.7);
    }
    // label the two discs on-canvas
    ctx.globalAlpha = w;
    label("GAA", guestCentre.cx, guestCentre.cy + guestCentre.R + 26, CHALK, 16, false);
    label("Soccer", soccerCentre.cx, soccerCentre.cy + soccerCentre.R + 26, CHALK, 16, false);
    ctx.restore();
  }
  // dashed reference ring at the uniform-expectation radius (item 2's honesty
  // anchor) — same "dashed uniform line" device f1's sunset chart uses.
  function petalRefRing(petal, w) {
    ctx.save(); ctx.globalAlpha = w * 0.55; ctx.strokeStyle = CHALK;
    ctx.lineWidth = 1; ctx.setLineDash([4, 4]);
    ctx.beginPath(); ctx.arc(petal.cx, petal.cy, petal.refR, 0, Math.PI * 2);
    ctx.stroke(); ctx.setLineDash([]); ctx.restore();
  }
  // mirrored ghost dots (axial data is a line, not a ray) — same convention
  // and same settle-gated alpha source (cur) as the main rose's ovMirror,
  // so the petal roses don't reintroduce the mid-morph smear in a new spot.
  function petalGhosts(petal, giList, cur, w) {
    for (let k = 0; k < giList.length; k++) {
      const gi = giList[k];
      const [gx, gy] = petal.ghost[k];
      drawPitch(P[gi], gx, gy, 0.06, cur[gi * 4 + 3] * w * 0.7, CHALK);
    }
  }
  function ovTownCountry(w, cur) {
    if (!townPetal) return;
    petalRefRing(townPetal, w); petalRefRing(countryPetal, w);
    petalGhosts(townPetal, townGi, cur, w);
    petalGhosts(countryPetal, countryGi, cur, w);
    ctx.save(); ctx.globalAlpha = w;
    // stats transcribed from the pipeline: urban 46.3% / rural 36.0% cardinal
    label("town", townPetal.cx, townPetal.cy - townPetal.R - 24, CHALK, 16, false);
    label("46% cardinal", townPetal.cx, townPetal.cy - townPetal.R - 5, CHALK_FAINT, 14);
    label("country", countryPetal.cx, countryPetal.cy - countryPetal.R - 24, CHALK, 16, false);
    label("36% cardinal", countryPetal.cx, countryPetal.cy - countryPetal.R - 5, CHALK_FAINT, 14);
    // TODO(author): final wording — states the encoding so the eye isn't
    // asked to infer it. Word-wrapped (device-gate fix #4): was a single
    // fillText that clipped at both viewport edges on narrow screens.
    // Stage 3A: bumped 12->14px (petal/rose label font-size floor).
    wrapLabel("petal length = share of pitches on that axis · bright = within 15° of N/S/E/W",
      (townPetal.cx + countryPetal.cx) / 2,
      Math.max(townPetal.cy, countryPetal.cy) + townPetal.R + 34,
      Math.min(VW - 32, 420), CHALK_FAINT, 14, 18);
    ctx.restore();
  }
  // chalk-italic annotation with a thin leader line into the cluster (item 9).
  // TODO(author): final wording for both close-up labels. The leader line
  // itself always stays chalk-faint (a neutral connector). `col` lets the
  // label text override the default chalk colour; unused since Stage 3A
  // removed the kicker (its only amber-label caller) but kept for the
  // Dublin/Cavan callers, which both still use the default.
  function annotate(text, tx, ty, lx, ly, w, col) {
    ctx.save(); ctx.globalAlpha = w;
    ctx.strokeStyle = CHALK_FAINT; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(tx, ty + 6); ctx.lineTo(lx, ly); ctx.stroke();
    label(text, tx, ty, col || CHALK, 15);   // italic
    ctx.restore();
  }
  // TODO(author): both close-ups also need a small permanent caption stating
  // "pitches shown as symbols, not to scale" (gate-fail fix #3) — drawn here
  // as a faint corner note pending the author's final wording/placement.
  function closeupNote(w) {
    ctx.save(); ctx.globalAlpha = w * 0.8;
    ctx.fillStyle = CHALK_FAINT;
    ctx.font = "italic 12px " + SERIF;
    // device-gate fix #8: was right-anchored at a hardcoded VW-12, which
    // clipped at the right edge. Measure the string and clamp its LEFT
    // edge explicitly, so it can never render past the canvas bounds
    // regardless of viewport width or text metrics.
    const text = "symbols, not scale";
    const margin = 14;
    const tw = ctx.measureText(text).width;
    ctx.textAlign = "left";
    ctx.fillText(text, Math.max(margin, VW - tw - margin), VH - 16);
    ctx.restore();
  }
  function ovDublin(w) {
    annotate("the capital's pitches obey the street grid",
      VW / 2, VH * 0.13, VW / 2, VH * 0.38, w);
    closeupNote(w);
  }
  function ovCavan(w) {
    annotate("combed NE–SW with the drumlins",
      VW / 2, VH * 0.13, VW / 2, VH * 0.38, w);
    closeupNote(w);
  }
  // Stage 3A-ii, item D: the sun-sweep scene (and axisLine, its only
  // caller) was removed -- phone testing found it "adds little." f1
  // (the sunset-deficit chart) already carries the same June/winter
  // numbers in the stage's <noscript> fallback (moved there in 3A).

  // Stage 3A, item 3: the Dublin street layer. Lazy-loaded (see the fetch
  // trigger near boot, below) and drawn only for the Dublin scene, faint
  // chalk under the pitches (same draw-order convention as drawOutlines —
  // backdrop first, cast on top). DUBLIN_STREETS is a plain array of
  // [lon,lat] paths; projected through the SAME fitter (FIT.dublin) the
  // pitches use, so streets and pitches always agree.
  function drawStreets(w) {
    if (!DUBLIN_STREETS || !FIT.dublin) return;
    ctx.save();
    ctx.strokeStyle = CHALK_LINE; ctx.globalAlpha = w; ctx.lineWidth = 1;
    ctx.beginPath();
    for (const path of DUBLIN_STREETS) {
      for (let k = 0; k < path.length; k++) {
        const [x, y] = FIT.dublin.posLL(path[k][0], path[k][1]);
        k ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
      }
    }
    ctx.stroke();
    ctx.restore();
  }

  // overlay owner scene index -> fn (2, 4 dispatched specially below).
  // Stage 3A-ii: 5 (Dublin-wide) and 7 (back-to-island) are camera-only
  // keyframes with no label of their own -- they're not in this map, so
  // they simply draw no overlay, same as scene 1 (island).
  const OVERLAYS = { 0: ovProtagonist, 2: ovMirror, 3: ovSoccer,
                     4: ovTownCountry, 6: ovDublin, 8: ovCavan };

  // ---------- scroll + draw: CARD-DRIVEN pacing (gate-fail fix #1) ----------
  // The old model divided the .scrolly element's total scroll distance into
  // N-1 UNIFORM segments — it never looked at where the .step cards actually
  // sit, and the CSS step heights are not uniform (60vh / 150vh x6 / 190vh),
  // so segment boundaries and card boundaries drifted apart, worse further
  // down the page. Replaced: each transition is now driven by the live
  // getBoundingClientRect() of its OWN destination card.
  const ease = t => t < .5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2;
  // 7 cards remain (protagonist's own card at index 0 is still unused, as
  // before — scene 0 needs no card to "arrive"): island, rose, soccer,
  // townCountry, dublin, cavan at indices 1-6.
  const cardEls = Array.from(document.querySelectorAll(".steps .card"));

  // Stage 3A-ii, item C: SCENE_CARD[i] = [cardIdx, subStart, subEnd] --
  // which card drives scene i's arrival, and which sub-range of that
  // card's raw reveal maps to scene i's own local [0,1] tau. Every scene
  // with its own card uses the full [0,1] range (unchanged behaviour).
  // Dublin-wide (5) and Dublin-6km (6) share card 5 (Dublin's), split at
  // its reveal midpoint; back-to-island (7) and Cavan (8) share card 6
  // (Cavan's) the same way — so the camera move happens smoothly within
  // the SAME scroll distance a single hard cut used to take, no new cards
  // or scroll length.
  const SCENE_CARD = {
    1: [1, 0, 1], 2: [2, 0, 1], 3: [3, 0, 1], 4: [4, 0, 1],
    5: [5, 0, 0.5], 6: [5, 0.5, 1],
    7: [6, 0, 0.5], 8: [6, 0.5, 1],
  };

  // How much scroll (as a fraction of one viewport height) each morph takes.
  // A card's own arrival is complete — formation fully done — exactly when
  // its top edge reaches the viewport bottom (top === VH); before that it's
  // still below the fold. Reaching 1 there, and staying there while the card
  // travels up through and off the viewport, IS the hold — it falls out of
  // the clamp for free, no separate plateau logic needed.
  const ARRIVE_FRAC = 0.6;   // tunable: ARRIVE_PX = VH * ARRIVE_FRAC

  function revealOf(cardEl, arrivePx) {
    const top = cardEl.getBoundingClientRect().top;
    return Math.max(0, Math.min(1, (VH + arrivePx - top) / arrivePx));
  }

  // Returns {a, tau, t}: a = index of the settled base scene; tau = raw
  // arrival progress (0..1) of the NEXT card (card a+1); t = eased/cut tau,
  // ready to interpolate S[a] -> S[a+1].
  function sceneState() {
    const arrivePx = VH * ARRIVE_FRAC;
    const reveal = [1];   // reveal[0] = 1 constant: scene 0 needs no card to "arrive"
    for (let i = 1; i <= N - 1; i++) {
      const [cardIdx, subStart, subEnd] = SCENE_CARD[i];
      const raw = cardEls[cardIdx] ? revealOf(cardEls[cardIdx], arrivePx) : 1;
      reveal[i] = Math.max(0, Math.min(1, (raw - subStart) / (subEnd - subStart)));
    }
    let settled = 0;
    while (settled < N - 1 && reveal[settled + 1] >= 1) settled++;
    const a = Math.min(N - 2, settled);
    const tau = reveal[a + 1];
    const t = reduced ? Math.round(tau) : ease(tau);
    return { a, tau, t };
  }

  // Anti-smear settle gate: an overlay that's a full ghost copy of the
  // moving cast (rose mirrors, petal-rose ghosts) must not draw until the
  // cast has actually finished arriving at scene `fromScene + 1` — else it
  // captures the mid-morph position. Shared by every such overlay (device-
  // gate fix #1 generalises this beyond scene 2 without duplicating it).
  function settleGate(a, tau, fromScene) {
    return (reduced || a !== fromScene) ? 1
      : Math.max(0, Math.min(1, (tau - 0.82) / 0.18));
  }

  // Stage 3A, item 2 (bug fix): every overlay used to have a two-transition
  // window — non-zero while ARRIVING (a===i-1, w=t) AND while DEPARTING
  // (a===i, w=1-t) — so an incoming overlay started drawing the instant its
  // predecessor began fading, at full strength on top of it. That's what
  // doubled the Cavan label onto Dublin's (both annotate() at the same
  // canvas position) and let the amber sun line bleed into the Cavan scene
  // (ovSun's arrival ramped from tau=0, while Cavan's own label was still
  // near full strength). Delaying the ARRIVING half only — same idea as
  // OUTLINE_DELAY and settleGate elsewhere in this file — leaves the first
  // ARRIVE_DELAY share of every transition entirely to the outgoing
  // overlay, closing both leaks with one change instead of two.
  const ARRIVE_DELAY = 0.5;
  const arriveWeight = t => Math.max(0, (t - ARRIVE_DELAY) / (1 - ARRIVE_DELAY));

  let CUR = new Float32Array(P.length * 4);

  // Stage 3A-ii, item B: settled-frame cache for the rose (2) and soccer
  // (3) scenes. Measured cost (4x CPU throttle): the per-pitch loop and
  // the mirror-ghost overlay are each ~4.5ms for these scenes, roughly
  // doubling frame cost to redraw ~2,700 pitches twice a frame -- for
  // nothing, once the scene has settled and NOTHING is moving (every
  // scroll position within a hold produces bit-identical output). Raw
  // pixel-to-pixel canvas copy (no dpr scaling math needed: cache and
  // live canvas share identical device-pixel dimensions whenever the
  // cache is valid). Invalidated on any rebuild (width or qualifying
  // height change -- see rebuild()) and implicitly on scene change,
  // since the cache is keyed by scene index and a mismatched vw/vh
  // simply isn't used.
  const settledCache = {};
  function invalidateSettledCache() { for (const k in settledCache) delete settledCache[k]; }
  function blitSettledCache(entry) {
    ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    ctx.drawImage(entry.canvas, 0, 0);
    ctx.restore();
  }
  function snapshotSettledCache(sceneIdx) {
    const off = document.createElement("canvas");
    off.width = ctx.canvas.width; off.height = ctx.canvas.height;
    off.getContext("2d").drawImage(ctx.canvas, 0, 0);
    settledCache[sceneIdx] = { canvas: off, vw: VW, vh: VH };
  }

  // Draws the current shared scene state into whichever canvas `ctx`
  // currently points at. draw() (below) sets `ctx` and calls this once per
  // registered canvas — only one is ever actually sticky/visible at a given
  // scroll position, but rendering to both is cheap and keeps this function
  // (and everything it calls) completely unaware there are two stages.
  function renderFrame() {
    const { a, tau, t } = sceneState();
    // pure hold (tau===0: the NEXT card hasn't started approaching yet) on
    // the rose or soccer scene -- reuse the cached settled frame if we
    // have one at this size instead of redrawing the full cast + ghosts.
    const cacheable = tau === 0 && (a === 2 || a === 3);
    if (cacheable) {
      const cached = settledCache[a];
      if (cached && cached.vw === VW && cached.vh === VH) { blitSettledCache(cached); return; }
    }
    const A = S[a], B = S[a + 1];
    // Stage 3A-ii: symbolic (min-length stroke) for every petal/close-up
    // scene and its approach -- townCountry(4), Dublin-wide(5, "pitches as
    // symbols" per the camera-move spec), back-to-island(7) and Cavan(8,
    // the last scene, holds).
    const symbolic = (a === 4 || a === 5 || a === 7 || a === 8);
    // Dublin 6km (a===6) only: true shape via drawPitch wherever a pitch
    // clears DUBLIN_TRUE_SHAPE_MIN_PX, falling back to symbolic below it
    // (only 14% fall under that floor at this bbox -- see the build report).
    const dublinTrueShape = a === 6;
    // device-gate fix #2: scene 3 (soccer guest) only. The GAA disc's
    // primary dots switch to the same fixed rose mark the soccer disc (and
    // both discs' mirror ghosts) use in ovSoccer — so the "smooth mass vs
    // spiky bristles" mismatch was a renderer mismatch, not a data one; the
    // two discs are now drawn identically. Scoped narrowly on purpose:
    // scene 2/7's own (already-approved, 2B-i) primary rendering is
    // untouched, switching over only once the guest scene is more-arrived-
    // than-not (t>0.5) during the 2->3 approach, and for all of the 3 hold.
    const guestRoseMode = (a === 2 && t > 0.5) || a === 3;

    ctx.clearRect(0, 0, VW, VH);

    // backdrops UNDER the cast: coast + county borders on every map scene,
    // Dublin's street layer under its pitches too (Stage 3A, item 3).
    // Stage 3A-ii: Dublin-wide(5) and back-to-island(7, reusing the island
    // frame) get the same backdrop treatment as every other map scene;
    // Cavan(8) additionally draws the named Cavan+Monaghan emphasis.
    let ow;
    if ((ow = outlineWeight(1, a, t)) > 0.02) drawOutlines(FIT.island, ow);
    if ((ow = outlineWeight(5, a, t)) > 0.02) drawOutlines(FIT.dublinWide, ow);
    if ((ow = outlineWeight(6, a, t)) > 0.02) { drawOutlines(FIT.dublin, ow); drawStreets(ow); }
    if ((ow = outlineWeight(7, a, t)) > 0.02) drawOutlines(FIT.island, ow);
    if ((ow = outlineWeight(8, a, t)) > 0.02) { drawOutlines(FIT.cavan, ow); drawCMBorders(ow); }

    for (let i = 0; i < P.length; i++) {
      const j = i * 4;
      const x = A[j] + (B[j] - A[j]) * t;
      const y = A[j + 1] + (B[j + 1] - A[j + 1]) * t;
      const s = A[j + 2] + (B[j + 2] - A[j + 2]) * t;
      const al = A[j + 3] + (B[j + 3] - A[j + 3]) * t;
      CUR[j] = x; CUR[j + 1] = y; CUR[j + 2] = s; CUR[j + 3] = al;
      // device-gate fix #9: the parked (0.02-scale, 0-alpha) rest-of-cast in
      // the protagonist scene was leaving a faint smudge inside the big
      // pitch rectangle — raised from 0.02 so any near-zero float residue
      // from the interpolation still gets skipped outright, not drawn.
      if (al < ALPHA_SKIP) continue;
      if (dublinTrueShape) {
        if (P[i].L * s >= DUBLIN_TRUE_SHAPE_MIN_PX) drawPitch(P[i], x, y, s, al, CHALK);
        else drawPitchSymbolic(P[i], x, y, s, al);
      }
      else if (symbolic) drawPitchSymbolic(P[i], x, y, s, al);
      else if (guestRoseMode) drawRoseMark(P[i].b, x, y, al);
      else drawPitch(P[i], x, y, s, al, CHALK);
    }

    // overlays: triangular weight around the owning scene. With a/t now
    // driven by real card position, this same formula also fixes overlay
    // fade-OUT: an overlay's weight is (a===i) ? 1-t : ... — i.e. it now
    // fades out exactly as the NEXT card arrives (1 - reveal(card[i+1])),
    // not on some fraction of a uniform slice. No overlay can persist past
    // its owning scene: once a > i, its branch condition is false and w=0.
    for (const key in OVERLAYS) {
      const i = +key;
      const w = a === i - 1 ? arriveWeight(t) : (a === i ? 1 - t : 0);
      if (w <= 0.02) continue;
      if (i === 2) {
        // rose mirror gated to the hold plateau on arrival (kills the mid-morph
        // smear: the cast is settled before the mirror draws). Cuts if reduced.
        ovMirror(w * settleGate(a, tau, 1), CUR);
      } else if (i === 3) {
        // device-gate fix #1: the soccer-guest scene's GAA disc also needs
        // its mirror ghost (was half-folded before) — same settle gate,
        // fromScene = i-1 = 2 (rose -> guest arrival), same reasoning.
        ovSoccer(w, CUR, settleGate(a, tau, 2));
      } else if (i === 4) {
        // petal-rose ghosts: same settle gate, same reason (item 2's ghosts
        // are a full copy of the moving cast too — avoid reintroducing the
        // scene-2 smear in a new spot).
        ovTownCountry(w * settleGate(a, tau, 3), CUR);
      } else {
        OVERLAYS[i](w);
      }
    }

    if (cacheable && !settledCache[a]) snapshotSettledCache(a);
  }

  function draw() {
    if (!S.length || !cardEls.length) return;
    const { a } = sceneState();
    maybeLoadDublinStreets(a);
    maybeLoadCMBorders(a);
    ctxs.forEach(c => { ctx = c; renderFrame(); });
  }

  // ---------- quiz -> protagonist personalisation + payoff line ----------
  const payoff = {
    sun: "You chose the sun — so does the folklore. If Ireland agreed, this ring would thin along the sunset line. It does not.",
    wind: "You chose the wind — a fine theory. If Ireland agreed, this ring would bulge to the south-west. It does not.",
    north: "You chose true north — the old crowd salutes you. If Ireland agreed, the top of this ring would swell. It does not.",
    none: "You said it makes no difference. 2,707 committees agree with you.",
  };
  function pick(answer) {
    if (protagonists[answer] != null) protagIdx = protagonists[answer];
    const verdict = document.getElementById("verdict");
    if (verdict) verdict.textContent = payoff[answer] || payoff.none;
    const after = document.getElementById("quiz-after");
    if (after) after.textContent = "Noted. 2,707 committees answered before you — scroll.";
    buildScenes(); draw();
  }
  const quiz = document.getElementById("quiz");
  if (quiz) quiz.addEventListener("click", e => {
    const b = e.target.closest("button"); if (!b) return;
    quiz.querySelectorAll("button").forEach(x => x.classList.remove("picked"));
    b.classList.add("picked");
    pick(b.dataset.a);
  });

  // ---------- tap-a-pitch sheet (works on the island / rose) ----------
  const sheet = document.getElementById("sheet");
  function openSheet(p) {
    const under = p.L < 130 || p.W < 80;
    document.getElementById("s-name").textContent = p.name || "Unnamed pitch";
    document.getElementById("s-meta").textContent =
      "bearing " + p.b + "° · " + p.county;
    document.getElementById("s-body").innerHTML =
      p.L + " m × " + p.W + " m. " + (under
        ? '<span class="flag">Under regulation size — like 39% of Ireland\'s adult pitches.</span>'
        : "Full regulation size.");
    sheet.classList.add("open");
  }
  if (sheet) {
    // Attached to both canvases — only the currently-sticky one can
    // realistically receive a click, but CUR (shared, canvas-agnostic pixel
    // space) makes the hit test correct regardless of which fired.
    canvases.forEach(c => c.addEventListener("click", e => {
      const r = c.getBoundingClientRect();
      const mx = e.clientX - r.left, my = e.clientY - r.top;
      // wider hit target in the Dublin/Cavan close-ups (item 7).
      // Stage 3A-ii: Dublin 6km is now scene 6, Cavan is scene 8.
      const { a: tapA, t: tapT } = sceneState();
      const scene = tapT > 0.5 ? tapA + 1 : tapA;
      const rad = (scene === 6 || scene === 8) ? 40 : 26;
      let best = -1, bd = rad * rad;
      for (let i = 0; i < P.length; i++) {
        if (CUR[i * 4 + 3] < 0.2) continue;
        const dx = CUR[i * 4] - mx, dy = CUR[i * 4 + 1] - my, d = dx * dx + dy * dy;
        if (d < bd) { bd = d; best = i; }
      }
      if (best < 0) { sheet.classList.remove("open"); return; }
      openSheet(P[best]);
    }));
    sheet.querySelector(".close").onclick = () => sheet.classList.remove("open");
  }

  // ---------- boot ----------
  // VW/VH are shared canvas-pixel space: both .stage-canvas elements use the
  // identical CSS rule (100vw x 100svh), so their client sizes are always
  // equal in practice — one shared measurement is correct, not an
  // approximation. Every canvas still gets its own width/height/transform.
  // Stage 3A-ii, item B: the flicker's confirmed root cause. iOS Safari's
  // address bar collapsing/expanding fires several `resize` events during
  // its own ~250-500ms animation, each a HEIGHT-ONLY change of order
  // 50-100px. The old resize() rebuilt buildScenes() (a real per-pitch
  // cost, ~5-6ms measured) on every single one, unconditionally -- so an
  // address-bar transition mid-scroll cost 60ms+ of stacked rebuild work
  // and produced 30-35ms frames (measured: 4 of 14 frames during one
  // simulated collapse burst), which is the flicker.
  //
  // Fix, matching what was asked, revised once during this build after
  // profiling caught a second-order bug in the first version (see below):
  // a full buildScenes() rebuild only happens for a WIDTH change or a
  // height change of >=150px from the last rebuilt size (comfortably
  // above the address bar's own ~50-100px range, so this is a size-class
  // distinction, not a magic number tuned to one device), debounced
  // 150ms so a burst of qualifying events (e.g. real orientation change,
  // which also fires several resizes) coalesces into one rebuild.
  //
  // On an IGNORED (small, height-only) change, this now does NOTHING —
  // not even a cheap canvas-pixel resize. First version updated the
  // canvas bitmap size immediately on every event "so nothing looks
  // clipped mid-transition", but that desynced the live VW/VH from the
  // coordinate space S[] and the settled-frame cache were actually built
  // for: the cache's stored vw/vh no longer matched live VW/VH, so it
  // missed on every frame during a resize burst and fell through to a
  // full per-pitch re-render anyway — re-profiling with the resize-storm
  // simulation still showed 3 of 12 frames over 16ms even though
  // buildScenes() itself was correctly no longer firing. Leaving the
  // canvas bitmap untouched during an ignored change means the CSS box
  // (`canvas { width:100%; height:100% }`) simply scales the existing
  // bitmap to fit — a barely-perceptible blur for a <150px, sub-second
  // mismatch, not a positional or clipping bug, and zero JS work.
  const RESIZE_HEIGHT_IGNORE_PX = 150;
  const RESIZE_DEBOUNCE_MS = 150;
  let lastBuiltVW = 0, lastBuiltVH = 0, resizeDebounceTimer = null;

  function applyCanvasPixelSize(w, h) {
    VW = w; VH = h;
    canvases.forEach((c, k) => {
      c.width = VW * dpr; c.height = VH * dpr;   // DPR cap stays at 2 (see `dpr` above)
      ctxs[k].setTransform(dpr, 0, 0, dpr, 0, 0);
    });
  }

  function rebuild() {
    applyCanvasPixelSize(canvases[0].clientWidth, canvases[0].clientHeight);
    lastBuiltVW = VW; lastBuiltVH = VH;
    CUR = new Float32Array(P.length * 4);
    invalidateSettledCache();   // Stage 3A-ii, item B: new framing, cache is stale
    buildScenes(); draw();
  }

  function onResize() {
    const w = canvases[0].clientWidth, h = canvases[0].clientHeight;
    const widthChanged = w !== lastBuiltVW;
    const heightJump = Math.abs(h - lastBuiltVH);
    if (!lastBuiltVW || widthChanged || heightJump >= RESIZE_HEIGHT_IGNORE_PX) {
      clearTimeout(resizeDebounceTimer);
      resizeDebounceTimer = setTimeout(rebuild, RESIZE_DEBOUNCE_MS);
    }
    // else: genuinely do nothing (see the comment above rebuild()).
  }

  let ticking = false;
  addEventListener("scroll", () => {
    if (!ticking) { ticking = true;
      requestAnimationFrame(() => { draw(); ticking = false; }); }
  }, { passive: true });
  // visualViewport is the event actually designed for this (address-bar
  // chrome changes, on-screen keyboard) and fires independently of
  // `resize`, which some browsers suppress for chrome-only changes.
  // Falls back to window resize where visualViewport isn't available.
  if (window.visualViewport) {
    visualViewport.addEventListener("resize", onResize);
  } else {
    addEventListener("resize", onResize);
  }

  // Stage 3A, item 3: the Dublin street layer loads lazily, only once
  // town/country (4) is approaching Dublin-wide (5) — not in the initial
  // Promise.all. Checked from inside draw() (cheap — the scene state is
  // already computed every frame for rendering) and fired at most once.
  function maybeLoadDublinStreets(a) {
    if (dublinStreetsRequested || a < 4) return;
    dublinStreetsRequested = true;
    fetch("data/dublin_streets.json").then(r => r.json()).then(j => {
      DUBLIN_STREETS = j.data; draw();
    }).catch(err => console.error("dublin_streets.json load failed", err));
  }
  // Stage 3A-ii, item C: same lazy pattern, triggered once back-to-island
  // (7) is near, so it's loaded well before Cavan (8) actually needs it.
  function maybeLoadCMBorders(a) {
    if (cmBordersRequested || a < 6) return;
    cmBordersRequested = true;
    fetch("data/cm_borders.json").then(r => r.json()).then(j => {
      CM_BORDERS = j.counties; draw();
    }).catch(err => console.error("cm_borders.json load failed", err));
  }

  Promise.all([
    fetch("data/cast.json").then(r => r.json()),
    fetch("data/soccer_bearings.json").then(r => r.json()),
    fetch("data/outlines.json").then(r => r.json()),
  ]).then(([castJson, soccerJson, outlinesJson]) => {
    const f = castJson.fields;
    const bi = f.indexOf("bearing"), li = f.indexOf("L"), wi = f.indexOf("W"),
          ni = f.indexOf("name"), ci = f.indexOf("county"), ui = f.indexOf("urban"),
          lati = f.indexOf("lat"), loni = f.indexOf("lon");
    P = castJson.data.map(rec => {
      const [x, y] = toXY(rec[lati], rec[loni]);
      return { b: rec[bi], L: rec[li], W: rec[wi], name: rec[ni],
               county: rec[ci], urban: rec[ui], gx: x, gy: y };
    });
    protagonists = castJson.protagonists || {};
    protagIdx = protagonists.none != null ? protagonists.none : 0;
    SOCCER = soccerJson.bearings;
    OUTLINES = outlinesJson;

    // initial boot: rebuild() itself measures + applies + builds, no
    // debounce needed here (that's only for subsequent resize events)
    rebuild();
  }).catch(err => {
    console.error("stage data load failed", err);
    document.querySelectorAll(".stage").forEach(s => s.classList.add("stage--failed"));
  });
})();
