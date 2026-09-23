/* Pitch Compass — the free explorer (Stage 2C).
 *
 * Independent of the sticky stage engine (docs/js/stage.js): no scroll-
 * driven scenes here, just a pan/zoom camera over the same cast + outlines
 * data. Self-contained on purpose — a separate script, its own fetches, its
 * own small copy of the pitch LOD renderer — so the two engines never have
 * to coordinate load order or share mutable state.
 *
 * Interaction model (per the Stage 2 reflection): pinch is ALWAYS live,
 * regardless of "Explore" mode, because a two-finger touch never collides
 * with page scroll. One-finger drag-pan and mouse-wheel zoom are gated
 * behind an explicit "Explore ▸ / Done" toggle, which also flips the
 * canvas's touch-action so the page scrolls straight through when the
 * toggle is off. Tap-to-inspect works either way. Desktop/no-touch gets
 * +/− /reset buttons and arrow-key panning — never touch-only.
 *
 * Chalk on grass; no amber here (the sun isn't the subject in this stage).
 */
(() => {
  "use strict";
  const cv = document.getElementById("ex-canvas");
  if (!cv) return;
  const ctx = cv.getContext("2d");
  const frame = document.getElementById("explorer-frame");
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  // No canvas text in the explorer — the county stat line is a DOM element
  // (#county-stat), more accessible than baking it into the canvas — so
  // only the stroke colour is needed here, not a font stack.
  const CHALK = "#f4f1e4";

  let VW = 0, VH = 0;
  let P = [];            // pitch objects {b,L,W,name,county,gx,gy}
  let OUTLINES = null;
  let COUNTY_STATS = {}; // name -> {n,R4,mean_axis,cardinal_pct,low_n}
  let filterCounty = "";

  const K = Math.cos(53.4 * Math.PI / 180);
  const toXY = (lat, lon) => [lon * K, -lat];

  // ---------- camera: world units (toXY space) <-> screen pixels ----------
  let baseScale = 1;   // world-unit -> px at zoom 1 (fits the whole island)
  let bboxCentre = { x: 0, y: 0 };
  let camera = { x: 0, y: 0, zoom: 1 };
  let cameraInit = false;
  const ZOOM_MIN = 1;
  let ZOOM_MAX = 40;    // recomputed once data loads (target ~1.3 px/metre)

  function worldToScreen(wx, wy) {
    const s = baseScale * camera.zoom;
    return [VW / 2 + (wx - camera.x) * s, VH / 2 + (wy - camera.y) * s];
  }
  function screenToWorld(sx, sy) {
    const s = baseScale * camera.zoom;
    return [(sx - VW / 2) / s + camera.x, (sy - VH / 2) / s + camera.y];
  }
  function llToScreen(lon, lat) {
    const [wx, wy] = toXY(lat, lon);
    return worldToScreen(wx, wy);
  }
  function clampZoom(z) { return Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, z)); }
  // keep the world point under `screen` fixed on screen while zooming
  function zoomAt(screen, newZoom) {
    const before = screenToWorld(screen.x, screen.y);
    camera.zoom = clampZoom(newZoom);
    const after = screenToWorld(screen.x, screen.y);
    camera.x += before[0] - after[0];
    camera.y += before[1] - after[1];
    clampPan();
  }
  function panByPixels(dx, dy) {
    const s = baseScale * camera.zoom;
    camera.x -= dx / s; camera.y -= dy / s;
    clampPan();
  }
  // loose clamp so the reader can't scroll the cast off into blank grass —
  // keeps at least a quarter of the island's extent reachable from centre
  function clampPan() {
    if (!OUTLINES) return;
    const [minlon, minlat, maxlon, maxlat] = OUTLINES.bbox;
    const [x0, y0] = toXY(minlat, minlon), [x1, y1] = toXY(maxlat, maxlon);
    const mx = (Math.max(x0, x1) - Math.min(x0, x1)) * 0.6;
    const my = (Math.max(y0, y1) - Math.min(y0, y1)) * 0.6;
    camera.x = Math.max(Math.min(x0, x1) - mx, Math.min(Math.max(x0, x1) + mx, camera.x));
    camera.y = Math.max(Math.min(y0, y1) - my, Math.min(Math.max(y0, y1) + my, camera.y));
  }

  function fitBBox(minlon, minlat, maxlon, maxlat, padFrac) {
    const [x0, y0] = toXY(maxlat, minlon), [x1, y1] = toXY(minlat, maxlon);
    const w = Math.abs(x1 - x0), h = Math.abs(y1 - y0);
    const pad = 1 + (padFrac || 0.14);
    const s = Math.min(VW / (w * pad), VH / (h * pad));
    return { cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, zoom: clampZoom(s / baseScale) };
  }

  let animId = null;
  function flyTo(target, instant) {
    if (animId) cancelAnimationFrame(animId);
    if (instant || reduced) {   // no zoom tweens under reduced motion
      camera.x = target.cx; camera.y = target.cy; camera.zoom = target.zoom;
      clampPan(); draw();
      return;
    }
    const from = { x: camera.x, y: camera.y, zoom: camera.zoom };
    const dur = 380, t0 = performance.now();
    const ease = t => t < .5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2;
    (function step(now) {
      const t = Math.min(1, (now - t0) / dur), e = ease(t);
      camera.x = from.x + (target.cx - from.x) * e;
      camera.y = from.y + (target.cy - from.y) * e;
      camera.zoom = from.zoom + (target.zoom - from.zoom) * e;
      clampPan(); draw();
      if (t < 1) animId = requestAnimationFrame(step); else animId = null;
    })(t0);
  }

  // ---------- pitch renderer: symbolic floor -> true rect -> markings ----
  // Reuses the close-ups' floored-stroke convention (stage.js gate-fail
  // fix #3) at low zoom, and the original engine's true-scale LOD ladder
  // (stroke -> rect -> halfway/20m lines) as the reader zooms toward a
  // single real pitch — "see its actual shape" falls out of one continuous
  // renderer, not a mode switch the reader has to notice.
  //
  // Device-gate fix #5: the floor used to be a FLAT 18px regardless of
  // zoom — right for the close-ups (a fixed frame), wrong for a zoomable
  // island view, where 2,707 flat-18px strokes at zoom-out overlap into a
  // hairball. The floor now SCALES with zoom: near-invisible short ticks
  // (a clean point-cloud) at ZOOM_MIN, ramping up to the same 18px close-up
  // convention by FLOOR_RAMP_ZOOM — beyond which true scale naturally takes
  // over anyway as the reader keeps zooming in.
  const MIN_FLOOR_LOW = 2.5, MIN_FLOOR_HIGH = 18, FLOOR_RAMP_ZOOM = 8;
  function strokeFloorPx(zoom) {
    const t = Math.max(0, Math.min(1, (zoom - ZOOM_MIN) / (FLOOR_RAMP_ZOOM - ZOOM_MIN)));
    return MIN_FLOOR_LOW + (MIN_FLOOR_HIGH - MIN_FLOOR_LOW) * t;
  }
  function renderPitch(p, x, y, s, alpha, floorPx) {
    const l = p.L * s, w = p.W * s;
    ctx.save(); ctx.translate(x, y); ctx.rotate(p.b * Math.PI / 180);
    ctx.strokeStyle = CHALK;
    if (l < floorPx) {
      ctx.globalAlpha = alpha * 0.6; ctx.lineWidth = 1;
      const fl = Math.max(l, floorPx);
      ctx.beginPath(); ctx.moveTo(0, -fl / 2); ctx.lineTo(0, fl / 2); ctx.stroke();
    } else {
      ctx.globalAlpha = alpha; ctx.lineWidth = Math.min(1.5, .8 + l / 220);
      ctx.strokeRect(-w / 2, -l / 2, w, l);
      if (l > 56) {
        ctx.globalAlpha = alpha * .35;
        ctx.beginPath(); ctx.moveTo(-w / 2, 0); ctx.lineTo(w / 2, 0); ctx.stroke();
        if (l > 140) {
          const q = l * (20 / 145);
          ctx.beginPath();
          ctx.moveTo(-w / 2, -l / 2 + q); ctx.lineTo(w / 2, -l / 2 + q);
          ctx.moveTo(-w / 2, l / 2 - q); ctx.lineTo(w / 2, l / 2 - q); ctx.stroke();
        }
      }
    }
    ctx.restore();
  }

  function strokePaths(paths, w) {
    ctx.beginPath();
    for (const path of paths) {
      for (let k = 0; k < path.length; k++) {
        const [x, y] = llToScreen(path[k][0], path[k][1]);
        k ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
      }
    }
    ctx.strokeStyle = CHALK; ctx.globalAlpha = w; ctx.lineWidth = 1;
    ctx.stroke();
  }

  const DIM_ALPHA = 0.15;   // non-selected-county pitches, when a county is chosen
  let CUR = new Float32Array(0);   // last-rendered screen positions, for tap hit-testing

  function draw() {
    if (!P.length) return;
    ctx.clearRect(0, 0, VW, VH);
    if (OUTLINES) {
      ctx.save();
      strokePaths(OUTLINES.borders, 0.22);
      strokePaths(OUTLINES.coast, 0.42);
      ctx.restore();
    }
    // world units are toXY's cos(lat)-scaled degrees, not metres — convert
    // world-scale to px-per-metre the same way stage.js's fitter does
    const pxPerM = (baseScale * camera.zoom) / 111320;
    const floorPx = strokeFloorPx(camera.zoom);   // device-gate fix #5
    for (let i = 0; i < P.length; i++) {
      const p = P[i];
      const [x, y] = worldToScreen(p.gx, p.gy);
      if (x < -40 || x > VW + 40 || y < -40 || y > VH + 40) { CUR[i * 2] = -9999; continue; }
      const alpha = (filterCounty && p.county !== filterCounty) ? DIM_ALPHA : 1;
      CUR[i * 2] = x; CUR[i * 2 + 1] = y;
      renderPitch(p, x, y, pxPerM, alpha, floorPx);
    }
  }

  // ---------- tap-a-pitch sheet (shared DOM with the stage) ----------
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
  function tapAt(sx, sy) {
    let best = -1, bd = 22 * 22;
    for (let i = 0; i < P.length; i++) {
      const x = CUR[i * 2]; if (x < -1000) continue;
      const dx = x - sx, dy = CUR[i * 2 + 1] - sy, d = dx * dx + dy * dy;
      if (d < bd) { bd = d; best = i; }
    }
    if (best < 0) { sheet.classList.remove("open"); return; }
    openSheet(P[best]);
  }
  if (sheet) sheet.querySelector(".close").onclick = () => sheet.classList.remove("open");

  // ---------- pan / pinch / wheel / keyboard ----------
  let exploring = false;
  const toggleBtn = document.getElementById("ex-toggle");
  function setExploring(v) {
    exploring = v;
    frame.classList.toggle("exploring", v);
    toggleBtn.classList.toggle("active", v);
    toggleBtn.setAttribute("aria-pressed", String(v));
    toggleBtn.textContent = v ? "Done" : "Explore ▸";
  }
  toggleBtn.addEventListener("click", () => setExploring(!exploring));

  const pointers = new Map();
  let pinch = null;      // {dist, mid, zoom0}
  let drag = null;       // {x,y}
  let tap = null;        // {x,y,t,moved}
  function dist(a, b) { return Math.hypot(a.x - b.x, a.y - b.y); }
  function mid(a, b) { return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }; }

  cv.addEventListener("pointerdown", e => {
    cv.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    tap = { x: e.clientX, y: e.clientY, t: performance.now(), moved: false };
    if (pointers.size === 2) {
      const pts = [...pointers.values()];
      pinch = { dist: dist(pts[0], pts[1]), mid: mid(pts[0], pts[1]), zoom0: camera.zoom };
      drag = null;
    } else if (pointers.size === 1 && exploring) {
      const r = cv.getBoundingClientRect();
      drag = { x: e.clientX - r.left, y: e.clientY - r.top };
    }
  });
  cv.addEventListener("pointermove", e => {
    if (!pointers.has(e.pointerId)) return;
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (tap && Math.hypot(e.clientX - tap.x, e.clientY - tap.y) > 8) tap.moved = true;
    if (pointers.size === 2 && pinch) {
      e.preventDefault();
      const pts = [...pointers.values()];
      const d = dist(pts[0], pts[1]);
      const m = mid(pts[0], pts[1]);
      const r = cv.getBoundingClientRect();
      zoomAt({ x: m.x - r.left, y: m.y - r.top }, pinch.zoom0 * (d / pinch.dist));
      panByPixels(m.x - pinch.mid.x, m.y - pinch.mid.y);
      pinch.mid = m;
      draw();
    } else if (drag && exploring) {
      e.preventDefault();
      const r = cv.getBoundingClientRect();
      const nx = e.clientX - r.left, ny = e.clientY - r.top;
      panByPixels(nx - drag.x, ny - drag.y);
      drag = { x: nx, y: ny };
      draw();
    }
  });
  function endPointer(e) {
    pointers.delete(e.pointerId);
    if (pointers.size < 2) pinch = null;
    if (pointers.size === 0) {
      if (tap && !tap.moved && performance.now() - tap.t < 500) {
        const r = cv.getBoundingClientRect();
        tapAt(tap.x - r.left, tap.y - r.top);
      }
      tap = null; drag = null;
    }
  }
  cv.addEventListener("pointerup", endPointer);
  cv.addEventListener("pointercancel", endPointer);

  // wheel zoom — gated: outside "Explore" mode the page scrolls normally
  cv.addEventListener("wheel", e => {
    if (!exploring) return;
    e.preventDefault();
    const r = cv.getBoundingClientRect();
    const factor = Math.exp(-e.deltaY * 0.001);
    zoomAt({ x: e.clientX - r.left, y: e.clientY - r.top }, camera.zoom * factor);
    draw();
  }, { passive: false });

  // buttons: always active, not gated — the accessible/no-touch fallback
  document.getElementById("ex-zoom-in").addEventListener("click", () => {
    zoomAt({ x: VW / 2, y: VH / 2 }, camera.zoom * 1.4); draw();
  });
  document.getElementById("ex-zoom-out").addEventListener("click", () => {
    zoomAt({ x: VW / 2, y: VH / 2 }, camera.zoom / 1.4); draw();
  });
  document.getElementById("ex-reset").addEventListener("click", () => resetView());

  // keyboard: arrow-pan, +/-/0 zoom, when the canvas has focus
  cv.tabIndex = 0;
  cv.addEventListener("keydown", e => {
    const step = 50 / camera.zoom;
    if (e.key === "ArrowLeft") { panByPixels(step, 0); draw(); e.preventDefault(); }
    else if (e.key === "ArrowRight") { panByPixels(-step, 0); draw(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { panByPixels(0, step); draw(); e.preventDefault(); }
    else if (e.key === "ArrowDown") { panByPixels(0, -step); draw(); e.preventDefault(); }
    else if (e.key === "+" || e.key === "=") {
      zoomAt({ x: VW / 2, y: VH / 2 }, camera.zoom * 1.3); draw(); e.preventDefault();
    } else if (e.key === "-" || e.key === "_") {
      zoomAt({ x: VW / 2, y: VH / 2 }, camera.zoom / 1.3); draw(); e.preventDefault();
    } else if (e.key === "0") { resetView(); e.preventDefault(); }
  });

  // ---------- county filter ----------
  const statEl = document.getElementById("county-stat");
  const countySel = document.getElementById("ex-county");
  function resetView() {
    filterCounty = ""; countySel.value = "";
    statEl.innerHTML = "";
    flyTo({ cx: bboxCentre.x, cy: bboxCentre.y, zoom: ZOOM_MIN });
  }
  countySel.addEventListener("change", () => {
    const name = countySel.value;
    if (!name) { resetView(); return; }
    filterCounty = name;
    const bb = OUTLINES.counties[name];
    if (bb) {
      const t = fitBBox(bb[0], bb[1], bb[2], bb[3], 0.35);
      flyTo(t);
    } else { draw(); }
    const st = COUNTY_STATS[name];
    if (st) {
      const axis = st.R4 < 0.05 ? "—" : Math.round(st.mean_axis) + "°";
      let html = `<b>${name}</b> · n = <b>${st.n}</b> · R₄ = <b>${st.R4.toFixed(2)}</b> `
        + `· mean axis <b>${axis}</b> · cardinal <b>${Math.round(st.cardinal_pct)}%</b>`;
      if (st.low_n) {
        html += ` <span class="honesty">— n = ${st.n}, treat as a story, not a verdict.</span>`;
      }
      statEl.innerHTML = html;
    } else {
      statEl.textContent = "";
    }
  });

  // ---------- boot ----------
  function resize() {
    VW = cv.clientWidth; VH = cv.clientHeight;
    cv.width = VW * dpr; cv.height = VH * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    if (OUTLINES) {
      const [minlon, minlat, maxlon, maxlat] = OUTLINES.bbox;
      const [x0, y0] = toXY(maxlat, minlon), [x1, y1] = toXY(minlat, maxlon);
      const w = Math.abs(x1 - x0), h = Math.abs(y1 - y0);
      baseScale = Math.min(VW / (w * 1.14), VH / (h * 1.14));
      bboxCentre = { x: (x0 + x1) / 2, y: (y0 + y1) / 2 };
      // target ~1.3 px/metre at max zoom so a real pitch (~150m) renders
      // at a legible, roughly-true-shape size
      const TARGET_PXPERM = 1.3;
      const basePxPerM = baseScale / 111320;
      ZOOM_MAX = Math.max(ZOOM_MIN, TARGET_PXPERM / basePxPerM);
      if (!cameraInit) {
        camera = { x: bboxCentre.x, y: bboxCentre.y, zoom: 1 };
        cameraInit = true;
      }
    }
    draw();
  }
  addEventListener("resize", resize);

  Promise.all([
    fetch("data/cast.json").then(r => r.json()),
    fetch("data/outlines.json").then(r => r.json()),
    fetch("data/county_stats.json").then(r => r.json()),
  ]).then(([castJson, outlinesJson, statsJson]) => {
    const f = castJson.fields;
    const bi = f.indexOf("bearing"), li = f.indexOf("L"), wi = f.indexOf("W"),
          ni = f.indexOf("name"), ci = f.indexOf("county"),
          lati = f.indexOf("lat"), loni = f.indexOf("lon");
    P = castJson.data.map(rec => {
      const [x, y] = toXY(rec[lati], rec[loni]);
      return { b: rec[bi], L: rec[li], W: rec[wi], name: rec[ni], county: rec[ci], gx: x, gy: y };
    });
    CUR = new Float32Array(P.length * 2);
    OUTLINES = outlinesJson;
    statsJson.forEach(c => { COUNTY_STATS[c.county] = c; });
    resize();
  }).catch(err => {
    console.error("explorer data load failed", err);
    frame.innerHTML = '<p class="explorer__noscript">The explorer could not load its data. '
      + 'The county book below has the same numbers, statically.</p>';
  });
})();
