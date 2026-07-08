import os
import json
import numpy as np
import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from matplotlib.collections import LineCollection
from PIL import Image

import config
MAP_IMAGE = config.PNG_FILE
OMAP_FILE = config.OMAP_FILE

CACHE_DIR = os.path.join("cache", os.path.splitext(os.path.basename(OMAP_FILE))[0])
GROUPS_FILE = os.path.join(CACHE_DIR, "vrstevnice_groups.json")
HEIGHTS_FILE = os.path.join(CACHE_DIR, "assigned_heights.json")
META_FILE = os.path.join(CACHE_DIR, "cenova_mapa_meta.npy")

def extract_coords(coords_text):
    pts = []
    if ';' in coords_text:
        for part in coords_text.strip().split(';'):
            nums = part.strip().split()
            if len(nums) >= 2:
                try: pts.append((float(nums[0]) / 1000.0, -float(nums[1]) / 1000.0))
                except ValueError: pass
    else:
        nums = coords_text.strip().split()
        for i in range(0, len(nums) - 1, 2):
            try: pts.append((float(nums[i]) / 1000.0, -float(nums[i+1]) / 1000.0))
            except ValueError: pass
    return pts

def main():
    print("Nacitam data pro vizualni kontrolu...")
    meta = np.load(META_FILE)
    min_x, min_y, max_x, max_y = meta[0], meta[1], meta[2], meta[3]
    
    with open(GROUPS_FILE, 'r') as f:
        groups_data = json.load(f)
        
    with open(HEIGHTS_FILE, 'r') as f:
        assigned_heights = json.load(f)
        
    group_map = {}
    for gid_str, cids in groups_data['groups'].items():
        for cid in cids:
            group_map[cid] = gid_str

    try:
        tree = ET.parse(OMAP_FILE)
        root = tree.getroot()
    except Exception as e:
        print(f"Chyba: {e}")
        return

    ns = {'ns': 'http://openorienteering.org/apps/mapper/xml/v2'}
    symbol_map = {}
    for sym_elem in root.findall('.//ns:symbol', ns) or root.findall('.//symbol'):
        s_id = sym_elem.attrib.get('id')
        s_code = sym_elem.attrib.get('code')
        if s_id and s_code:
            symbol_map[s_id] = s_code.split('.')[0]

    objects = root.findall('.//ns:object', ns) or root.findall('.//object')
    if not root.findall('.//ns:object', ns): ns = {}
    
    contours = {}
    for idx, obj in enumerate(objects):
        isom_code = None
        sym_child = obj.find('symbol' if not ns else 'ns:symbol', ns)
        if sym_child is not None and sym_child.text:
            isom_code = sym_child.text.strip().split('.')[0][:3]
        else:
            sym_attr = obj.attrib.get('symbol')
            if sym_attr:
                if sym_attr in symbol_map:
                    isom_code = symbol_map[sym_attr][:3]
                else:
                    isom_code = sym_attr.split('.')[0][:3]
                    
        if isom_code in ['101', '102']:
            coords_elem = obj.find('coords' if not ns else 'ns:coords', ns)
            if coords_elem is not None and coords_elem.text:
                pts = extract_coords(coords_elem.text)
                if len(pts) >= 2:
                    contours[idx] = np.array(pts)
                    
    img = Image.open(MAP_IMAGE)
    fig, ax = plt.subplots(figsize=(15, 10))
    ax.imshow(img)  # BEZ extent, pouzijeme pixelove souradnice
    
    cal_path = os.path.join(CACHE_DIR, "kalibrace.npy")
    if os.path.exists(cal_path):
        cal = np.load(cal_path)
        cal_a, cal_b, cal_c, cal_d, cal_e, cal_f = cal
        det = cal_a * cal_e - cal_b * cal_d
    else:
        print("Chyba: kalibrace.npy nenalezena!")
        return
        
    lines = []
    colors = []
    
    min_h = min(assigned_heights.values())
    max_h = max(assigned_heights.values())
    
    print("Vykresluji puvodni VEKTOROVE vrstevnice...")
    labeled_gids = set()
    
    for cid, pts in contours.items():
        if cid in group_map:
            gid = group_map[cid]
            if gid in assigned_heights:
                h = assigned_heights[gid]
                
                # Transformace do pixelovych souradnic obrazku
                oom_x = pts[:, 0]
                oom_y = pts[:, 1]
                img_x = (cal_e * (oom_x - cal_c) - cal_b * (oom_y - cal_f)) / det
                img_y = (cal_a * (oom_y - cal_f) - cal_d * (oom_x - cal_c)) / det
                trans_pts = np.column_stack((img_x, img_y))
                
                lines.append(trans_pts)
                colors.append(h)
                
                # Popisek
                if gid not in labeled_gids and len(pts) > 5:
                    mid_idx = len(pts) // 2
                    mid_x = img_x[mid_idx]
                    mid_y = img_y[mid_idx]
                    ax.text(mid_x, mid_y, f"{h}m", color='black', 
                            fontsize=9, fontweight='bold',
                            bbox=dict(facecolor='white', alpha=0.5, edgecolor='none', pad=0.5))
                    labeled_gids.add(gid)
                
    cmap = plt.get_cmap('jet')
    norm = plt.Normalize(min_h, max_h)
    lc = LineCollection(lines, cmap=cmap, norm=norm, linewidths=2.0)
    lc.set_array(np.array(colors))
    
    ax.add_collection(lc)
    cbar = fig.colorbar(lc, ax=ax)
    cbar.set_label('Vypocitana vyska (m)')
                
    ax.set_title("Vizuální kontrola originálních VEKTOROVÝCH tvarů a jejich výšek")
    plt.tight_layout()
    plt.savefig("debug_vector_heights.png", dpi=300, bbox_inches='tight')
    print("Obrazek byl ulozen do debug_vector_heights.png")

if __name__ == "__main__":
    main()
