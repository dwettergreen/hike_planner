# Hike Planner

A browser-based multi-trail backpacking itinerary optimizer. Generates an optimal multi-night camping plan from your target pace, start date, and snowmelt conditions using dynamic programming — then lets you adjust any night by dragging markers on the map.

**Live site:** https://dwettergreen.github.io/hike_planner/

---

## Trails

| Trail | Miles | Campsites | Season |
|-------|-------|-----------|--------|
| PCT Washington | 505 mi | ~178 | Aug–Sep |
| PCT Oregon | 417 mi | 118 | Jul–Sep |
| PCT No. California | 758 mi | 218 | Jul–Sep |
| PCT So. California | 917 mi | 350 | Apr–Jun |
| Long Trail (VT) | 272 mi | 64 | Jun–Sep |
| Colorado Trail | 486 mi | ~150 | Jul–Sep |

Select any trail from the dropdown — the map, campsite data, and bug model update automatically.

---

## Repository Structure

```
hike_planner/
├── index.html              ← Full application (single page, no build step)
├── registry.json           ← Trail list for the selector dropdown
└── trails/
    ├── pct-wa/
    │   ├── config.json     ← Trail constants + bug model
    │   ├── trail.geojson   ← Trail polyline
    │   ├── campsites.json  ← Campsites with trailDist
    │   └── plans/
    │       └── index.json  ← Saved itineraries manifest
    ├── pct-or/   (same structure)
    ├── pct-nca/  (same structure)
    ├── pct-sca/  (same structure)
    ├── long-trail/   (same structure)
    └── colorado-trail/   (same structure)
```

The tool is a static site — no server, no database, no build step. For local development:

```bash
cd hike_planner
python3 -m http.server 8000
# Open http://localhost:8000
```

---

## How It Works

### Campsite Selection Algorithm

The planner uses **dynamic programming (DP)** to find the globally optimal campsite sequence for the entire trip in one forward pass, rather than making greedy day-by-day decisions.

**Step 1 — Target night count**

```
T = round(total_distance / avg_pace)
```

**Step 2 — Daily distance window**

```
min_d = total / (T × 1.25)
max_d = total / (T × 0.75)
```

If no complete path exists (campsites too sparse in a section), the DP retries with progressively wider tolerances: ±25%, ±35%, ±45%, ±55%, ±65%, ±80%. A valid plan is always found.

**Step 3 — Campsite scoring**

Every candidate is scored on elevation and mosquito pressure on the estimated arrival date:

```
score = elev × (1 + weight × (1 − mosquito_pressure))
```

Mosquito pressure is a Gaussian bell curve from the V4 bug model, parameterized per trail with species-specific `peakDoy`, `sigma`, `weight`, elevation decay, and water proximity bonus. A camp at zero pressure scores `(1 + weight)×` its elevation; at peak pressure it scores `1×` its elevation.

**Step 4 — DP forward pass**

```
for each campsite i:
  for each earlier campsite j where min_d ≤ dist[i]−dist[j] ≤ max_d:
    if dp[j] + score(i) > dp[i]:
      dp[i] = dp[j] + score(i)
      prev[i] = j
```

Backtrack from the terminus to reconstruct the optimal path.

Inter-campsite distances use `trailDist` — cumulative Haversine arc-length from the trail start, computed from the full-resolution GPS track in Python. The published mile marker is retained as a display label only.

### What the Algorithm Does Not Consider

- **Terrain difficulty** — a strenuous pass and a flat valley day with equal mileage score identically
- **Water carries** — the dataset notes water presence but the optimizer does not penalize dry stretches
- **Permit zones** — quota areas (Enchantments, John Muir Wilderness, Whitney Zone, etc.) are not modeled
- **Trail closures** — fire or seasonal closures are not reflected in the data

---

## Using the Planner

### Controls

| Control | Effect |
|---------|--------|
| **Trail** | Select trail from dropdown; reloads all data |
| **Start date** | Departure date; drives arrival date calculations and bug model |
| **Avg mi/day** | Target pace; determines night count and DP distance window |
| **Flex ± mi** | Displayed pace range (informational; DP widens independently as needed) |
| **Snowmelt date** | Shifts mosquito pressure peaks for all elevation bands |

### Night Cards

The sidebar shows one card per night with campsite name, mile marker, elevation, miles that day, and arrival date. Badges indicate conditions:

