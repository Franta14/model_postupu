"""Analyze what flags mean in OMAP coordinates and check Bezier curves."""
import xml.etree.ElementTree as ET

tree = ET.parse('Homolka_Vojirov_20240917.omap')
root = tree.getroot()

symbol_map = {}
for elem in root.iter():
    if 'symbol' in elem.tag.lower():
        sid = elem.attrib.get('id')
        code = elem.attrib.get('code')
        if sid and code:
            symbol_map[sid] = code

# Look at raw coordinate data of a few contour objects
count = 0
for obj in root.iter():
    if 'object' not in obj.tag.lower():
        continue
    isom = symbol_map.get(obj.attrib.get('symbol', ''), '').split('.')[0]
    if isom not in ['101', '102']:
        continue
    for child in obj:
        if 'coords' in child.tag.lower() and child.text:
            raw = child.text.strip()
            points = raw.split(';')
            if len(points) >= 5 and count < 3:
                print(f"\n=== Contour ISOM {isom}, {len(points)} points ===")
                for i, p in enumerate(points[:10]):
                    print(f"  [{i}] {p.strip()}")
                if len(points) > 10:
                    print(f"  ... ({len(points)-10} more) ...")
                    for i in range(max(10, len(points)-3), len(points)):
                        print(f"  [{i}] {points[i].strip()}")
                count += 1
            break

# OMAP flag meanings:
# Flag bit 0 (value 1): This point is a Bezier curve control point
# Flag bit 4 (value 16): Close point / dash point
# Flag bit 1 (value 2): Various control
print("\n\n=== FLAG ANALYSIS ===")
print("OMAP coordinate flags for contour lines:")
print("  Flag 0 (no flag): Regular point on the contour line")
print("  Flag 1: Bezier curve handle (control point, not on the line itself)")
print("  Flag 16: Special marker (close point, gap, dash)")
print("  Flag 18: 16+2 combination")
print("  Flag 33: 32+1 combination")

# Count how many objects have Bezier curves
bezier_count = 0
no_bezier_count = 0
for obj in root.iter():
    if 'object' not in obj.tag.lower():
        continue
    isom = symbol_map.get(obj.attrib.get('symbol', ''), '').split('.')[0]
    if isom not in ['101', '102']:
        continue
    has_bezier = False
    for child in obj:
        if 'coords' in child.tag.lower() and child.text:
            for p in child.text.strip().split(';'):
                parts = p.strip().split()
                if len(parts) >= 3 and parts[2] == '1':
                    has_bezier = True
                    break
            break
    if has_bezier:
        bezier_count += 1
    else:
        no_bezier_count += 1

print(f"\nObjects with Bezier curves: {bezier_count}")
print(f"Objects without Bezier curves: {no_bezier_count}")

# Check the typical curvature / segment angle changes
from math import sqrt, atan2, pi, degrees
print("\n=== CURVATURE ANALYSIS (sharpest turns) ===")
max_angles = []
for obj in root.iter():
    if 'object' not in obj.tag.lower():
        continue
    isom = symbol_map.get(obj.attrib.get('symbol', ''), '').split('.')[0]
    if isom not in ['101', '102']:
        continue
    pts = []
    for child in obj:
        if 'coords' in child.tag.lower() and child.text:
            for p in child.text.strip().split(';'):
                parts = p.strip().split()
                if len(parts) >= 2:
                    flag = int(parts[2]) if len(parts) >= 3 else 0
                    # Skip Bezier control points (flag 1)
                    if flag & 1:
                        continue
                    try:
                        pts.append((float(parts[0])/1000, -float(parts[1])/1000))
                    except ValueError:
                        pass
            break
    
    if len(pts) < 3:
        continue
    
    max_angle = 0
    for i in range(1, len(pts)-1):
        dx1 = pts[i][0] - pts[i-1][0]
        dy1 = pts[i][1] - pts[i-1][1]
        dx2 = pts[i+1][0] - pts[i][0]
        dy2 = pts[i+1][1] - pts[i][1]
        a1 = atan2(dy1, dx1)
        a2 = atan2(dy2, dx2)
        diff = abs(a2 - a1)
        if diff > pi:
            diff = 2*pi - diff
        if diff > max_angle:
            max_angle = diff
    max_angles.append(degrees(max_angle))

import numpy as np
arr = np.array(max_angles)
print(f"Sharpest turn per contour object:")
print(f"  min={arr.min():.1f}°, max={arr.max():.1f}°, mean={arr.mean():.1f}°, median={np.median(arr):.1f}°")
for t in [30, 45, 60, 90, 120, 150]:
    print(f"  Objects with sharpest turn > {t}°: {np.sum(arr > t)}")
