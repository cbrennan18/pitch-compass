/* Pitch Compass — the floodlit stage engine (Stage 2B-i: Acts 1–3).
 *
 * One canvas, N scenes. Every pitch holds a per-scene target [x,y,scale,
 * alpha]; scroll drives an eased interpolation between consecutive scenes.
 * Scenes are DESCRIPTORS with an optional overlay(ctx, w, t) hook — the
 * rose mirror, the soccer guest rose, the sun sweep and the on-canvas
 * labels are overlays, not special-cased scene indices. This generalises
 * the v4 prototype's hand-wired mW/sunW/kickW dispatch.
 *
 * Scenes (Acts 1–3):
 *   0 protagonist · 1 island · 2 rose · 3 soccer guest · 4 town/country
 *   5 Dublin · 6 Cavan–Monaghan · 7 rose + sun sweep
 *
 * Chalk on grass; amber is semantic (the sun only). Data © OpenStreetMap
 * contributors (ODbL 1.0); see /data and the methods box.
 */
(() => {
  "use strict";
  const cv = document.getElementById("cv");
  if (!cv) return;
  const ctx = cv.getContext("2d");
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const CHALK = "#f4f1e4", AMBER = "#e8a13d";
  const CHALK_FAINT = "rgba(244,241,228,.62)";
  const SERIF = "Charter, Georgia, 'Times New Roman', serif";

  let VW = 0, VH = 0;
  let P = [];            // pitch objects {b,L,W,name,urban,gx,gy}
  let SOCCER = [];       // soccer guest bearings (numbers)
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
    return { pos: p => [ox + (p.gx - x0) * s, oy + (p.gy - y0) * s],
             pxPerM: s / 111320 };
  }

  // deterministic per-pitch jitter in [0,1)
  const hash = (i, salt) => ((i * 2654435761 + salt * 40503) >>> 16 & 255) / 255;

  // ---------- scene target arrays ----------
  const N = 8;
  let S = [];            // S[i] = Float32Array(P.length*4)
  let mirror = null;     // rose fold mirror positions (2 per pitch)
  let soccerRose = null; // precomputed soccer guest rose [x,y] per bearing
  let roseCentre = null; // {cx,cy,R} of the centred rose (for the sun sweep)

  function setTarget(arr, i, x, y, s, a) { arr.set([x, y, s, a], i * 4); }

  function buildScenes() {
    S = Array.from({ length: N }, () => new Float32Array(P.length * 4));

    // 0 — protagonist: the chosen named pitch alone, large; the rest hidden
    const prot = P[protagIdx];
    const psc = Math.min(VW, VH) * 0.5 / prot.L;
    P.forEach((p, i) => setTarget(S[0], i, VW / 2, VH * 0.42,
      p === prot ? psc : 0.02, p === prot ? 1 : 0));

    // 1 — island: the cast draws Ireland unaided (no outlines)
    const isl = fitter(51.35, 55.45, -10.6, -5.4, 24);
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

    // 4 — town / country: two loose piles, drawn at true bearing. The town
    //     pile reads more N–S/E–W because it genuinely is (46% vs 36% cardinal).
    const tc = { x: VW * 0.30, y: VH * 0.54 }, cc = { x: VW * 0.70, y: VH * 0.54 };
    const spread = Math.min(VW, VH) * 0.20;
    P.forEach((p, i) => {
      const c = p.urban ? tc : cc;
      const ang = hash(i, 2) * 2 * Math.PI, rad = spread * Math.sqrt(hash(i, 3));
      setTarget(S[4], i, c.x + rad * Math.cos(ang), c.y + rad * Math.sin(ang), 0.075, 1);
    });

    // 5 — Dublin close-up (street grid); 6 — Cavan–Monaghan (drumlin comb)
    const dub = fitter(53.20, 53.45, -6.45, -6.05, 30);
    P.forEach((p, i) => { const [x, y] = dub.pos(p);
      setTarget(S[5], i, x, y, dub.pxPerM, 1); });
    const cav = fitter(53.85, 54.45, -7.65, -6.65, 30);
    P.forEach((p, i) => { const [x, y] = cav.pos(p);
      setTarget(S[6], i, x, y, cav.pxPerM, 1); });

    // 7 — rose again, re-centred, for the sun sweep (mirror off)
    P.forEach((p, i) => S[7].set(S[2].subarray(i * 4, i * 4 + 4), i * 4));
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

  function label(text, x, y, col, size, italic) {
    ctx.fillStyle = col || CHALK;
    ctx.font = (italic === false ? "" : "italic ") + (size || 15) + "px " + SERIF;
    ctx.textAlign = "center";
    ctx.fillText(text, x, y);
  }

  // ---------- overlays, keyed to their owning scene ----------
  // Each returns nothing; called with weight w in (0,1] and local ease t.
  function ovProtagonist(w) {
    const p = P[protagIdx];
    ctx.save(); ctx.globalAlpha = w;
    label(p.name || "Unnamed", VW / 2,
      VH * 0.42 + Math.min(VW, VH) * 0.31, CHALK, 15);
    label(p.L + " m × " + p.W + " m · bearing " + p.b + "°", VW / 2,
      VH * 0.42 + Math.min(VW, VH) * 0.31 + 22, CHALK_FAINT, 13);
    ctx.restore();
  }
  function ovMirror(w, cur) {
    for (let i = 0; i < P.length; i++) {
      drawPitch(P[i], mirror[i * 2], mirror[i * 2 + 1], 0.09,
        cur[i * 4 + 3] * w * 0.7, CHALK);
    }
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
    ctx.globalAlpha = w;
    label("2,458 soccer pitches — the same round disc", VW / 2, VH - 26,
      CHALK_FAINT, 14);
    ctx.restore();
  }
  function ovPiles(w) {
    ctx.save(); ctx.globalAlpha = w;
    label("town", VW * 0.30, VH * 0.54 - Math.min(VW, VH) * 0.24, CHALK, 16);
    label("country", VW * 0.70, VH * 0.54 - Math.min(VW, VH) * 0.24, CHALK, 16);
    ctx.restore();
  }
  function ovDublin(w) {
    ctx.save(); ctx.globalAlpha = w;
    label("Dublin — north–south, east–west", VW / 2, VH * 0.12, CHALK, 15);
    ctx.restore();
  }
  function ovCavan(w) {
    ctx.save(); ctx.globalAlpha = w;
    label("Cavan–Monaghan — combed NE–SW", VW / 2, VH * 0.12, CHALK, 15);
    ctx.restore();
  }
  function ovSun(w, t) {
    if (!roseCentre) return;
    const az = 228 + (311.8 - 228) * Math.min(1, t);   // winter -> June sunset
    const { cx, cy } = roseCentre, R = Math.min(VW, VH) * 0.46;
    const a = (az - 90) * Math.PI / 180;
    ctx.save(); ctx.globalAlpha = w; ctx.strokeStyle = AMBER; ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(cx - R * Math.cos(a), cy - R * Math.sin(a));
    ctx.lineTo(cx + R * Math.cos(a), cy + R * Math.sin(a));
    ctx.stroke();
    ctx.fillStyle = AMBER;
    ctx.beginPath();
    ctx.arc(cx + R * Math.cos(a), cy + R * Math.sin(a), 7, 0, 7); ctx.fill();
    label(t >= 1 ? "June sunset · 311.8°" : "sunset, by season",
      cx + R * Math.cos(a), cy + R * Math.sin(a) - 14, AMBER, 14);
    ctx.restore();
  }

  // overlay owner scene index -> fn
  const OVERLAYS = { 0: ovProtagonist, 2: ovMirror, 3: ovSoccer,
                     4: ovPiles, 5: ovDublin, 6: ovCavan, 7: ovSun };

  // ---------- scroll + draw ----------
  const scrolly = document.querySelector(".scrolly");
  const ease = t => t < .5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2;
  function progress() {
    const r = scrolly.getBoundingClientRect();
    return Math.max(0, Math.min(1, -r.top / (r.height - VH)));
  }

  let CUR = new Float32Array(P.length * 4);

  function draw() {
    if (!S.length) return;
    const p = progress() * (N - 1);
    const a = Math.min(N - 2, Math.floor(p));
    const raw = p - a;
    const t = reduced ? Math.round(raw) : ease(raw);
    const A = S[a], B = S[a + 1];

    ctx.clearRect(0, 0, VW, VH);
    for (let i = 0; i < P.length; i++) {
      const j = i * 4;
      const x = A[j] + (B[j] - A[j]) * t;
      const y = A[j + 1] + (B[j + 1] - A[j + 1]) * t;
      const s = A[j + 2] + (B[j + 2] - A[j + 2]) * t;
      const al = A[j + 3] + (B[j + 3] - A[j + 3]) * t;
      CUR[j] = x; CUR[j + 1] = y; CUR[j + 2] = s; CUR[j + 3] = al;
      if (al < 0.02) continue;
      drawPitch(P[i], x, y, s, al, CHALK);
    }

    // overlays: triangular weight around the owning scene
    for (const key in OVERLAYS) {
      const i = +key;
      const w = a === i - 1 ? t : (a === i ? 1 - t : 0);
      if (w > 0.02) {
        // local progress within the owning scene's arrival (for the sun sweep)
        const local = a === i - 1 ? t : 1;
        OVERLAYS[i](w, i === 2 ? CUR : local);
      }
    }
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
    cv.addEventListener("click", e => {
      const r = cv.getBoundingClientRect();
      const mx = e.clientX - r.left, my = e.clientY - r.top;
      let best = -1, bd = 26 * 26;
      for (let i = 0; i < P.length; i++) {
        if (CUR[i * 4 + 3] < 0.2) continue;
        const dx = CUR[i * 4] - mx, dy = CUR[i * 4 + 1] - my, d = dx * dx + dy * dy;
        if (d < bd) { bd = d; best = i; }
      }
      if (best < 0) { sheet.classList.remove("open"); return; }
      openSheet(P[best]);
    });
    sheet.querySelector(".close").onclick = () => sheet.classList.remove("open");
  }

  // ---------- boot ----------
  function resize() {
    VW = cv.clientWidth; VH = cv.clientHeight;
    cv.width = VW * dpr; cv.height = VH * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
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
  ]).then(([castJson, soccerJson]) => {
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
    resize();
  }).catch(err => {
    console.error("stage data load failed", err);
    const s = cv.closest(".stage");
    if (s) s.classList.add("stage--failed");
  });
})();
