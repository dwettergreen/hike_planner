#!/usr/bin/env python3
"""
reverse_trail.py  —  Reverse the coordinate array in a trail.geojson so that
TRAIL_COORDS[0] is the NOBO start (trailDist = 0).

Use when prepare_trail.py produced a trail.geojson that runs in the wrong
direction (e.g. Colorado Trail: Denver is the NOBO start but trail.geojson
stored coordinates Denver→Durango, putting the terminus at index 0).

Usage:
    python reverse_trail.py trails/colorado-trail/trail.geojson

The file is updated in-place. A backup is written to trail.geojson.bak.

Verification printed after reversal:
  - First coordinate (should be NOBO start / southern-most for most trails)
  - Last coordinate  (should be terminus)
  - Total point count (should be unchanged)
"""

import json, shutil, sys, os

def reverse_trail(path):
    bak = path + '.bak'
    shutil.copy2(path, bak)
    print(f'Backup written to {bak}')

    with open(path) as f:
        data = json.load(f)

    feat = data['features'][0]
    geom = feat['geometry']

    if geom['type'] == 'LineString':
        coords = geom['coordinates']
        geom['coordinates'] = coords[::-1]
        n = len(coords)
    elif geom['type'] == 'MultiLineString':
        # Reverse each segment internally AND reverse the segment order
        segs = geom['coordinates']
        geom['coordinates'] = [seg[::-1] for seg in reversed(segs)]
        n = sum(len(s) for s in segs)
    else:
        print(f'ERROR: unsupported geometry type: {geom["type"]}')
        sys.exit(1)

    with open(path, 'w') as f:
        json.dump(data, f, separators=(',', ':'))

    # Re-read to verify
    with open(path) as f:
        check = json.load(f)
    c = check['features'][0]['geometry']['coordinates']
    if check['features'][0]['geometry']['type'] == 'MultiLineString':
        first, last = c[0][0], c[-1][-1]
    else:
        first, last = c[0], c[-1]

    print(f'Done. {n} points reversed.')
    print(f'  First coord (NOBO start): lon={first[0]:.5f}, lat={first[1]:.5f}')
    print(f'  Last coord  (terminus):   lon={last[0]:.5f},  lat={last[1]:.5f}')
    print()
    print('Next steps:')
    print('  1. Verify first coord matches your NOBO trailhead')
    print('  2. git add ' + path)
    print('  3. git commit -m "fix: reverse Colorado Trail coordinate order (NOBO start at index 0)"')
    print('  4. git push  (wait ~2 min for GitHub Pages propagation)')

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: python reverse_trail.py <path/to/trail.geojson>')
        sys.exit(1)
    p = sys.argv[1]
    if not os.path.exists(p):
        print(f'ERROR: file not found: {p}')
        sys.exit(1)
    reverse_trail(p)
