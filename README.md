# Hike Planner

A browser-based, multi-night thru-hiking itinerary planner. Uses dynamic programming to find the globally optimal camp sequence for a given pace, start date, and bug emergence window. Supports multiple trails via a dropdown selector.

**Currently configured for:**
- **Long Trail, Vermont** — 64 shelters, full 272-mile trail
- **PCT Washington** — 178 campsites, Bridge of Gods to Northern Terminus (505 miles)

**Live tool:** https://dwettergreen.github.io/hike_planner/

---

## How it works

### Itinerary optimization (Dynamic Programming)

The planner finds the **globally optimal** camp sequence — not a greedy night-by-night selection. It runs a forward DP over all candidate campsites, maximizing the sum of campsite scores across all nights subject to a daily distance window.

**Score function:**
```
score = elevation x (1 + 2.0 x (1 - bugPressure))
```
A zero-bug camp scores 3x its elevation; a peak-bug camp scores 1x its elevation. The algorithm rewards high camps and good timing, trading off between them when they conflict.

The DP runs up to six times with progressively wider distance windows (+/-25% through +/-80% of target pace) to guarantee a solution even when campsites are sparse.

### Bug pressure model (V4)

Each trail defines its own multi-species bug model in `config.json`. Each species is a Gaussian bell curve with elevation and water-proximity adjustments:

```
pressure(band) = weight
              x exp(-0.5 x ((doy - peakDoy) / sigma)^2)   seasonal Gaussian
              x exp(-elevDecay x elevation_ft)              exponential elev decay
              x (1 + waterBonus x nearWater)

totalPressure = max(pressure across all bands)             worst pest wins
```

**Why max() not sum():** you care about the worst thing biting you, not a combined count.

**Why exponential elevation decay:** linear decay (1 - k x elev) clamps to zero at typical hiking elevations. Exponential exp(-k x elev) asymptotically approaches zero — real reduction at altitude without eliminating bugs entirely.

The **Emergence date** control shifts all species peak dates by the same offset, modeling late or early bug seasons.

---

## Repository structure

```
hike_planner/
├── index.html              — full application (~92 KB, no build step)
├── registry.json           — list of available trails
├── trails/
│   ├── long-trail/
│   │   ├── config.json         — trail constants + bug model
│   │   ├── trail.geojson       — trail polyline (LineString)
│   │   ├── campsites.json      — 64 shelters with coordinates, elevations
│   │   └── plans/
│   │       ├── index.json      — manifest of saved plans
│   │       └── *.json          — saved itineraries
│   └── pct-wa/
│       └── ...
└── data/                   — legacy fallback (single-trail mode)
```

---

## Adding a new trail

1. Create `trails/<trail-id>/` with four files:

   **config.json** — all trail-specific constants including bugBands, terminus, endTrailDist

   **trail.geojson** — GeoJSON FeatureCollection, single LineString.
   Add startMile/endMile to properties. MultiLineString is handled automatically.

   **campsites.json** — sorted by trailDist. Both mile and trailDist required.
   trailDist is GPS arc-length from trail start, precomputed offline in Python.

   **plans/index.json** — start with []

2. Add one line to registry.json:
   ```json
   { "id": "my-trail", "label": "My Trail Name", "path": "trails/my-trail" }
   ```

3. Push. Trail appears in dropdown immediately. No changes to index.html.

---

## Saving and restoring plans

From the **Export** tab, download a plan file named `long-trail-plan-20260625-12.0.json`.
To restore it automatically, place it in `trails/<trail-id>/plans/` and add an entry to `plans/index.json`:
```json
[{ "file": "long-trail-plan-20260625-12.0.json", "label": "Jun 25 '26 · 12.0 mpd" }]
```

---

## URL bookmarking

```
https://dwettergreen.github.io/hike_planner/#trail=long-trail
https://dwettergreen.github.io/hike_planner/#trail=pct-wa
```

---

## Local development

```bash
cd hike_planner
python3 -m http.server 8000
# Open http://localhost:8000
# Cmd+Shift+R to force-reload after pushing changes
```

---

## Technical reference

See Hike_Planner_Technical_Design_v4.docx for full DP pseudocode, V4 bug model derivation,
data format specs, trail distance infrastructure, multi-trail architecture, and bug catalog.

---

*Vibe coded with Claude - March 2026*
