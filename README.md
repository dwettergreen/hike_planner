# Hike Planner

A browser-based, multi-night thru-hiking itinerary planner. Supports multiple trails via a dropdown selector. Currently configured for:

- **Long Trail, Vermont** (64 shelters, full trail)
- **PCT Washington** (178 campsites, Bridge of Gods → Northern Terminus)

Live tool: https://dwettergreen.github.io/hike_planner/

---

## How it works

- Loads a trail registry from `registry.json`
- Fetches trail geometry, campsite data, and config from `trails/<trail-id>/`
- Runs a dynamic-programming optimizer to suggest daily camp stops
- Accounts for pace, elevation, mosquito pressure, and date
- Runs entirely in the browser — no server, no API keys

---

## Repository structure

```
hike_planner/
├── index.html              — full application (HTML + CSS + JS, ~92 KB)
├── registry.json           — list of available trails
│
├── trails/
│   ├── long-trail/
│   │   ├── config.json         — trail constants (distances, terminus, mosquito model)
│   │   ├── trail.geojson       — trail polyline (LineString)
│   │   ├── campsites.json      — 64 shelters with coordinates and elevations
│   │   └── plans/
│   │       ├── index.json      — list of saved plans for this trail
│   │       └── *.json          — saved itinerary files
│   │
│   └── pct-wa/
│       ├── config.json
│       ├── trail.geojson
│       ├── campsites.json
│       └── plans/
│           ├── index.json
│           └── *.json
│
└── data/                   — legacy fallback (single-trail mode, backwards compat)
    ├── config.json
    ├── trail.geojson
    └── campsites.json
```

---

## Adding a new trail

1. Create `trails/<trail-id>/` with these four files:

   **`config.json`** — trail-specific constants:
   ```json
   {
     "trailName":        "My Trail",
     "trailAbbrev":      "MT",
     "startMarkerLabel": "Southern Terminus — Start (Mi 0)",
     "defaultStartDate": "2026-07-01",
     "defaultMeltDate":  "2026-06-01",
     "defaultAvgPace":   13,
     "defaultFlexPace":  3,
     "endTrailDist":     500.0,
     "baselineMeltDoy":  152,
     "terminus": { "name": "Northern Terminus", "lat": 0, "lon": 0, "elev": 0, "mile": 500 },
     "mosqBands": [[3000,155,22],[4500,175,20],[99999,207,14]]
   }
   ```

   **`trail.geojson`** — GeoJSON FeatureCollection with a single LineString feature.
   Add `startMile` and `endMile` to `properties` for automatic mile marker configuration:
   ```json
   { "properties": { "name": "My Trail", "startMile": 0, "endMile": 500 } }
   ```
   MultiLineString is also supported — the tool will flatten and sort segments automatically.

   **`campsites.json`** — array of campsite objects. Required fields:
   ```json
   [{ "name": "Camp Name", "mile": 12.5, "trailDist": 12.5,
      "lat": 45.0, "lon": -120.0, "elev": 3500,
      "type": "Established", "water": true, "outhouse": false,
      "source": "manual", "desc": "Optional notes" }]
   ```
   `trailDist` is the GPS arc-length distance from the start (computed via Python data prep — see Section 11 of `PCT_WA_Planner_Technical_Design.docx`).

   **`plans/index.json`** — start with an empty array: `[]`

2. Add one line to `registry.json`:
   ```json
   { "id": "my-trail", "label": "My Trail Name", "path": "trails/my-trail" }
   ```

3. Push to GitHub. The trail appears immediately in the dropdown — no changes to `index.html`.

---

## Saving and restoring plans

From the **Export** tab, click **Save plan.json** to download the current itinerary. To restore it automatically on future loads:

1. Place the file in `trails/<trail-id>/plans/`
2. Add an entry to `trails/<trail-id>/plans/index.json`:
   ```json
   [{ "file": "my-plan-20260701.json", "label": "Jul 2026 · 13 mpd" }]
   ```
3. Push to GitHub. The plan appears in the plan selector dropdown next to the trail selector.

The plan file captures pace settings, start date, snowmelt date, and all camp overrides. Plans are matched by `trailDist` proximity so they survive minor campsite list updates.

---

## URL bookmarking

The tool encodes the active trail in the URL hash:
```
https://dwettergreen.github.io/hike_planner/#trail=long-trail
https://dwettergreen.github.io/hike_planner/#trail=pct-wa
```
Bookmarks and shared links open directly to the specified trail.

---

## Local development

Because the app uses `fetch()` to load data files, browsers block requests from `file://` URLs. Run a local web server:

```bash
cd hike_planner
python3 -m http.server 8000
# Then open http://localhost:8000
```

---

## Data preparation

The `trailDist` values in `campsites.json` are computed offline using Python (shapely + pandas) from a full-resolution GPS track. See **Section 11** of `PCT_WA_Planner_Technical_Design.docx` for the full data preparation workflow including:
- Flattening MultiLineString segments
- Computing Haversine cumulative arc-length
- Snapping campsite lat/lon to nearest trail point
- Thinning the rendering trail (every 25th–30th point)

Elevation data for Long Trail shelters was fetched from the [Open Elevation API](https://api.open-elevation.com) using shelter coordinates.

---

## Technical design

See `PCT_WA_Planner_Technical_Design.docx` for a complete reference covering architecture, data formats, DP algorithm, all functions, and a catalog of bugs encountered and resolved during development.

---

*Vibe coded with Claude · March 2026*
