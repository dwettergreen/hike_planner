# Hike Planner

A browser-based, multi-night hiking itinerary planner. Currently configured for the **Long Trail, Vermont**.

Live tool: https://dwettergreen.github.io/hike_planner/

## How it works
- Loads trail geometry from `data/trail.geojson`
- Loads campsite/shelter data from `data/campsites.json`
- Restores a saved plan from `data/plan.json` (if present)
- Runs a dynamic-programming optimizer to suggest daily camp stops
- Runs entirely in the browser — no server required

## File structure
```
hike_planner/
├── index.html              — full application (HTML + CSS + JS)
├── data/
│   ├── trail.geojson       — trail polyline (LineString or MultiLineString)
│   ├── campsites.json      — shelter/campsite list with trailDist values
│   └── plan.json           — saved itinerary (edit via Export tab)
└── README.md
```

## Local development
Because the app uses `fetch()` to load data files, open via a local server rather than `file://`:
```bash
cd hike_planner
python3 -m http.server 8000
# Then open http://localhost:8000
```

## Adding a new trail
Replace `data/trail.geojson` and `data/campsites.json` with data for the new trail,
then update the constants at the top of the `<script>` block in `index.html`:
- `START_MILE`, `END_MILE`
- `END_TRAIL_DIST`
- `BASELINE_MELT_DOY`
- `TERMINUS` (name, lat, lon, elev, mile)
- `MOSQ_BASE` bands (recalibrate for target climate)

See `PCT_WA_Planner_Technical_Design.docx` Section 11 for full details.

---
Vibe coded with Claude · March 2026
