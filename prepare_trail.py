#!/usr/bin/env python3
"""
prepare_trail.py  —  Hike Planner trail data preparation
=========================================================
Converts a raw GPS track and campsite list into the two data files
the hike_planner application requires:

    data/trail.geojson   — thinned rendering trail (~8,000 points)
    data/campsites.json  — campsite array with trailDist pre-computed

Usage
-----
    python prepare_trail.py \\
        --trail     raw_trail.geojson \\
        --campsites raw_campsites.csv \\
        --name      "Long Trail" \\
        --expected  272 \\
        --thin      25 \\
        --out       data/

Arguments
---------
    --trail       Path to raw GPS track.  Accepted formats:
                    GeoJSON FeatureCollection of LineString features
                    GeoJSON FeatureCollection with a MultiLineString feature
                    GeoJSON single Feature with LineString or MultiLineString
                    GPX file (.gpx extension)

    --campsites   Path to campsite source file.  Accepted formats:
                    CSV  with columns: name, lat, lon, mile, elev, type,
                         water, outhouse, source [, desc] [, amenities]
                    JSON array already in campsites.json schema (re-computes
                         trailDist from current track)

    --name        Trail name written into trail.geojson properties.

    --expected    Published total distance in miles (used for arc-length
                  validation, ±10% tolerance).  Pass 0 to skip this check.

    --spacing     Target distance between rendering trail points in feet
                  (default 300).  The script computes the thin value as
                  round(spacing / avg_source_spacing), measured over the
                  first 2,000 source points.  Aim for 200–500 ft for a
                  good balance of visual accuracy and file size.
                  The original PCT WA trail.geojson used ~263 ft spacing.

    --out         Output directory (default: data/).  Created if absent.
                  Writes trail.geojson and campsites.json into this directory.

    --reverse     Reverse the coordinate array before processing.  Use when
                  the source track is SOBO and the direction check fails.

    --skip-validate
                  Skip the five data validation checks.  Not recommended;
                  use only when iterating on campsite data interactively.

Output
------
    trail.geojson   Single LineString FeatureCollection, thinned.
    campsites.json  Array sorted by mile ascending, all camps with trailDist.

    Also prints to stdout:
        Full-resolution arc-length  →  set as END_TRAIL_DIST in index.html
        Thinned point count
        Camp count and trailDist range
        Any validation warnings

Campsite CSV format
-------------------
Required columns (order does not matter, header row required):
    name        string   campsite identifier
    lat         float    decimal degrees WGS84
    lon         float    decimal degrees, negative west
    mile        float    published NOBO mile marker
    elev        float    elevation in feet (leave blank for resupply stops)
    type        string   Undeveloped | Established | Resupply
    water       bool     true/false or 1/0
    outhouse    bool     true/false or 1/0
    source      string   halfmile | gmc | farout | osm | resupply | custom

Optional columns:
    desc        string   free-text notes (omitted if blank)
    amenities   string   comma-separated list for resupply stops
                         e.g. "Post office,Store,Lodging"

Dependencies
------------
    Standard library only: json, math, csv, argparse, pathlib, sys, os
    No numpy, pandas, or shapely required.

References
----------
    Trail Import Guide v1.0  §§2–5
    Technical Design Document v2.0  §§3, 7.2, 11.2
"""

import argparse
import csv
import json
import math
import os
import sys
from pathlib import Path


# ── Haversine distance ────────────────────────────────────────────────────────

def haversine(a, b):
    """
    Arc-length in miles between two [lon, lat] points.
    Uses the Haversine formula.  Accurate to <0.1% for distances up to
    several hundred miles.
    """
    R = 3958.8  # Earth radius in miles
    lat1, lon1 = math.radians(a[1]), math.radians(a[0])
    lat2, lon2 = math.radians(b[1]), math.radians(b[0])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    x = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(min(x, 1.0)))  # clamp for floating-point safety


# ── GPS track loading ─────────────────────────────────────────────────────────

