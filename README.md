# Hike Planner

A browser-based, multi-night thru-hiking itinerary planner. Uses dynamic programming to find the globally optimal camp sequence for a given pace, start date, and bug emergence window. Supports multiple trails via a dropdown selector.

**Currently deployed trails:**
- **PCT Washington** — Bridge of Gods to Northern Terminus (505 miles)
- **PCT Oregon** — Ashland to Bridge of Gods (417 miles)
- **PCT No. California** — Tuolumne Meadows to Ashland (758 miles)
- **PCT So. California** — Campo to Tuolumne Meadows (917 miles)
- **Long Trail, Vermont** — All Vermont (272 miles)
- **Colorado Trail** — Denver to Durango (486 miles)

**Live tool:** https://dwettergreen.github.io/hike_planner/

---

## How it works

### Itinerary optimization (Dynamic Programming)

The planner finds the **globally optimal** camp sequence — not a greedy night-by-night selection. It runs a forward DP over all candidate campsites, maximizing the sum of campsite scores across all nights subject to a daily distance window.

**Score function:**
```
score = elevation × (1 + 2.0 × (1 - bugPressure))
```
A zero-bug camp scores 3× its elevation; a peak-bug camp scores 1× its elevation. The algorithm rewards high camps and good timing, trading off between them when they conflict.

The DP runs up to six times with progressively wider distance windows (±25% through ±80% of target pace) to guarantee a solution even when campsites are sparse.

### Manual campsite selection

Any night marker can be dragged to a different campsite. Dragged camps are flagged as `_manual: true` and persist when the user changes pace, start date, flex, or emergence date. The DP reruns on the full trail and then re-slots manual camps back into the new plan at the proportionally correct night, preserving the user's choices while keeping all other nights optimal.

### Bug pressure model (V4)

Each trail defines its own multi-species bug model in `config.json`. Each species is a Gaussian bell curve with elevation and water-proximity adjustments:

```
pressure(band) = weight
              × exp(-0.5 × ((doy - peakDoy) / sigma)²)   seasonal Gaussian
              × exp(-elevDecay × elevation_ft)              exponential elev decay
              × (1 + waterBonus × nearWater)

totalPressure = max(pressure across all bands)             worst pest wins
```

**Why max() not sum():** you care about the worst thing biting you, not a combined count.

**Why exponential elevation decay:** linear decay clamps to zero at typical hiking elevations. Exponential asymptotically approaches zero — real reduction at altitude without eliminating bugs entirely.

The **Emergence date** control shifts all species peak dates by the same offset, modeling late or early bug seasons.

---

## Intended workflow

The planner is hosted as a static website. Users do not need access to the repository to use it. The intended planning workflow is:

1. **Visit the live site** and select your trail.
2. **Set your parameters** — start date, miles per day, flex, emergence date.
3. **Review and adjust** the optimizer's suggested itinerary. Drag night markers to move individual camps; the rest of the plan reoptimizes around your choices.
4. **Export your plan** from the Import/Export tab. Save the `.json` file to your local machine.
5. **To resume planning**, return to the site and import your saved `.json` file. Your settings, camps, and manual selections are restored exactly.

Plan files live on the user's local machine. There is no account or login required.

---

## Plan file format

Exported plan files follow the naming convention `{trail-id}-plan-{YYYYMMDD}-{mpd}.json` — for example, `pct-wa-plan-20260701-13.0.json`. The file encodes the trail, settings, and every night's campsite including any manually placed camps.

When re-imported, the planner:
- Restores all slider and date settings
- Matches each saved night to the nearest campsite by trail distance
- Preserves `_manual` flags so dragged camps survive subsequent parameter changes
- If the file is for a different trail than the one currently loaded, offers to switch trails automatically before loading

---

## Repository structure

```
hike_planner/
├── index.html              — full application (~100 KB, no build step)
├── registry.json           — list of available trails (required)
├── prepare_trail.py        — data preparation script (see below)
├── docs/
│   ├── Hike_Planner_TDD_v4_1.docx     — technical design document
│   ├── Trail_Import_Guide_v3_1.docx   — step-by-step trail import guide
│   └── Hike_Planner_User_Guide_v1_0.docx — end-user planning guide
├── source/                 — raw GPS source files (committed for reproducibility)
│   ├── Washington.geojson      — PCTA 2026 PCT Washington centerline
│   ├── Oregon.geojson          — PCTA 2026 PCT Oregon centerline
│   ├── Northern_California.geojson
│   ├── Southern_California.geojson
│   └── long-trail.geojson      — OSM Long Trail track
└── trails/
    ├── pct-wa/
    │   ├── config.json         — trail constants + bug model
    │   ├── trail.geojson       — trail polyline (generated by prepare_trail.py)
    │   ├── campsites.json      — campsite waypoints with trailDist (generated)
    │   └── plans/
    │       └── index.json      — manifest of server-hosted plans (empty by default)
    ├── pct-or/       (same structure)
    ├── pct-nca/      (same structure)
    ├── pct-sca/      (same structure)
    ├── long-trail/   (same structure)
    └── colorado-trail/ (same structure)
```

