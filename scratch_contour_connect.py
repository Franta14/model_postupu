"""Test contour merging logic with shapely intersection checks."""
import xml.etree.ElementTree as ET
import numpy as np
from math import sqrt, atan2, pi
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree

tree = ET.parse('Homolka_Vojirov_20240917.omap')
root = tree.getroot()

symbol_map = {}
for elem in root.iter():
    if 'symbol' in elem.tag.lower():
        sid = elem.attrib.get('id')
        code = elem.attrib.get('code')
        if sid and code:
            symbol_map[sid] = code

contours = []
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
                        flag = int(parts[2]) if len(parts) >= 3 else 0
                        if flag & 1:  # skip Bezier control points
                            continue
                        try:
                            pts.append((float(parts[0])/1000, -float(parts[1])/1000))
                        except ValueError:
                            pass
                break
        if len(pts) >= 2:
            contours.append(pts)

print(f"Loaded {len(contours)} contour fragments.")

# 1. Create shapely linestrings for all contours for fast intersection tests
lines = [LineString(pts) for pts in contours]
tree_lines = STRtree(lines)

def intersects_any_contour(p1, p2, ignore_idx1, ignore_idx2):
    """Check if the segment p1-p2 intersects any contour (except the ones we are connecting)."""
    seg = LineString([p1, p2])
    # Find potential intersections using spatial index
    candidates_idx = tree_lines.query(seg)
    for idx in candidates_idx:
        if idx == ignore_idx1 or idx == ignore_idx2:
            continue
        if seg.intersects(lines[idx]):
            return True
    return False

def angle_diff(a1, a2):
    d = abs(a1 - a2)
    if d > pi: d = 2*pi - d
    return d

# 2. Extract endpoints
endpoints = []
for i, pts in enumerate(contours):
    # Check if closed
    if sqrt((pts[0][0]-pts[-1][0])**2 + (pts[0][1]-pts[-1][1])**2) < 0.5:
        continue
    
    # Start endpoint
    dx_s = pts[0][0] - pts[1][0]
    dy_s = pts[0][1] - pts[1][1]
    endpoints.append({
        'contour_idx': i,
        'is_start': True,
        'pt': pts[0],
        'angle': atan2(dy_s, dx_s)
    })
    
    # End endpoint
    dx_e = pts[-1][0] - pts[-2][0]
    dy_e = pts[-1][1] - pts[-2][1]
    endpoints.append({
        'contour_idx': i,
        'is_start': False,
        'pt': pts[-1],
        'angle': atan2(dy_e, dx_e)
    })

print(f"Found {len(endpoints)} open endpoints.")

# 3. Find matches
matches = []
MAX_DIST = 25.0  # meters
for i in range(len(endpoints)):
    ep1 = endpoints[i]
    best_cost = float('inf')
    best_j = -1
    
    for j in range(len(endpoints)):
        if i == j: continue
        ep2 = endpoints[j]
        if ep1['contour_idx'] == ep2['contour_idx']: continue # Don't connect to itself directly here
        
        dist = sqrt((ep1['pt'][0]-ep2['pt'][0])**2 + (ep1['pt'][1]-ep2['pt'][1])**2)
        if dist > MAX_DIST: continue
        
        # Directions should be roughly opposite
        expected_angle = ep1['angle'] + pi if ep1['angle'] < 0 else ep1['angle'] - pi
        dir_diff = angle_diff(ep2['angle'], expected_angle)
        
        # Cost function: distance (m) + angle difference penalty
        # 1 radian ~ 57 degrees. Let's say 90 deg (1.57 rad) penalty is equivalent to 20m.
        cost = dist + dir_diff * 15.0
        
        if cost < best_cost:
            # Check intersection
            if not intersects_any_contour(ep1['pt'], ep2['pt'], ep1['contour_idx'], ep2['contour_idx']):
                best_cost = cost
                best_j = j
                
    if best_j != -1:
        matches.append((i, best_j, best_cost))

print(f"Found {len(matches)} potential directed connections.")

# 4. Resolve mutual matches (i thinks j is best, and j thinks i is best)
mutual = []
for i, j, cost in matches:
    # Check if j's best match is i
    j_matches = [m for m in matches if m[0] == j]
    if j_matches and j_matches[0][1] == i:
        if i < j: # prevent duplicates
            mutual.append((i, j, cost))

print(f"Found {len(mutual)} mutual, valid connections without intersections.")

# Simulate merge
# We will use union-find or simply build paths
parent = {i: i for i in range(len(contours))}
def find(i):
    if parent[i] == i: return i
    parent[i] = find(parent[i])
    return parent[i]
def union(i, j):
    root_i = find(i)
    root_j = find(j)
    if root_i != root_j:
        parent[root_i] = root_j

for i, j, _ in mutual:
    c1 = endpoints[i]['contour_idx']
    c2 = endpoints[j]['contour_idx']
    union(c1, c2)

groups = {}
for i in range(len(contours)):
    r = find(i)
    groups.setdefault(r, []).append(i)

print(f"Resulting contour groups: {len(groups)} (was {len(contours)})")
lengths = [len(g) for g in groups.values()]
print(f"Fragments per group: max={max(lengths)}, avg={sum(lengths)/len(lengths):.1f}")
