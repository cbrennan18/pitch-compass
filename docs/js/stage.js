/* Pitch Compass — the floodlit stage engine (Stage 2B-i Acts 1–3 +
 * 2B-ii Act 5's kicker; Act 4's charts are static, off-stage — see index.html).
 *
 * TWO sticky stages sharing ONE engine. Every pitch holds a per-scene
 * target [x,y,scale,alpha]; scroll drives an eased interpolation between
 * consecutive scenes. Scenes are DESCRIPTORS with an optional overlay
 * (ctx,w,t) hook — the rose mirror, the soccer guest rose, the sun sweep,
 * the stadium kicker and the on-canvas labels are overlays, not
 * special-cased scene indices. This generalises the v4 prototype's
 * hand-wired mW/sunW/kickW dispatch.
 *
 * Scenes:
 *   0 protagonist · 1 island · 2 rose · 3 soccer guest · 4 town/country
 *   5 Dublin · 6 Cavan–Monaghan · 7 rose + sun sweep · 8 THE KICKER
 * Scenes 0–7 live on the first sticky stage (.scrolly #1); scene 8 lives
 * on a SECOND, independent sticky stage after the Act 4 charts — the
 * stage deliberately un-sticks and re-sticks (see the card-driven pacing
 * section below for why this needs no special-casing at all).
 *
 * Chalk on grass; amber is semantic (the sun sweep and the kicker's
 * stadiums — the sun/floodlight is the subject of both). Data ©
 * OpenStreetMap contributors (ODbL 1.0); see /data and the methods box.
 */