**Notes:**
- `registry.json` is required — the app will not load without it.
- There is no `data/` fallback directory. All trails live under `trails/<id>/`.
- Plan files are named `{trail-id}-plan-{YYYYMMDD}-{mpd}.json`. Users save and manage these locally.

---

## Data preparation script

`prepare_trail.py` converts a raw GPS track and campsite source file into the two data files the planner needs — `trail.geojson` and `campsites.json` — with all `trailDist` values pre-computed. It requires only the Python standard library (no numpy, pandas, or shapely).

```bash
python prepare_trail.py \
    --trail     source/Washington.geojson \
    --campsites trails/pct-wa/campsites_source.csv \
    --name      "PCT Washington" \
    --expected  505 \
    --out       trails/pct-wa/
```

The script prints the `endTrailDist` value to set in `config.json`, runs all 5 validation checks, and gives a next-steps summary. Key options:

| Option | Default | Purpose |
|--------|---------|---------|
| `--trail` | required | Raw GPS track (GeoJSON or GPX) |
| `--campsites` | required | Campsite source (CSV or existing campsites.json) |
| `--expected` | 0 (skip) | Published miles, used for arc-length validation |
| `--spacing` | 300 ft | Target distance between rendering trail points |
| `--reverse` | off | Reverse coords if source track is SOBO |

### GPS track sources

**PCT sections:** Download from the [PCTA public Box folder](https://pcta.app.box.com/s/wsv09z18lw4kwptjrxd79kj07xm6ufsr/folder/305401160536) — `Washington.geojson`, `Oregon.geojson`, `Northern_California.geojson`, `Southern_California.geojson`. Updated each January. Commit to `source/`.

**Other trails:** OpenStreetMap Waymarked Trails for the Long Trail; Colorado Trail Foundation GIS for the CT; Halfmile pctmap.net GPX for campsite waypoints (2020 legacy data, waypoints still useful).

---

## Adding a new trail

1. **Download the GPS track** into `source/<id>.geojson` and commit it.

2. **Prepare campsite data** as a CSV (see Trail Import Guide for column spec).

3. **Run prepare_trail.py:**
   ```bash
   python prepare_trail.py \
       --trail     source/<id>.geojson \
       --campsites <your_camps>.csv \
       --name      "My Trail" \
       --expected  <published_miles> \
       --out       trails/<id>/
   ```
   Note the `endTrailDist` value it prints.

4. **Create `trails/<id>/config.json`** with trail constants, terminus coordinates, and bug model. Set `endTrailDist` from the script output.

5. **Add one line to `registry.json`:**
   ```json
   { "id": "my-trail", "label": "My Trail Name", "path": "trails/my-trail" }
   ```

6. **Create `trails/<id>/plans/index.json`** with content `[]`.

7. **Push.** Trail appears in the dropdown. No changes to `index.html`.

See `docs/Trail_Import_Guide_v3_1.docx` for the complete step-by-step procedure, including campsite extraction from Halfmile waypoints, resupply stop conventions, bug model calibration by climate, and the pre-commit checklist.

---

## URL bookmarking

```
https://dwettergreen.github.io/hike_planner/#trail=pct-wa
https://dwettergreen.github.io/hike_planner/#trail=long-trail
https://dwettergreen.github.io/hike_planner/#trail=colorado-trail
```

---

## Local development

```bash
cd hike_planner
python3 -m http.server 8000
# Open http://localhost:8000
# Cmd+Shift+R to force-reload after pushing changes
```

`registry.json` must be served by a web server — `file://` URLs block cross-origin fetches. Always use the local server for development.

---

## Technical reference

See `docs/Hike_Planner_User_Guide_vX_X.docx` for detailed explanation of the web-based tool and workflow for developing your hike plan. 

See `docs/Hike_Planner_TDD_vX_X.docx` for full DP pseudocode, V4 bug model derivation, data format specs, trail distance infrastructure, multi-trail architecture, and bug catalog.

See `docs/Trail_Import_Guide_vX_X.docx` for explanation of how to add a new trail to the tool, including scripts to prepare trail geojson and other necessary configuration settings.



---

*Vibe coded with Claude by David Wettergreen - April 2026*
