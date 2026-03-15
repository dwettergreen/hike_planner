# Hike Planner

A browser-based, multi-night hiking itinerary planner. Currently configured for the **Long Trail, Vermont**.

Live tool: https://dwettergreen.github.io/hike_planner/

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

## Self-configuring mile markers
Add `startMile` and `endMile` to `trail.geojson` properties and the tool
reads them automatically at load time — no need to edit index.html constants.

## Local development
```bash
cd hike_planner
python3 -m http.server 8000
# Open http://localhost:8000
```

---
Vibe coded with Claude · March 2026
