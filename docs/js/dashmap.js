/* ==========================================================================
   dashmap.js — the load-bearing visual for Pitch Compass.
   Canvas, no dependencies. Every signal pitch is drawn as a short stroke at
   its playing orientation, on a coastline derived from the county boundaries.
   Projection: equirectangular with a single cos(lat) longitude scaling at the
   reference latitude (53.4 N) — the same distance convention the analysis
   scripts use. Distortion across Ireland's ~4 deg of latitude is invisible at
   this extent.

   Stage 1 behaviour: renders all 2,707 dashes; two preset framings (Dublin,
   Cavan-Monaghan) plus a whole-island default, reachable by buttons, with an
   animated pan/zoom between them. Reduced-motion cuts instantly. No free
   pan/zoom; no touch handlers on the canvas, so page scroll is never captured.

   Data (c) OpenStreetMap contributors, ODbL 1.0. Coastline derived from
   Tailte Eireann (CC-BY 4.0) + OSNI (OGL) boundaries.
   ========================================================================== */
(function () {
  "use strict";

  var canvas = document.getElementById("dashmap-canvas");
  if (!canvas || !canvas.getContext) return;
  var ctx = canvas.getContext("2d");

  var REF_LAT = 53.4;
  var KX = Math.cos(REF_LAT * Math.PI / 180);   // lon -> world-x scaling
  var ASPECT = 900 / 720;                        // canvas h/w (matches markup)

  var reduceMotion = window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // world coords: wx = lon * KX (east +), wy = -lat (north up)
  function wx(lon) { return lon * KX; }
  function wy(lat) { return -lat; }

  var pitches = [];   // [wx, wy, sin(bearing), -cos(bearing)]
  var coast = [];     // array of paths, each [[wx,wy],...]
  var loaded = false;

  var cssW = 0, cssH = 0, dpr = 1;
  var view = null, from = null, to = null, animStart = 0, animId = 0;
  var current = "island";
  var islandView = null;

  // ----- presets (centre lon/lat + vertical span in degrees of latitude) ----
  var PRESETS = {
    dublin:  { lon: -6.27, lat: 53.35, span: 0.62 },
    drumlin: { lon: -7.05, lat: 54.05, span: 1.55 }
  };

  function presetView(p) {
    return { cx: wx(p.lon), cy: wy(p.lat), span: p.span };
  }

  // whole-island view: fit the coast bbox with padding, respecting canvas aspect
  function fitIsland(bbox) {
    var minx = wx(bbox[0]), maxx = wx(bbox[2]);
    var miny = wy(bbox[3]), maxy = wy(bbox[1]);   // note wy flips lat order
    var worldW = maxx - minx, worldH = maxy - miny;
    var pad = 1.10;
    // span (vertical, world-units) must contain both the height and the width
    // scaled by the canvas aspect ratio.
    var span = Math.max(worldH, worldW * ASPECT) * pad;
    return { cx: (minx + maxx) / 2, cy: (miny + maxy) / 2, span: span };
  }

  function project(worldX, worldY, v) {
    var scale = cssH / v.span;                    // css px per world-unit
    return [(worldX - v.cx) * scale + cssW / 2,
            (worldY - v.cy) * scale + cssH / 2];
  }

  function dashHalfLen(v) {
    var scale = cssH / v.span;                     // px per world-unit
    // fixed-ish screen length: a texture at island zoom, distinct when close
    var h = scale * 0.0055;
    return Math.max(2.2, Math.min(7.5, h));
  }

  // ----- drawing --------------------------------------------------------------
  function draw(v) {
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssW, cssH);

    // paper-deep ground
    ctx.fillStyle = "#EFE9DA";
    ctx.fillRect(0, 0, cssW, cssH);

    // coastline — fine ink hairline
    ctx.lineWidth = 1;
    ctx.strokeStyle = "rgba(28,26,23,0.55)";
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.beginPath();
    for (var i = 0; i < coast.length; i++) {
      var path = coast[i];
      for (var j = 0; j < path.length; j++) {
        var p = project(path[j][0], path[j][1], v);
        if (j === 0) ctx.moveTo(p[0], p[1]); else ctx.lineTo(p[0], p[1]);
      }
    }
    ctx.stroke();

    // pitches — each a short ink stroke at its bearing
    var scale = cssH / v.span;
    var h = dashHalfLen(v);
    ctx.lineWidth = 1;
    ctx.strokeStyle = "rgba(28,26,23,0.82)";
    ctx.beginPath();
    for (var k = 0; k < pitches.length; k++) {
      var pt = pitches[k];
      var cx = (pt[0] - v.cx) * scale + cssW / 2;
      var cy = (pt[1] - v.cy) * scale + cssH / 2;
      // cheap cull for the zoomed presets
      if (cx < -20 || cx > cssW + 20 || cy < -20 || cy > cssH + 20) continue;
      var ex = pt[2] * h, ey = pt[3] * h;
      ctx.moveTo(cx - ex, cy - ey);
      ctx.lineTo(cx + ex, cy + ey);
    }
    ctx.stroke();
  }

  // ----- animation ------------------------------------------------------------
  function easeInOut(t) {
    return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  }

  function lerpView(a, b, t) {
    return { cx: a.cx + (b.cx - a.cx) * t,
             cy: a.cy + (b.cy - a.cy) * t,
             span: a.span + (b.span - a.span) * t };
  }

  function animateTo(target) {
    if (!loaded) { view = target; return; }
    if (reduceMotion || !view) { view = target; draw(view); return; }
    from = { cx: view.cx, cy: view.cy, span: view.span };
    to = target;
    animStart = performance.now();
    if (animId) cancelAnimationFrame(animId);
    var DUR = 820;
    function step(now) {
      var t = Math.min(1, (now - animStart) / DUR);
      view = lerpView(from, to, easeInOut(t));
      draw(view);
      if (t < 1) animId = requestAnimationFrame(step);
    }
    animId = requestAnimationFrame(step);
  }

  function viewForCurrent() {
    if (current === "island") return islandView;
    return presetView(PRESETS[current]);
  }

  // ----- sizing (retina-crisp) ------------------------------------------------
  function resize() {
    dpr = Math.max(1, Math.min(3, window.devicePixelRatio || 1));
    cssW = Math.max(240, Math.round(canvas.clientWidth));
    cssH = Math.round(cssW * ASPECT);
    canvas.style.height = cssH + "px";
    canvas.width = Math.round(cssW * dpr);
    canvas.height = Math.round(cssH * dpr);
    if (loaded) {
      view = viewForCurrent();       // snap to current framing at new size
      draw(view);
    }
  }

  // ----- controls -------------------------------------------------------------
  function bindButtons() {
    var btns = document.querySelectorAll(".dashmap__controls .btn");
    Array.prototype.forEach.call(btns, function (btn) {
      btn.addEventListener("click", function () {
        var preset = btn.getAttribute("data-preset");
        if (preset === current) return;
        current = preset;
        Array.prototype.forEach.call(btns, function (b) {
          b.setAttribute("aria-pressed", b === btn ? "true" : "false");
        });
        animateTo(viewForCurrent());
      });
    });
  }

  // If the data can't be loaded, replace the canvas + controls with the same
  // styled placeholder box the page uses everywhere else — never a blank
  // canvas or a console-only error.
  function failGracefully() {
    var container = document.getElementById("dashmap");
    if (!container) return;
    var slot = document.createElement("div");
    slot.className = "plate__slot";
    slot.innerHTML =
      '<div class="plate__placeholder">' +
      '<span class="mark">Fig. 2 · dash-map · data unavailable</span>' +
      '<p class="finding">Every pitch drawn at its true bearing. In Dublin the ' +
      'strokes snap to the street grid; in Cavan&ndash;Monaghan they comb along ' +
      'the drumlins. The interactive map could not load here.</p></div>';
    container.innerHTML = "";
    container.appendChild(slot);
  }

  // ----- load -----------------------------------------------------------------
  Promise.all([
    fetch("data/pitches.json").then(function (r) { return r.json(); }),
    fetch("data/coast.json").then(function (r) { return r.json(); })
  ]).then(function (res) {
    var pdata = res[0], cdata = res[1];
    var f = pdata.fields, iLat = f.indexOf("lat"), iLon = f.indexOf("lon"),
        iB = f.indexOf("bearing");
    pdata.data.forEach(function (row) {
      var b = row[iB] * Math.PI / 180;
      pitches.push([wx(row[iLon]), wy(row[iLat]), Math.sin(b), -Math.cos(b)]);
    });
    coast = cdata.paths.map(function (path) {
      return path.map(function (pt) { return [wx(pt[0]), wy(pt[1])]; });
    });
    islandView = fitIsland(cdata.bbox);
    loaded = true;
    resize();                          // sizes + draws island view
  }).catch(function () {
    failGracefully();
  });

  bindButtons();
  window.addEventListener("resize", resize);
  // initial size so the canvas has dimensions even before data arrives
  resize();
})();
