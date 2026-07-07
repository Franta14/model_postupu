"""Deeper analysis: closed vs open contours, segment lengths, direction analysis."""
import xml.etree.ElementTree as ET
import numpy as np
from math import sqrt, atan2, pi

tree = ET.parse('Homolka_Vojirov_20240917.omap')
root = tree.getroot()

symbol_map = {}
for elem in root.iter():
    if 'symbol' in elem.tag.lower():
        sid = elem.attrib.get('id')
        code = elem.attrib.get('code')
        if sid and code:
            symbol_map[sid] = code

contour_objs = []
for obj in root.iter():
    if 'object' not in obj.tag.lower():
        continue
    isom = symbol_map.get(obj.attrib.get('symbol', ''), '').split('.')[0]
    if isom in ['101', '102']:
        pts = []
        for child in obj:
            if 'coords' in child.tag.lower() and child.text:
                for p in child.text.strip().split(';'):
                    parts = p.strip().split()
                    if len(parts) >= 2:
                        try:
                            pts.append((float(parts[0])/1000, -float(parts[1])/1000))
                        except ValueError:
                            pass
                break
        if pts:
            contour_objs.append({
                'isom': isom,
                'pts': pts,
            })

print(f"Total contour objects (101+102): {len(contour_objs)}")

# Classify: closed (first==last or very close) vs open
closed = 0
open_contours = []
single_pts = 0
for o in contour_objs:
    pts = o['pts']
    if len(pts) <= 1:
        single_pts += 1
        continue
    d = sqrt((pts[0][0] - pts[-1][0])**2 + (pts[0][1] - pts[-1][1])**2)
    if d < 0.5:  # less than 0.5m = closed
        closed += 1
        o['closed'] = True
    else:
        open_contours.append(o)
        o['closed'] = False

print(f"  Closed (loop): {closed}")
print(f"  Open (has free endpoints): {len(open_contours)}")
print(f"  Single-point fragments: {single_pts}")

# Segment length distribution
lengths = []
for o in contour_objs:
    pts = o['pts']
    if len(pts) < 2:
        continue
    length = sum(sqrt((pts[i+1][0]-pts[i][0])**2 + (pts[i+1][1]-pts[i][1])**2) for i in range(len(pts)-1))
    lengths.append(length)
    o['length'] = length

arr = np.array(lengths)
print(f"\nContour lengths (m):")
print(f"  min={arr.min():.1f}, max={arr.max():.1f}, mean={arr.mean():.1f}, median={np.median(arr):.1f}")
for t in [5, 10, 20, 50, 100, 200, 500]:
    print(f"  Shorter than {t}m: {np.sum(arr < t)}")

# Endpoint direction analysis - what angle does each endpoint point in?
# This helps determine if two endpoints should connect
print("\n--- Open endpoint direction + proximity analysis ---")
endpoints = []
for i, o in enumerate(open_contours):
    pts = o['pts']
    if len(pts) < 2:
        continue
    # Start endpoint: direction from pt[1] to pt[0] (outward direction)
    dx = pts[0][0] - pts[1][0]
    dy = pts[0][1] - pts[1][1]
    angle_start = atan2(dy, dx)
    endpoints.append((i, 'start', pts[0], angle_start, o['isom']))
    
    # End endpoint: direction from pt[-2] to pt[-1] (outward direction)
    dx = pts[-1][0] - pts[-2][0]
    dy = pts[-1][1] - pts[-2][1]
    angle_end = atan2(dy, dx)
    endpoints.append((i, 'end', pts[-1], angle_end, o['isom']))

print(f"Open endpoints to connect: {len(endpoints)}")

# For each open endpoint, find candidates within distance + compatible direction
def angle_diff(a1, a2):
    """Returns smallest angle between two directions (0..pi)."""
    d = abs(a1 - a2)
    if d > pi:
        d = 2*pi - d
    return d

good_candidates = 0
ambiguous = 0
no_match = 0

for i in range(len(endpoints)):
    idx_i, type_i, pt_i, angle_i, isom_i = endpoints[i]
    candidates = []
    for j in range(len(endpoints)):
        idx_j, type_j, pt_j, angle_j, isom_j = endpoints[j]
        if idx_i == idx_j:
            continue
        d = sqrt((pt_i[0] - pt_j[0])**2 + (pt_i[1] - pt_j[1])**2)
        if d > 20:
            continue
        # Direction compatibility: endpoint i points outward, endpoint j should point roughly opposite
        # If connecting, angle_j should be roughly angle_i + pi (pointing back towards i)
        expected_angle = angle_i + pi if angle_i < 0 else angle_i - pi
        dir_diff = angle_diff(angle_j, expected_angle)
        candidates.append((j, d, dir_diff))
    
    if not candidates:
        no_match += 1
    elif len(candidates) == 1:
        good_candidates += 1
    else:
        # Sort by distance
        candidates.sort(key=lambda x: x[1])
        if candidates[0][1] < candidates[1][1] * 0.5:
            good_candidates += 1  # Clear winner
        else:
            ambiguous += 1

print(f"  Clear match: {good_candidates}")
print(f"  Ambiguous (multiple close candidates): {ambiguous}")
print(f"  No match within 20m: {no_match}")

# Check the OMAP coordinate flags (some points have flags like 1, 17, etc.)
print("\n--- Coordinate flags analysis ---")
flag_counts = {}
for obj in root.iter():
    if 'object' not in obj.tag.lower():
        continue
    isom = symbol_map.get(obj.attrib.get('symbol', ''), '').split('.')[0]
    if isom not in ['101', '102']:
        continue
    for child in obj:
        if 'coords' in child.tag.lower() and child.text:
            for p in child.text.strip().split(';'):
                parts = p.strip().split()
                if len(parts) >= 3:
                    flag = parts[2]
                    flag_counts[flag] = flag_counts.get(flag, 0) + 1
                elif len(parts) == 2:
                    flag_counts['(no flag)'] = flag_counts.get('(no flag)', 0) + 1

print("Coordinate flags found:")
for flag, count in sorted(flag_counts.items(), key=lambda x: -x[1]):
    print(f"  Flag '{flag}': {count}")