| Badge | Meaning |
|-------|---------|
| 🦟 HIGH / MEDIUM | Mosquito pressure on arrival date |
| 🌬️ High Wind | Camp above ~6,500 ft |
| 💧 Water | Water source at or near camp |
| 🚽 Outhouse | Outhouse or privy present |
| Established | Designated site with infrastructure |
| Resupply | Town or resort stop |

Click any card to fly the map to that camp.

### Adjusting Your Plan

Drag any numbered marker on the map to move that night to a different camp — the route and sidebar update live on release. Markers snap to known campsites only.

### Exporting

- **⬇ Download CSV** — one row per night (Mile, Miles Today, Campsite, Elevation, Date, Notes). Opens in Excel or Google Sheets.
- **💾 Save plan.json** — records pace settings and all camp locations. Drop the file in `trails/<id>/plans/` and add it to `plans/index.json` to restore on reload.

---

## Editing Campsite Data

Click the **Editor** tab. The map cursor becomes a crosshair and all campsites appear as colored dots:

| Color | Source |
|-------|--------|
| Orange | Halfmile / trail agency data |
| Green | Custom sites you have added |
| Blue square | Resupply stops |

- **Add** — click near the trail; location snaps to the nearest GPS track point
- **Edit** — click any dot or list row
- **Delete** — select and click 🗑 Delete (resupply stops cannot be deleted)
- **Search** — filter by name or mile number

> **To save permanently:** Download `campsites.json` from the Editor toolbar → replace `trails/<id>/campsites.json` in your local repo → commit and push.

---

## Campsite Data Format

`campsites.json` is an array of objects sorted by `trailDist`. Required fields marked *:

| Field | Type | Description |
|-------|------|-------------|
| `mile` * | number | Published NOBO mile marker — display only, not used by optimizer |
| `trailDist` * | number | Arc-length from trail start in miles (3 decimal places) — used by optimizer |
| `name` * | string | Campsite identifier, no spaces preferred |
| `lat` * | number | Latitude, decimal degrees, WGS84, 6dp |
| `lon` * | number | Longitude, decimal degrees, negative west, 6dp |
| `elev` | number\|null | Elevation in feet |
| `type` * | string | `"Undeveloped"`, `"Established"`, or `"Resupply"` |
| `water` * | boolean | Water source at or near camp |
| `outhouse` * | boolean | Outhouse or privy present |
| `source` * | string | `"halfmile"`, `"gmc"`, `"farout"`, `"osm"`, `"resupply"`, or `"custom"` |
| `offTrail` | boolean | If `true`, excluded from DP route planning but still shown on map. Required for resupply stops more than ~1 mile from the main trail. |
| `desc` | string | Optional notes |
| `amenities` | string[] | Resupply stops only, e.g. `["Store","Lodging","Laundry"]` |

---

## Adding a New Trail

See the **Trail Import Guide v2.0** for the complete step-by-step procedure. In summary:

1. Obtain Halfmile GPX (PCT) or equivalent GPS track
2. Run the Python prep script — outputs `campsites.json`, `trail.geojson`, and updated `config.json`
3. Review gaps and `offTrail` flags; add gap-filling camps if needed
4. Create `trails/<id>/` with the four required files
5. Append one entry to `registry.json`
6. Commit and push — the new trail appears in the dropdown

No changes to `index.html` are required.

---

## Data Sources

| Trail | Track source | Campsite source |
|-------|-------------|-----------------|
| PCT (all sections) | [Halfmile PCT Maps](https://pctmap.net/gps/) GPX (2020) | Halfmile waypoints + PCTA resupply |
| Long Trail | OpenStreetMap relation #391736 | Green Mountain Club shelter list |
| Colorado Trail | Colorado Trail Foundation GeoJSON | CTF databook |

---

## Technical Documentation

Full technical documentation is available in the project docs folder:

- **Hike Planner TDD v3.0** — architecture, algorithms, data formats, bug catalog, and trail generalization guide
- **Trail Import Guide v2.0** — step-by-step procedure for adding a new trail from raw GPS data to deployment

---

## Known Limitations

- **Halfmile data frozen at 2020** — PCT campsites reflect the trail as of the last Halfmile update; newer reroutes require manual additions
- **Elevation gain not modeled** — daily distance is arc-length only; steep days and flat days at equal mileage score identically
- **Water carries** — dry stretches are noted in campsite descriptions but not modeled by the optimizer; critical for PCT SoCal desert sections
- **Permit zones** — quota areas are not modeled; add permit notes to campsite `desc` fields as a minimum
- **Map tiles require internet** — app logic and data load locally; only basemap tiles require a connection

---

*Vibe coded with Claude by David Wettergreen · March 2026*