def load_gpx(path):
    """
    Parse a GPX file and return a flat list of [lon, lat] coordinates.
    Concatenates all <trkpt> elements across all tracks and segments.
    Uses only the standard library (xml.etree).
    """
    import xml.etree.ElementTree as ET
    tree = ET.parse(path)
    root = tree.getroot()
    # GPX namespace varies; handle with or without it
    ns = ''
    if root.tag.startswith('{'):
        ns = root.tag.split('}')[0] + '}'
    coords = []
    for trkpt in root.iter(f'{ns}trkpt'):
        lat = float(trkpt.attrib['lat'])
        lon = float(trkpt.attrib['lon'])
        coords.append([lon, lat])
    if not coords:
        raise ValueError("No <trkpt> elements found in GPX file.")
    return coords


def extract_coords_from_geojson(data):
    """
    Accept a GeoJSON object in any of these forms and return a flat
    list of [lon, lat] coordinate pairs:

        FeatureCollection  of one or more LineString features
        FeatureCollection  with a MultiLineString feature
        Feature            with LineString or MultiLineString geometry
        Geometry           object directly (LineString or MultiLineString)

    For multi-feature FeatureCollections the features are sorted by their
    southernmost latitude (min latitude) before concatenation so that the
    result is in NOBO order regardless of storage order in the source file.
    Near-duplicate junction points (first point of a segment within 0.05 mi
    of the last point of the previous segment) are removed during merging.
    """
    def flatten_multilinestring(mls_coords):
        """Merge MultiLineString segments, deduplicating junctions."""
        merged = list(mls_coords[0])
        for seg in mls_coords[1:]:
            if haversine(merged[-1], seg[0]) < 0.05:
                merged.extend(seg[1:])
            else:
                merged.extend(seg)
        return merged

    def geom_to_coords(geom):
        if geom['type'] == 'LineString':
            return list(geom['coordinates'])
        elif geom['type'] == 'MultiLineString':
            return flatten_multilinestring(geom['coordinates'])
        else:
            raise ValueError(f"Unsupported geometry type: {geom['type']}")

    # Unwrap to a list of geometry objects
    obj_type = data.get('type')

    if obj_type == 'FeatureCollection':
        features = data['features']
        if not features:
            raise ValueError("FeatureCollection has no features.")

        # If there is exactly one feature, extract directly
        if len(features) == 1:
            return geom_to_coords(features[0]['geometry'])

        # Multiple features: sort by min latitude (southernmost first = NOBO)
        def min_lat(feat):
            geom = feat['geometry']
            if geom['type'] == 'LineString':
                return min(c[1] for c in geom['coordinates'])
            elif geom['type'] == 'MultiLineString':
                return min(c[1] for seg in geom['coordinates'] for c in seg)
            return 0.0

        features_sorted = sorted(features, key=min_lat)
        print(f"  Sorted {len(features_sorted)} features by min latitude (NOBO order).")

        # Merge, deduplicating junctions
        merged = list(features_sorted[0]['geometry']['coordinates'])
        for feat in features_sorted[1:]:
            seg = feat['geometry']['coordinates']
            if haversine(merged[-1], seg[0]) < 0.05:
                merged.extend(seg[1:])
                print(f"    Deduplicated junction point (features within 0.05 mi).")
            else:
                merged.extend(seg)
        return merged

    elif obj_type == 'Feature':
        return geom_to_coords(data['geometry'])

    elif obj_type in ('LineString', 'MultiLineString'):
        return geom_to_coords(data)

    else:
        raise ValueError(f"Unrecognised GeoJSON type: '{obj_type}'")


