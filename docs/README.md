# Pitch Compass — site

This folder is the published article: plain HTML, CSS and JS with no build step, no framework and no CDN loads (fonts and all data are vendored locally). To publish, enable GitHub Pages with **Source: Deploy from a branch → Branch: `main` → Folder: `/docs`**; GitHub then serves this directory at the site root with no Actions workflow. For local development, run `python3 -m http.server` from inside `docs/` and open `http://localhost:8000`.

## Contents

- `index.html`, `css/style.css`, `js/dashmap.js` — the page and the canvas dash-map.
- `data/` — lean JSONs precomputed by `../exploration/make_site_data.py` from the frozen exploration outputs. Never hand-edit; regenerate with `python3 exploration/make_site_data.py` from the repo root.
- `fonts/` — self-hosted OFL fonts (Source Serif 4, Fraunces, IBM Plex Mono) with each family's `OFL.txt`.

Data © OpenStreetMap contributors (ODbL 1.0). County boundaries: Tailte Éireann (CC-BY 4.0) and OSNI (UK OGL).
