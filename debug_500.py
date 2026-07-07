import json
import numpy as np
from collections import defaultdict
import os

try:
    import config
    MAP_IMAGE = config.PNG_FILE
except ImportError:
    MAP_IMAGE = "mapa.png"

def load_meta():
    meta = np.load("cache/Homolka_Vojirov_20240917/cenova_mapa_meta.npy")
    return {
        'min_x': meta[0], 'min_y': meta[1],
        'max_x': meta[2], 'max_y': meta[3],
        'grid_size': meta[4]
    }

def main():
    meta = load_meta()
    lidar_grid = np.load("cache/Homolka_Vojirov_20240917/vyskova_mapa.npy")
    
    with open("cache/Homolka_Vojirov_20240917/assigned_heights.json") as f:
        assigned = json.load(f)
        
    c500 = [k for k,v in assigned.items() if v == 500.0]
    
    print(f"Pocet 500.0 contours: {len(c500)}")
    
    # Check what get_lidar_height would return for their points
    import xml.etree.ElementTree as ET
    tree = ET.parse("Homolka_Vojirov_20240917.omap")
    root = tree.getroot()
    ns = {'ns': 'http://openorienteering.org/apps/mapper/xml/v2'}
    objects = root.findall('.//ns:object', ns) or root.findall('.//object')
    if not root.findall('.//ns:object', ns): ns = {}
    
    contours = {}
    for idx, obj in enumerate(objects):
        coords_elem = obj.find('coords' if not ns else 'ns:coords', ns)
        if coords_elem is not None and coords_elem.text:
            pts = []
            text = coords_elem.text
            if ';' in text:
                for part in text.strip().split(';'):
                    nums = part.strip().split()
                    if len(nums) >= 2:
                        pts.append((float(nums[0]) / 1000.0, -float(nums[1]) / 1000.0))
            else:
                nums = text.strip().split()
                for i in range(0, len(nums) - 1, 2):
                    pts.append((float(nums[i]) / 1000.0, -float(nums[i+1]) / 1000.0))
            if len(pts) >= 2:
                contours[idx] = pts
                
    with open("cache/Homolka_Vojirov_20240917/vrstevnice_groups.json") as f:
        gdata = json.load(f)['groups']
        
    group_map = {}
    for gid, cids in gdata.items():
        for cid in cids:
            group_map[cid] = gid
            
    # Sample a few 500.0 contours
    for gid in cids[:5]:  # Wait, cids is the last group. I want c500!
        pass
        
    for gid in c500[:5]:
        cids = [c for c, g in group_map.items() if g == gid]
        print(f"\nGroup {gid} has {len(cids)} contours.")
        for cid in cids[:1]:
            pts = contours.get(cid, [])
            print(f"  Contour {cid} has {len(pts)} points.")
            if pts:
                p = pts[len(pts)//2]
                grid_x = int((p[0] - meta['min_x']) / meta['grid_size'])
                grid_y = int((p[1] - meta['min_y']) / meta['grid_size'])
                if 0 <= grid_x < lidar_grid.shape[1] and 0 <= grid_y < lidar_grid.shape[0]:
                    val = lidar_grid[grid_y, grid_x]
                    print(f"  Middle point {p} -> grid ({grid_x}, {grid_y}) -> lidar_val = {val}")
                else:
                    print(f"  Middle point {p} -> OUT OF BOUNDS")

if __name__ == '__main__':
    main()