def load_trail(path, reverse=False):
    """
    Load a GPS track from a GeoJSON or GPX file.
    Returns a flat list of [lon, lat] coordinates in NOBO order.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Trail file not found: {path}")

    print(f"\nLoading trail from: {p.name}")

    if p.suffix.lower() == '.gpx':
        coords = load_gpx(path)
        print(f"  GPX: {len(coords):,} trackpoints loaded.")
    else:
        with open(path) as f:
            data = json.load(f)
        coords = extract_coords_from_geojson(data)
        print(f"  GeoJSON: {len(coords):,} coordinate pairs extracted.")

    if reverse:
        coords = coords[::-1]
        print("  Reversed coordinate array (--reverse flag).")

    return coords


# ── Arc-length computation ────────────────────────────────────────────────────

def build_cumulative(coords):
    """
    Build a cumulative Haversine arc-length array over a coordinate list.
    Returns cum[] where cum[i] is the distance in miles from coords[0] to coords[i].
    cum[0] = 0.0 always.
    """
    cum = [0.0]
    for i in range(1, len(coords)):
        cum.append(cum[-1] + haversine(coords[i - 1], coords[i]))
    return cum


# ── Campsite snapping ─────────────────────────────────────────────────────────

def snap_trail_dist(camp_lat, camp_lon, coords, cum):
    """
    Find the nearest trail point to (camp_lat, camp_lon) by squared
    Euclidean distance (fast approximation; accurate for nearby points).
    Returns the cumulative arc-length at that point, rounded to 3 decimal
    places (~50 foot precision).
    """
    best_i = 0
    best_d = float('inf')
    for i, (lon, lat) in enumerate(coords):
        d = (lat - camp_lat) ** 2 + (lon - camp_lon) ** 2
        if d < best_d:
            best_d = d
            best_i = i
    return round(cum[best_i], 3)


# ── Campsite loading ──────────────────────────────────────────────────────────

def _parse_bool(val):
    """Convert a string representation of a boolean to Python bool."""
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ('true', '1', 'yes', 'y')


def load_campsites_csv(path):
    """
    Load campsites from a CSV file.
    Returns a list of dicts with the campsites.json schema (minus trailDist,
    which is computed later).
    """
    camps = []
    with open(path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        required = {'name', 'lat', 'lon', 'mile', 'type', 'water', 'outhouse', 'source'}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV is missing required columns: {sorted(missing)}")

        for row_num, row in enumerate(reader, start=2):
            name = row['name'].strip()
            if not name:
                print(f"  Warning: row {row_num} has blank name — skipped.")
                continue

            camp = {
                'mile':     round(float(row['mile']), 3),
                'name':     name,
                'lat':      float(row['lat']),
                'lon':      float(row['lon']),
                'elev':     float(row['elev']) if row.get('elev', '').strip() else None,
                'type':     row['type'].strip(),
                'water':    _parse_bool(row['water']),
                'outhouse': _parse_bool(row['outhouse']),
                'source':   row['source'].strip(),
            }

            # Validate type field
            valid_types = {'Undeveloped', 'Established', 'Resupply'}
            if camp['type'] not in valid_types:
                print(f"  Warning: '{name}' has unrecognised type '{camp['type']}' "
                      f"(expected one of: {', '.join(sorted(valid_types))}).")

            # Optional desc — omit if blank (do not set to null or empty string)
            desc = row.get('desc', '').strip()
            if desc:
                camp['desc'] = desc

            # Optional amenities — parse comma-separated list
            amenities_raw = row.get('amenities', '').strip()
            if amenities_raw:
                camp['amenities'] = [a.strip() for a in amenities_raw.split(',') if a.strip()]

            camps.append(camp)

    print(f"  CSV: {len(camps)} campsites loaded.")
    return camps


def load_campsites_json(path):
    """
    Load an existing campsites.json array.
    trailDist values will be recomputed from the current track, so any
    existing trailDist values are discarded to ensure consistency.
    """
    with open(path) as f:
        camps = json.load(f)
    # Strip existing trailDist so we recompute cleanly
    for c in camps:
        c.pop('trailDist', None)
    print(f"  JSON: {len(camps)} campsites loaded (trailDist will be recomputed).")
    return camps


def load_campsites(path):
    """Dispatch to CSV or JSON loader based on file extension."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Campsite file not found: {path}")
    print(f"\nLoading campsites from: {p.name}")
    if p.suffix.lower() == '.csv':
        return load_campsites_csv(path)
    elif p.suffix.lower() == '.json':
        return load_campsites_json(path)
    else:
        raise ValueError(f"Unsupported campsite file format: {p.suffix}  (use .csv or .json)")


