"""
debug_elevation.py - Diagnostika presnosti vyskovych dat

Rezim 1 (vychozi): Zobrazi POUZE rasterizovane OCAD vrstevnice (cervene)
                    pres PNG mapu -> vizualni overeni pozic.
Rezim 2 (--model): Zobrazi vyskovy model (heatmapa + izolinie) pres PNG mapu.

Spusteni:
    python debug_elevation.py          # Pouze OCAD vrstevnice
    python debug_elevation.py --model  # Vyskovy model
"""

import os
import sys
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

import config
map_image_file = config.PNG_FILE
map_name = os.path.splitext(os.path.basename(config.OMAP_FILE))[0]


def load_common():
    """Nacte spolecna data (meta, kalibrace, obrazek)."""
    cache_dir = os.path.join("cache", map_name)
    meta_path = os.path.join(cache_dir, "cenova_mapa_meta.npy")
    cal_path = os.path.join(cache_dir, "kalibrace.npy")

    if not os.path.exists(meta_path):
        print(f"❌ Nenalezen soubor {meta_path}")
        return None
    
    meta = np.load(meta_path)
    cal = np.load(cal_path)
    min_x, min_y, max_x, max_y, grid_size = meta
    cal_a, cal_b, cal_c, cal_d, cal_e, cal_f = cal

    print("Načítám obrázek mapy...")
    if not os.path.exists(map_image_file):
        print(f"❌ Nenalezen obrázek mapy: {map_image_file}")
        return None
    img = mpimg.imread(map_image_file)

    return {
        'cache_dir': cache_dir,
        'min_x': min_x, 'min_y': min_y, 'grid_size': grid_size,
        'cal': (cal_a, cal_b, cal_c, cal_d, cal_e, cal_f),
        'img': img,
    }


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

def mode_contour_positions(data):
    """Zobrazi plynulé vektorové čáry vrstevnic přímo z OMAP přes PNG mapu."""
    import xml.etree.ElementTree as ET
    
    omap_file = getattr(config, 'OMAP_FILE', "Homolka_Vojirov_20240917.omap") if 'config' in globals() else "Homolka_Vojirov_20240917.omap"
    
    print(f"Nacitam vektorove krivky z {omap_file}...")
    try:
        tree = ET.parse(omap_file)
        root = tree.getroot()
    except Exception as e:
        print(f"Chyba pri cteni {omap_file}: {e}")
        return

    ns = {'ns': 'http://openorienteering.org/apps/mapper/xml/v2'}
    
    symbol_map = {}
    for sym_elem in root.findall('.//ns:symbol', ns) or root.findall('.//symbol'):
        s_id = sym_elem.attrib.get('id')
        s_code = sym_elem.attrib.get('code')
        if s_id and s_code:
            symbol_map[s_id] = s_code.split('.')[0]

    objects = root.findall('.//ns:object', ns)
    if not objects:
        objects = root.findall('.//object')
        ns = {}

    print("Kreslim spojite vektorove cary pres mapu...")
    fig, ax = plt.subplots(figsize=(14, 10))
    ax.imshow(data['img'])
    
    count = 0
    for obj in objects:
        isom_code = None
        
        # 1. Zkus najit <symbol> uvnitr
        sym_child = obj.find('symbol' if not ns else 'ns:symbol', ns)
        if sym_child is not None and sym_child.text:
            isom_code = sym_child.text.strip().split('.')[0][:3]
        else:
            # 2. Zkus mapovani pres atribut
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
                if len(pts) < 2:
                    continue
                
                pts = np.array(pts)
                
                # Prevod OMAP -> Grid index -> PNG Pixel
                # 1. Na grid indexy
                grid_x = (pts[:, 0] - data['min_x']) / data['grid_size']
                grid_y = (pts[:, 1] - data['min_y']) / data['grid_size']
                
                # 2. Na PNG pixely
                cal_a, cal_b, cal_c, cal_d, cal_e, cal_f = data['cal']
                det = cal_a * cal_e - cal_b * cal_d
                
                oom_x = data['min_x'] + grid_x * data['grid_size']
                oom_y = data['min_y'] + grid_y * data['grid_size']
                
                img_x = (cal_e * (oom_x - cal_c) - cal_b * (oom_y - cal_f)) / det
                img_y = (cal_a * (oom_y - cal_f) - cal_d * (oom_x - cal_c)) / det
                
                # Jednotná červená barva pro oboje vrstevnice
                ax.plot(img_x, img_y, color='red', linewidth=1.2, alpha=0.9)
                count += 1
                
    # Vykresleni mostu
    groups_file = os.path.join(data['cache_dir'], "vrstevnice_groups.json")
    if os.path.exists(groups_file):
        print("Kreslim spojovaci mosty...")
        import json
        with open(groups_file, 'r') as f:
            gdata = json.load(f)
            bridges = gdata.get('connections', [])
            
        for pt_a, pt_b in bridges:
            bx = np.array([pt_a[0], pt_b[0]])
            by = np.array([pt_a[1], pt_b[1]])
            
            # Prevod mostu na img coords
            grid_x = (bx - data['min_x']) / data['grid_size']
            grid_y = (by - data['min_y']) / data['grid_size']
            
            cal_a, cal_b, cal_c, cal_d, cal_e, cal_f = data['cal']
            det = cal_a * cal_e - cal_b * cal_d
            oom_x = data['min_x'] + grid_x * data['grid_size']
            oom_y = data['min_y'] + grid_y * data['grid_size']
            img_x = (cal_e * (oom_x - cal_c) - cal_b * (oom_y - cal_f)) / det
            img_y = (cal_a * (oom_y - cal_f) - cal_d * (oom_x - cal_c)) / det
            
            ax.plot(img_x, img_y, color='lime', linewidth=3.0, alpha=0.9, zorder=5)
            ax.scatter(img_x, img_y, color='cyan', s=15, zorder=6)
                
    ax.set_title(f"DIAGNOSTIKA: Vytazeno {count} vrstevnic. Zeleně jsou spoje.",
                 fontsize=13, fontweight='bold')
    ax.axis('off')
    plt.tight_layout()
    print("Hotovo! Zobrazuji okno...")
    plt.show()

def main():
    data = load_common()
    if data is None:
        return
    
    # Rezim --model je smazany, vzdy pouzivame vykreslovani z OMAP
    mode_contour_positions(data)

if __name__ == "__main__":
    main()