(() => {
  "use strict";
  // Two independent sticky stages (Act 1–3's and the kicker's), ONE shared
  // engine: each canvas is just another render target for the same S[]/P/
  // cardEls state. `ctx` is reassigned per canvas inside draw()'s loop —
  // every drawing function below closes over it and always sees the right
  // context for whichever canvas is currently being rendered.
  const canvases = Array.from(document.querySelectorAll(".stage-canvas"));
  if (!canvases.length) return;
  const ctxs = canvases.map(c => c.getContext("2d"));
  let ctx = ctxs[0];
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const CHALK = "#f4f1e4", AMBER = "#e8a13d";
  const CHALK_FAINT = "rgba(244,241,228,.62)";
  const CHALK_LINE = "rgba(244,241,228,.28)";
  const SERIF = "Charter, Georgia, 'Times New Roman', serif";

  let VW = 0, VH = 0;
  let P = [];            // pitch objects {b,L,W,name,urban,gx,gy}
  let SOCCER = [];       // soccer guest bearings (numbers)
  let ST = [];           // the 29 county grounds {b,L,W,name,gx,gy}
  let stPos = [];        // stadium positions, island frame (scene 8)
  let OUTLINES = null;   // {coast:[[ [lon,lat],... ]], borders:[...]}
  let FIT = {};          // stored map fitters: island / dublin / cavan
  let protagonists = {}; // {sun,wind,north,none} -> index into P
  let protagIdx = 0;     // current protagonist (quiz-selected)

  // ---------- geometry (equirectangular, ref lat 53.4) ----------
  const K = Math.cos(53.4 * Math.PI / 180);
  const toXY = (lat, lon) => [lon * K, -lat];

  function fitter(latMin, latMax, lonMin, lonMax, pad) {
    const [x0] = toXY(latMax, lonMin), [, y0] = toXY(latMax, lonMin);
    const [x1] = toXY(latMin, lonMax), [, y1] = toXY(latMin, lonMax);
    const s = Math.min((VW - 2 * pad) / (x1 - x0), (VH - 2 * pad) / (y1 - y0));
    const ox = (VW - s * (x1 - x0)) / 2, oy = (VH - s * (y1 - y0)) / 2;
    return {
      pos: p => [ox + (p.gx - x0) * s, oy + (p.gy - y0) * s],
      posLL: (lon, lat) => [ox + (lon * K - x0) * s, oy + (-lat - y0) * s],
      pxPerM: s / 111320,
    };
  }

  // deterministic per-pitch jitter in [0,1)
  const hash = (i, salt) => ((i * 2654435761 + salt * 40503) >>> 16 & 255) / 255;

  // ---------- scene target arrays ----------
  const N = 9;
  let S = [];            // S[i] = Float32Array(P.length*4)
  let mirror = null;     // rose fold mirror positions (2 per pitch)
  let soccerRose = null; // precomputed soccer guest rose [x,y] per bearing
  let roseCentre = null; // {cx,cy,R} of the centred rose (for the sun sweep)
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

    // 0 — protagonist: the chosen named pitch alone, large; the rest hidden
    const prot = P[protagIdx];
    const psc = Math.min(VW, VH) * 0.5 / prot.L;
    P.forEach((p, i) => setTarget(S[0], i, VW / 2, VH * 0.42,
      p === prot ? psc : 0.02, p === prot ? 1 : 0));

    // 1 — island: the cast on the island, coast + county borders drawn faint
    //     underneath (the "unaided" conceit retired — author's call)
    const isl = fitter(51.35, 55.45, -10.6, -5.4, 24);
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
    //     (the 2,458 soccer bearings) forms on the right as an overlay
    const gcx = VW * 0.30, gcy = VH * 0.5, gR = Math.min(VW, VH) * 0.24;
    P.forEach((p, i) => {
      const a = (p.b - 90) * Math.PI / 180;
      const r = gR * (0.70 + 0.28 * hash(i, 1));
      setTarget(S[3], i, gcx + r * Math.cos(a), gcy + r * Math.sin(a), 0.075, 1);
    });
    const scx = VW * 0.70, scy = VH * 0.5;
    soccerRose = new Float32Array(SOCCER.length * 2);
    SOCCER.forEach((b, i) => {
      const a = (b - 90) * Math.PI / 180;
      const r = gR * (0.70 + 0.28 * hash(i, 7));
      soccerRose[i * 2] = scx + r * Math.cos(a);
      soccerRose[i * 2 + 1] = scy + r * Math.sin(a);
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
    const petalR4 = Math.min(VW, VH) * 0.20;
    townPetal = buildPetalRose(VW * 0.30, VH * 0.50, petalR4, townGi);
    countryPetal = buildPetalRose(VW * 0.70, VH * 0.50, petalR4, countryGi);
    let ti = 0, ci = 0;
    P.forEach((p, i) => {
      const [x, y] = p.urban ? townPetal.pos[ti++] : countryPetal.pos[ci++];
      // cardinal emphasis: full chalk within 15deg of N/S/E/W, faint otherwise
      const alpha = withinCardinalAxis(p.b) ? EMPH_FULL : EMPH_FAINT;
      setTarget(S[4], i, x, y, 0.06, alpha);
    });

    // 5 — Dublin close-up (street grid); 6 — Cavan–Monaghan (drumlin comb).
    //     Boxes tightened vs the prototype so the dashes read and tap at phone
    //     scale; county borders drawn under each (items 7 & 9). Rendered with
    //     drawPitchSymbolic (gate-fail fix #3: min-length strokes, not true-
    //     scale rects — a rect blobs at this zoom, a stroke reads an angle).
    //     Cardinal emphasis (same axis test as item 2) reuses the alpha
    //     channel, same mechanism, no new per-scene logic.
    const dub = fitter(53.28, 53.42, -6.40, -6.12, 22);
    FIT.dublin = dub;
    P.forEach((p, i) => { const [x, y] = dub.pos(p);
      setTarget(S[5], i, x, y, dub.pxPerM, withinCardinalAxis(p.b) ? EMPH_FULL : EMPH_FAINT); });
    const cav = fitter(53.92, 54.28, -7.45, -6.78, 22);
    FIT.cavan = cav;
    P.forEach((p, i) => { const [x, y] = cav.pos(p);
      setTarget(S[6], i, x, y, cav.pxPerM, withinCardinalAxis(p.b) ? EMPH_FULL : EMPH_FAINT); });

    // 7 — rose again, re-centred, for the sun sweep (mirror off)
    P.forEach((p, i) => S[7].set(S[2].subarray(i * 4, i * 4 + 4), i * 4));

    // 8 — THE KICKER: cast ghosts to ~0.10 alpha on the SAME island framing
    // as scene 1 (the piece opens and closes on the same geographic frame).
    // The 29 county grounds draw in amber as an overlay (ovKicker) — see
    // below for why amber is correct here (the sun/floodlight is the
    // literal subject: county grounds cluster east–west, into the sunset).
    const KICK_ALPHA = 0.10;
    P.forEach((p, i) => { const [x, y] = isl.pos(p);
      setTarget(S[8], i, x, y, isl.pxPerM, KICK_ALPHA); });
    stPos = ST.map(s => isl.pos(s));
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
  function drawPitchSymbolic(p, x, y, s, alpha) {
    const l = Math.max(p.L * s, MIN_STROKE_PX);
    ctx.save(); ctx.translate(x, y); ctx.rotate(p.b * Math.PI / 180);
    ctx.globalAlpha = alpha * CLOSEUP_LINE_ALPHA;
    ctx.strokeStyle = CHALK; ctx.lineWidth = CLOSEUP_LINE_WIDTH;
    ctx.beginPath(); ctx.moveTo(0, -l / 2); ctx.lineTo(0, l / 2); ctx.stroke();
    ctx.restore();
  }

  function label(text, x, y, col, size, italic) {
    ctx.fillStyle = col || CHALK;
    ctx.font = (italic === false ? "" : "italic ") + (size || 15) + "px " + SERIF;
    ctx.textAlign = "center";
    ctx.fillText(text, x, y);
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
  function outlineWeight(i, a, t) {   // triangular around owning scene i
    return a === i - 1 ? t : (a === i ? 1 - t : 0);
  }

  // N/S/E/W around a centred rose, chalk-faint (item 4)
  function drawCompass(cx, cy, R, w) {
    const r = R * 1.06;
    const pts = [["N", 0, -1], ["S", 0, 1], ["E", 1, 0], ["W", -1, 0]];
    ctx.save(); ctx.globalAlpha = w * 0.72;
    for (const [t, dx, dy] of pts) label(t, cx + dx * r, cy + dy * r + 5, CHALK_FAINT, 13, false);
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
  function ovMirror(w, cur) {
    for (let i = 0; i < P.length; i++) {
      drawPitch(P[i], mirror[i * 2], mirror[i * 2 + 1], 0.09,
        cur[i * 4 + 3] * w * 0.7, CHALK);
    }
    if (roseCentre) drawCompass(roseCentre.cx, roseCentre.cy, roseCentre.R, w);
  }
  function ovSoccer(w) {
    ctx.save();
    for (let i = 0; i < SOCCER.length; i++) {
      const x = soccerRose[i * 2], y = soccerRose[i * 2 + 1];
      const a = (SOCCER[i] - 90) * Math.PI / 180;
      ctx.globalAlpha = w * 0.62; ctx.strokeStyle = CHALK; ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x - 5 * Math.cos(a), y - 5 * Math.sin(a));
      ctx.lineTo(x + 5 * Math.cos(a), y + 5 * Math.sin(a));
      ctx.stroke();
    }
    // label the two discs on-canvas (item 5)
    const gR = Math.min(VW, VH) * 0.24;
    ctx.globalAlpha = w;
    label("GAA", VW * 0.30, VH * 0.5 + gR + 26, CHALK, 16, false);
    label("Soccer", VW * 0.70, VH * 0.5 + gR + 26, CHALK, 16, false);
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
    label("46% cardinal", townPetal.cx, townPetal.cy - townPetal.R - 5, CHALK_FAINT, 13);
    label("country", countryPetal.cx, countryPetal.cy - countryPetal.R - 24, CHALK, 16, false);
    label("36% cardinal", countryPetal.cx, countryPetal.cy - countryPetal.R - 5, CHALK_FAINT, 13);
    // TODO(author): final wording — states the encoding so the eye isn't
    // asked to infer it (item 2 requirement).
    label("petal length = share of pitches on that axis · bright = within 15° of N/S/E/W",
      (townPetal.cx + countryPetal.cx) / 2,
      Math.max(townPetal.cy, countryPetal.cy) + townPetal.R + 36, CHALK_FAINT, 12, false);
    ctx.restore();
  }
  // chalk-italic annotation with a thin leader line into the cluster (item 9).
  // TODO(author): final wording for both close-up labels.
  function annotate(text, tx, ty, lx, ly, w) {
    ctx.save(); ctx.globalAlpha = w;
    ctx.strokeStyle = CHALK_FAINT; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(tx, ty + 6); ctx.lineTo(lx, ly); ctx.stroke();
    label(text, tx, ty, CHALK, 15);   // italic
    ctx.restore();
  }
  // TODO(author): both close-ups also need a small permanent caption stating
  // "pitches shown as symbols, not to scale" (gate-fail fix #3) — drawn here
  // as a faint corner note pending the author's final wording/placement.
  function closeupNote(w) {
    ctx.save(); ctx.globalAlpha = w * 0.8;
    ctx.fillStyle = CHALK_FAINT;
    ctx.font = "italic 12px " + SERIF;
    ctx.textAlign = "right";
    ctx.fillText("symbols, not scale", VW - 12, VH - 14);
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
  function axisLine(cx, cy, R, azDeg, dash) {
    const a = (azDeg - 90) * Math.PI / 180;
    ctx.setLineDash(dash || []);
    ctx.beginPath();
    ctx.moveTo(cx - R * Math.cos(a), cy - R * Math.sin(a));
    ctx.lineTo(cx + R * Math.cos(a), cy + R * Math.sin(a));
    ctx.stroke();
    ctx.setLineDash([]);
    return [cx + R * Math.cos(a), cy + R * Math.sin(a)];   // the "setting" end
  }
  function ovSun(w, t) {
    if (!roseCentre) return;
    const { cx, cy } = roseCentre, R = Math.min(VW, VH) * 0.46;
    const az = 228 + (311.8 - 228) * Math.min(1, t);   // sweep winter -> June
    // the ghost winter axis + both counts fade in once the sweep has settled
    const ghost = Math.max(0, Math.min(1, (t - 0.55) / 0.45)) * w;
    ctx.save();
    drawCompass(cx, cy, roseCentre.R, w);
    if (ghost > 0.02) {
      ctx.strokeStyle = AMBER; ctx.globalAlpha = ghost * 0.5; ctx.lineWidth = 1.5;
      const wend = axisLine(cx, cy, R, 228, [5, 5]);     // winter, dashed ghost
      ctx.globalAlpha = ghost;
      label("winter 427", wend[0], wend[1] + 16, AMBER, 13);
    }
    ctx.strokeStyle = AMBER; ctx.globalAlpha = w; ctx.lineWidth = 2;
    const jend = axisLine(cx, cy, R, az);                 // June, solid
    ctx.fillStyle = AMBER;
    ctx.beginPath(); ctx.arc(jend[0], jend[1], 7, 0, 7); ctx.fill();
    label(t >= 0.98 ? "June 363" : "sunset, by season",
      jend[0], jend[1] - 14, AMBER, 13);
    ctx.restore();
  }

  // THE KICKER (scene 8, Act 5): the 29 county grounds in amber, at their
  // true bearings, on the island frame the ghosted cast (drawn in the main
  // per-pitch loop at KICK_ALPHA) already sits on. Named callouts for the
  // two grounds the storyboard calls out by name. Amber is correct here —
  // the sun/floodlight is literally the subject (long axes east–west, into
  // the sunset the folklore warns about).
  function ovKicker(w) {
    if (!ST.length || !stPos.length) return;
    for (let i = 0; i < ST.length; i++) {
      const [x, y] = stPos[i];
      drawPitch(ST[i], x, y, FIT.island ? FIT.island.pxPerM : 0, w, AMBER);
    }
    ctx.save(); ctx.globalAlpha = w; ctx.fillStyle = AMBER;
    const semple = ST.findIndex(s => s.name.includes("Semple"));
    const rinn = ST.findIndex(s => s.name.includes("Rinn"));
    if (semple >= 0) {
      const [x, y] = stPos[semple];
      label("Semple 92°", x, y - 14, AMBER, 12, true);
    }
    if (rinn >= 0) {
      const [x, y] = stPos[rinn];
      label("Páirc Uí Rinn 89°", x, y - 14, AMBER, 12, true);
    }
    // TODO(author): final wording — one amber label line, per the storyboard.
    label("the 29 county grounds — long axes east–west, into the sunset",
      VW / 2, VH - 26, AMBER, 14, true);
    ctx.restore();
  }

  // overlay owner scene index -> fn (2, 4 and 7 are dispatched specially below)
  const OVERLAYS = { 0: ovProtagonist, 2: ovMirror, 3: ovSoccer,
                     4: ovTownCountry, 5: ovDublin, 6: ovCavan, 7: ovSun,
                     8: ovKicker };

  // ---------- scroll + draw: CARD-DRIVEN pacing (gate-fail fix #1) ----------
  // The old model divided the .scrolly element's total scroll distance into
  // N-1 UNIFORM segments — it never looked at where the .step cards actually
  // sit, and the CSS step heights are not uniform (60vh / 150vh x6 / 190vh),
  // so segment boundaries and card boundaries drifted apart, worse further
  // down the page. Replaced: each transition is now driven by the live
  // getBoundingClientRect() of its OWN destination card.
  const ease = t => t < .5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2;
  // .steps lives inside BOTH sticky stages; this selector picks up all 9
  // cards, across both, in document order — index === scene index (0..8).
  // Extending to a second stage needed no change here at all.
  const cardEls = Array.from(document.querySelectorAll(".steps .card"));

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
    for (let i = 1; i <= N - 1; i++) reveal[i] = cardEls[i]
      ? revealOf(cardEls[i], arrivePx) : 1;
    let settled = 0;
    while (settled < N - 1 && reveal[settled + 1] >= 1) settled++;
    const a = Math.min(N - 2, settled);
    const tau = reveal[a + 1];
    const t = reduced ? Math.round(tau) : ease(tau);
    return { a, tau, t };
  }

  let CUR = new Float32Array(P.length * 4);

  // Draws the current shared scene state into whichever canvas `ctx`
  // currently points at. draw() (below) sets `ctx` and calls this once per
  // registered canvas — only one is ever actually sticky/visible at a given
  // scroll position, but rendering to both is cheap and keeps this function
  // (and everything it calls) completely unaware there are two stages.
  function renderFrame() {
    const { a, tau, t } = sceneState();
    const A = S[a], B = S[a + 1];
    // Dublin(5)/Cavan(6) render with the min-length symbolic stroke whenever
    // either scene is the source or destination of the current transition —
    // covers arriving at 5, holding 5, 5->6, holding 6, and departing 6.
    const symbolic = (a === 4 || a === 5 || a === 6);

    ctx.clearRect(0, 0, VW, VH);

    // backdrops UNDER the cast: coast + county borders on the map scenes
    let ow;
    if ((ow = outlineWeight(1, a, t)) > 0.02) drawOutlines(FIT.island, ow);
    if ((ow = outlineWeight(5, a, t)) > 0.02) drawOutlines(FIT.dublin, ow);
    if ((ow = outlineWeight(6, a, t)) > 0.02) drawOutlines(FIT.cavan, ow);

    for (let i = 0; i < P.length; i++) {
      const j = i * 4;
      const x = A[j] + (B[j] - A[j]) * t;
      const y = A[j + 1] + (B[j + 1] - A[j + 1]) * t;
      const s = A[j + 2] + (B[j + 2] - A[j + 2]) * t;
      const al = A[j + 3] + (B[j + 3] - A[j + 3]) * t;
      CUR[j] = x; CUR[j + 1] = y; CUR[j + 2] = s; CUR[j + 3] = al;
      if (al < 0.02) continue;
      if (symbolic) drawPitchSymbolic(P[i], x, y, s, al);
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
      const w = a === i - 1 ? t : (a === i ? 1 - t : 0);
      if (w <= 0.02) continue;
      if (i === 2) {
        // rose mirror gated to the hold plateau on arrival (kills the mid-morph
        // smear: the cast is settled before the mirror draws). Cuts if reduced.
        const gate = (reduced || a !== 1) ? 1
          : Math.max(0, Math.min(1, (tau - 0.82) / 0.18));
        ovMirror(w * gate, CUR);
      } else if (i === 4) {
        // petal-rose ghosts: same settle gate, same reason (item 2's ghosts
        // are a full copy of the moving cast too — avoid reintroducing the
        // scene-2 smear in a new spot).
        const gate = (reduced || a !== 3) ? 1
          : Math.max(0, Math.min(1, (tau - 0.82) / 0.18));
        ovTownCountry(w * gate, CUR);
      } else if (i === 7) {
        // sun sweep bound to the same model: sweeps as the scene settles, holds
        const sweepT = reduced ? t : (a === 6 ? tau : 1);
        ovSun(w, sweepT);
      } else {
        OVERLAYS[i](w);
      }
    }
  }

  function draw() {
    if (!S.length || !cardEls.length) return;
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
      // wider hit target in the Dublin/Cavan close-ups (item 7)
      const { a: tapA, t: tapT } = sceneState();
      const scene = tapT > 0.5 ? tapA + 1 : tapA;
      const rad = (scene === 5 || scene === 6) ? 40 : 26;
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
  function resize() {
    VW = canvases[0].clientWidth; VH = canvases[0].clientHeight;
    canvases.forEach((c, k) => {
      c.width = VW * dpr; c.height = VH * dpr;
      ctxs[k].setTransform(dpr, 0, 0, dpr, 0, 0);
    });
    CUR = new Float32Array(P.length * 4);
    buildScenes(); draw();
  }
  let ticking = false;
  addEventListener("scroll", () => {
    if (!ticking) { ticking = true;
      requestAnimationFrame(() => { draw(); ticking = false; }); }
  }, { passive: true });
  addEventListener("resize", resize);

  Promise.all([
    fetch("data/cast.json").then(r => r.json()),
    fetch("data/soccer_bearings.json").then(r => r.json()),
    fetch("data/outlines.json").then(r => r.json()),
    fetch("data/stadiums.json").then(r => r.json()),
  ]).then(([castJson, soccerJson, outlinesJson, stadiumsJson]) => {
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

    const sf = stadiumsJson.fields;
    const sbi = sf.indexOf("bearing"), sli = sf.indexOf("L"), swi = sf.indexOf("W"),
          sni = sf.indexOf("name"), slati = sf.indexOf("lat"), sloni = sf.indexOf("lon");
    ST = stadiumsJson.data.map(rec => {
      const [x, y] = toXY(rec[slati], rec[sloni]);
      return { b: rec[sbi], L: rec[sli], W: rec[swi], name: rec[sni], gx: x, gy: y };
    });

    resize();
  }).catch(err => {
    console.error("stage data load failed", err);
    document.querySelectorAll(".stage").forEach(s => s.classList.add("stage--failed"));
  });
})();