# ── Validation ────────────────────────────────────────────────────────────────

def validate(coords, cum, camps, expected_miles):
    """
    Run all five pre-commit data checks.  Raises AssertionError on first
    failure with a descriptive message.  See Trail Import Guide §4.

    Check 1  — Direction: track must be NOBO (lat[0] < lat[-1]).
    Check 2  — Arc-length: must be within 10% of expected_miles
               (skip if expected_miles == 0).
    Check 3  — Required fields: every camp must have 'mile' and 'trailDist'.
    Check 4  — Monotonicity: trailDist values must be strictly ascending.
               Non-monotonic values break the DP optimizer (Bug 2).
    Check 5  — Snap distance: no camp should snap more than 0.5 mi from trail.
               Catches coordinate errors, swapped lat/lon, off-trail waypoints.
    """
    errors = []

    # 1. Direction
    if coords[0][1] >= coords[-1][1]:
        errors.append(
            f"Check 1 FAIL — Trail runs SOBO (lat start={coords[0][1]:.4f}, "
            f"end={coords[-1][1]:.4f}).  Re-run with --reverse."
        )
    else:
        print("  Check 1 PASS — Direction: NOBO (lat increases south to north).")

    # 2. Arc-length
    arc = cum[-1]
    if expected_miles > 0:
        lo, hi = 0.90 * expected_miles, 1.10 * expected_miles
        if not (lo <= arc <= hi):
            errors.append(
                f"Check 2 FAIL — Arc-length {arc:.1f} mi deviates >10% from "
                f"expected {expected_miles} mi (acceptable range: {lo:.1f}–{hi:.1f} mi).  "
                f"Check for feature ordering errors or wrong source file."
            )
        else:
            print(f"  Check 2 PASS — Arc-length {arc:.2f} mi "
                  f"(expected {expected_miles} mi, {abs(arc - expected_miles) / expected_miles * 100:.1f}% deviation).")
    else:
        print(f"  Check 2 SKIP — No expected distance provided (arc = {arc:.2f} mi).")

    # 3. Required fields
    missing_fields = [c['name'] for c in camps if 'mile' not in c or 'trailDist' not in c]
    if missing_fields:
        errors.append(
            f"Check 3 FAIL — {len(missing_fields)} camp(s) missing 'mile' or 'trailDist': "
            + ", ".join(missing_fields[:10])
            + (" ..." if len(missing_fields) > 10 else "")
        )
    else:
        print(f"  Check 3 PASS — All {len(camps)} camps have 'mile' and 'trailDist'.")

    # 4. Monotonicity
    sorted_camps = sorted(camps, key=lambda c: c.get('trailDist', 0))
    non_mono = []
    for i in range(1, len(sorted_camps)):
        if sorted_camps[i]['trailDist'] <= sorted_camps[i - 1]['trailDist']:
            non_mono.append(
                f"  '{sorted_camps[i]['name']}' (trailDist={sorted_camps[i]['trailDist']}) "
                f"<= '{sorted_camps[i-1]['name']}' ({sorted_camps[i-1]['trailDist']})"
            )
    if non_mono:
        errors.append(
            f"Check 4 FAIL — Non-monotonic trailDist values (breaks the DP optimizer):\n"
            + "\n".join(non_mono[:5])
            + ("\n  ..." if len(non_mono) > 5 else "")
        )
    else:
        print(f"  Check 4 PASS — trailDist values are strictly monotonic.")

    # 5. Snap distance
    bad_snaps = []
    for c in camps:
        td = snap_trail_dist(c['lat'], c['lon'], coords, cum)
        dist = abs(td - c['trailDist'])
        if dist >= 0.5:
            bad_snaps.append(f"  '{c['name']}' snaps {dist:.2f} mi from trail "
                             f"(lat={c['lat']}, lon={c['lon']})")
    if bad_snaps:
        errors.append(
            f"Check 5 FAIL — {len(bad_snaps)} camp(s) snap more than 0.5 mi from trail "
            f"(wrong coordinates, swapped lat/lon, or off-trail waypoint):\n"
            + "\n".join(bad_snaps[:5])
            + ("\n  ..." if len(bad_snaps) > 5 else "")
        )
    else:
        print(f"  Check 5 PASS — All camps snap within 0.5 mi of trail.")

    if errors:
        print("\n── VALIDATION FAILED ──────────────────────────────────────────")
        for e in errors:
            print(f"\n{e}")
        print()
        sys.exit(1)

    print("  All checks passed.")


