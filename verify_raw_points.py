import os
import xml.etree.ElementTree as ET
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import config

def main():
    map_image_file = config.PNG_FILE
    map_name = os.path.splitext(os.path.basename(config.OMAP_FILE))[0]

    print("Načítám obrázek mapy...")
    if not os.path.exists(map_image_file):
        print(f"❌ Nenalezen obrázek mapy: {map_image_file}")
        return
    img = mpimg.imread(map_image_file)

    print("Načítám kalibraci...")
    cache_dir = os.path.join("cache", map_name)
    cal_path = os.path.join(cache_dir, "kalibrace.npy")
    if not os.path.exists(cal_path):
        print(f"❌ Nenalezena kalibrace v {cal_path}. Spusťte nejprve setup_mapa.py pro její vytvoření.")
        return
        
    cal = np.load(cal_path)
    cal_a, cal_b, cal_c, cal_d, cal_e, cal_f = cal

    print("Extrahuji RAW body vrstevnic z OMAP (přesně tak, jak jsou v XML)...")
    tree = ET.parse(config.OMAP_FILE)
    root = tree.getroot()

    symbol_map = {
        elem.attrib.get('id'): elem.attrib.get('code')
        for elem in root.iter()
        if 'symbol' in elem.tag.lower()
    }

    raw_points_x = []
    raw_points_y = []

    for obj in root.iter():
        if 'object' not in obj.tag.lower():
            continue
            
        isom_full = symbol_map.get(obj.attrib.get('symbol', ''), '')
        isom = isom_full.split('.')[0]
        
        # Pouze vrstevnice
        if isom in ['101', '102']:
            for child in obj:
                if 'coords' in child.tag.lower() and child.text:
                    for p in child.text.strip().split(';'):
                        parts = p.strip().split()
                        if len(parts) >= 2:
                            try:
                                # OOM coordinates are in meters when divided by 1000
                                oom_x = float(parts[0]) / 1000.0
                                oom_y = -float(parts[1]) / 1000.0
                                raw_points_x.append(oom_x)
                                raw_points_y.append(oom_y)
                            except ValueError:
                                pass
                    break

    raw_points_x = np.array(raw_points_x)
    raw_points_y = np.array(raw_points_y)

    print(f"Nalezeno {len(raw_points_x)} raw bodů.")

    print("Převádím OOM souřadnice na PNG pixely...")
    # Inverzni transformace z world (OOM) do pixelu
    det = cal_a * cal_e - cal_b * cal_d
    img_cols = (cal_e * (raw_points_x - cal_c) - cal_b * (raw_points_y - cal_f)) / det
    img_rows = (cal_a * (raw_points_y - cal_f) - cal_d * (raw_points_x - cal_c)) / det

    print("Vykresluji...")
    fig, ax = plt.subplots(figsize=(14, 10))
    ax.imshow(img)
    ax.scatter(img_cols, img_rows, color='red', s=3.0, alpha=0.8, marker='.')
    ax.set_title("VERIFIKACE: RAW body vrstevnic z OMAP (červené body) vs PNG", fontsize=14, fontweight='bold')
    ax.axis('off')
    plt.tight_layout()
    print("Zobrazuji okno. Zkontrolujte, zda červené tečky sedí přesně na vrstevnice v mapě.")
    plt.show()

if __name__ == '__main__':
    main()
