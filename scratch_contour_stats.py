"""Quick analysis of contour line objects in the OMAP file."""
import xml.etree.ElementTree as ET

tree = ET.parse('Homolka_Vojirov_20240917.omap')
root = tree.getroot()

# Build symbol map
symbol_map = {}
for elem in root.iter():
    if 'symbol' in elem.tag.lower():
        sid = elem.attrib.get('id')
        code = elem.attrib.get('code')
        if sid and code:
            symbol_map[sid] = code

# Find contour objects
contour_objs = []
for obj in root.iter():
    if 'object' not in obj.tag.lower():
        continue
    isom = symbol_map.get(obj.attrib.get('symbol', ''), '').split('.')[0]
    if isom in ['101', '102', '103']:
        # Get coords
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
        contour_objs.append({
            'isom': isom,
            'num_pts': len(pts),
            'pts': pts,
        })

print(f"Total contour objects: {len(contour_objs)}")
for code in ['101', '102', '103']:
    objs = [o for o in contour_objs if o['isom'] == code]
    if objs:
        pt_counts = [o['num_pts'] for o in objs]
        print(f"  ISOM {code}: {len(objs)} objects, pts per obj: min={min(pt_counts)}, max={max(pt_counts)}, avg={sum(pt_counts)/len(pt_counts):.1f}")

# Show a few examples
print("\nFirst 5 contour objects (101/102):")
shown = 0
for o in contour_objs:
    if o['isom'] in ['101', '102'] and shown < 5:
        print(f"  ISOM {o['isom']}: {o['num_pts']} pts, first: {o['pts'][:3]}, last: {o['pts'][-3:]}")
        shown += 1

# Check distances between endpoints of different contour fragments
from math import sqrt
print("\n--- Endpoint proximity analysis ---")
endpoints = []
for i, o in enumerate(contour_objs):
    if o['isom'] in ['101', '102'] and len(o['pts']) >= 2:
        endpoints.append((i, 'start', o['pts'][0], o['isom'], len(o['pts'])))
        endpoints.append((i, 'end', o['pts'][-1], o['isom'], len(o['pts'])))

print(f"Total endpoints: {len(endpoints)}")

# For each endpoint, find nearest endpoint from a DIFFERENT contour
close_pairs = []
for i in range(len(endpoints)):
    idx_i, type_i, pt_i, isom_i, npts_i = endpoints[i]
    best_dist = float('inf')
    best_j = None
    for j in range(len(endpoints)):
        idx_j, type_j, pt_j, isom_j, npts_j = endpoints[j]
        if idx_i == idx_j:
            continue
        d = sqrt((pt_i[0] - pt_j[0])**2 + (pt_i[1] - pt_j[1])**2)
        if d < best_dist:
            best_dist = d
            best_j = j
    if best_j is not None and best_dist < 20:  # within 20 meters
        close_pairs.append((i, best_j, best_dist))

print(f"\nEndpoint pairs within 20m: {len(close_pairs)}")
# Distribution of distances
dists = [d for _, _, d in close_pairs]
if dists:
    import numpy as np
    arr = np.array(dists)
    print(f"  Distance stats: min={arr.min():.2f}, max={arr.max():.2f}, mean={arr.mean():.2f}, median={np.median(arr):.2f}")
    for threshold in [0.5, 1, 2, 3, 5, 10, 15, 20]:
        count = sum(1 for d in dists if d <= threshold)
        print(f"  Pairs within {threshold}m: {count}")