# ── Trail geojson output ──────────────────────────────────────────────────────

def build_rendering_trail(coords, thin, trail_name):
    """
    Build the rendering trail.geojson by keeping every Nth coordinate.
    Returns a GeoJSON FeatureCollection dict with a single LineString feature.

    IMPORTANT: The caller must set END_TRAIL_DIST in index.html to the
    full-resolution arc-length (total_arc), NOT to the thinned trail's
    arc-length.  buildTrailCum() in the browser rescales _trailCum[] to
    match END_TRAIL_DIST.  See TDD §7.3.
    """
    thinned = coords[::thin]
    # Always include the last point so the trail reaches the terminus exactly
    if thinned[-1] != coords[-1]:
        thinned.append(coords[-1])
    # Round to 6 decimal places (~11cm accuracy) — eliminates floating-point
    # noise from GPS processing (e.g. 45.66470590000006) and reduces file
    # size by ~40% with no meaningful loss of accuracy for trail rendering.
    thinned = [[round(lon, 6), round(lat, 6)] for lon, lat in thinned]
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": thinned
            },
            "properties": {
                "name": trail_name
            }
        }]
    }


# ── Main pipeline ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Hike Planner trail data preparation tool.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('--trail',     required=True,  help="Raw GPS track (GeoJSON or GPX)")
    parser.add_argument('--campsites', required=True,  help="Campsite source file (CSV or JSON)")
    parser.add_argument('--name',      default="Trail", help="Trail name for trail.geojson properties")
    parser.add_argument('--expected',  type=float, default=0,
                        help="Published total miles (for arc-length check; 0 = skip)")
    parser.add_argument('--spacing',   type=float, default=300,
                        help="Target distance between rendering trail points in feet "
                             "(default 300). Computes thin value from source point density.")
    parser.add_argument('--out',       default="data",
                        help="Output directory (default: data/)")
    parser.add_argument('--reverse',   action='store_true',
                        help="Reverse coord array (use when source track is SOBO)")
    parser.add_argument('--skip-validate', action='store_true',
                        help="Skip the five validation checks (not recommended)")
    args = parser.parse_args()

    # ── 1. Load GPS track ────────────────────────────────────────────────────
    coords = load_trail(args.trail, reverse=args.reverse)

    # ── 2. Build cumulative arc-length (full resolution) ─────────────────────
    print("\nComputing full-resolution arc-length...")
    cum = build_cumulative(coords)
    total_arc = cum[-1]
    print(f"  Full-resolution arc-length: {total_arc:.3f} miles  ({len(coords):,} points)")
    print(f"\n  *** SET END_TRAIL_DIST = {total_arc:.3f} in index.html ***\n")

    # ── 3. Load campsites ────────────────────────────────────────────────────
    camps = load_campsites(args.campsites)

    # ── 4. Compute trailDist for every campsite ───────────────────────────────
    print("\nSnapping campsites to trail...")
    for c in camps:
        c['trailDist'] = snap_trail_dist(c['lat'], c['lon'], coords, cum)

    # Report trailDist range
    tds = [c['trailDist'] for c in camps]
    print(f"  trailDist range: {min(tds):.3f} – {max(tds):.3f} miles")

    # ── 5. Sort by mile ascending ─────────────────────────────────────────────
    camps.sort(key=lambda c: c['mile'])

    # ── 6. Validate ──────────────────────────────────────────────────────────
    if not args.skip_validate:
        print("\nRunning validation checks...")
        validate(coords, cum, camps, args.expected)
    else:
        print("\nValidation skipped (--skip-validate).")

    # ── 7. Build rendering trail.geojson ─────────────────────────────────────
    # Compute thin value from target point spacing in feet.
    # Measure average source spacing over the first 2,000 points for speed;
    # the PCTA source is uniform enough that this sample is representative.
    sample = min(2000, len(coords))
    avg_spacing_ft = sum(
        haversine(coords[i - 1], coords[i]) * 5280
        for i in range(1, sample)
    ) / (sample - 1)
    thin = max(1, round(args.spacing / avg_spacing_ft))
    print(f"\nBuilding rendering trail...")
    print(f"  Source avg spacing:  {avg_spacing_ft:.1f} ft/pt")
    print(f"  Target spacing:      {args.spacing:.0f} ft/pt")
    print(f"  Computed thin value: every {thin}th point")

    rendering_trail = build_rendering_trail(coords, thin, args.name)
    thinned_count = len(rendering_trail['features'][0]['geometry']['coordinates'])
    thinned_arc = sum(
        haversine(
            rendering_trail['features'][0]['geometry']['coordinates'][i - 1],
            rendering_trail['features'][0]['geometry']['coordinates'][i]
        )
        for i in range(1, thinned_count)
    )
    actual_spacing_ft = (thinned_arc * 5280) / thinned_count
    print(f"  Output: {thinned_count:,} points, {thinned_arc:.2f} mi arc, "
          f"~{actual_spacing_ft:.0f} ft avg spacing")
    print(f"  (Note: {total_arc - thinned_arc:.2f} mi lost to corner-cutting — "
          f"buildTrailCum() rescales this in the browser)")
    if thinned_count < 3000:
        print(f"  Warning: only {thinned_count:,} output points — trail may render jaggedly. "
              f"Try --spacing {args.spacing // 2:.0f}.")
    elif thinned_count > 20000:
        print(f"  Warning: {thinned_count:,} output points may slow map rendering. "
              f"Try --spacing {args.spacing * 2:.0f}.")

    # ── 8. Write output files ─────────────────────────────────────────────────
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    trail_out = out_dir / "trail.geojson"
    with open(trail_out, 'w') as f:
        json.dump(rendering_trail, f, separators=(',', ':'))
    print(f"\nWrote: {trail_out}  ({trail_out.stat().st_size // 1024} KB)")

    camps_out = out_dir / "campsites.json"
    with open(camps_out, 'w') as f:
        json.dump(camps, f, indent=2)
    print(f"Wrote: {camps_out}  ({len(camps)} campsites, "
          f"{camps_out.stat().st_size // 1024} KB)")

    # ── 9. Summary ────────────────────────────────────────────────────────────
    resupply_count = sum(1 for c in camps if c.get('source') == 'resupply')
    print(f"""
────────────────────────────────────────────────────────────────
Summary
────────────────────────────────────────────────────────────────
  Trail              {args.name}
  Campsites          {len(camps)}  ({resupply_count} resupply stops)
  Full arc-length    {total_arc:.3f} mi   ← END_TRAIL_DIST in index.html
  Rendering trail    {thinned_count:,} points  (~{actual_spacing_ft:.0f} ft spacing, {thinned_arc:.2f} mi arc, rescaled by browser)

Next steps
  1. Set END_TRAIL_DIST = {total_arc:.3f} in the index.html constants block.
  2. Set START_MILE / END_MILE to the published trail mile markers.
  3. Update TERMINUS lat/lon/elev/mile for the end terminus.
  4. Recalibrate BASELINE_MELT_DOY and MOSQ_BASE for the trail's climate.
  5. Update the start marker tooltip text in loadData().
  6. Test locally:  python3 -m http.server 8000
  7. Commit and push data/ to GitHub Pages.
────────────────────────────────────────────────────────────────
""")


if __name__ == '__main__':
    main()
