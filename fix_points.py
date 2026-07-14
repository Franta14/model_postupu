import os
import json
import glob
import xml.etree.ElementTree as ET
import numpy as np
import config

map_name = os.path.splitext(os.path.basename(config.OMAP_FILE))[0]
cache_dir = os.path.join(config.CACHE_DIR, map_name)

meta = np.load(os.path.join(cache_dir, "cenova_mapa_meta.npy"))
min_x, min_y, max_x, max_y, grid_size = meta

def oom_to_grid(oom_x, oom_y):
    gx = (oom_x - min_x) / grid_size
    gy = (oom_y - min_y) / grid_size
    return int(gy), int(gx)

print("Nacitam OMAP...")
tree = ET.parse(config.OMAP_FILE)
root = tree.getroot()

POINT_SYMBOLS = {
    "109", "110", "111", "112", "115", 
    "203", "204", "205", "206",        
    "303", "311", "312", "313",        
    "417", "418", "419",               
    "524", "525", "526", "527", "530", "531" 
}

symbol_map = {}
for elem in root.iter():
    if 'symbol' in elem.tag.lower():
        s_id = elem.attrib.get('id')
        s_code = elem.attrib.get('code')
        if s_id and s_code: symbol_map[s_id] = s_code

grid_to_oom = {}

for obj in root.iter():
    if 'object' not in obj.tag.lower(): continue
    s_id = obj.attrib.get('symbol')
    if not s_id: continue
    isom_full = symbol_map.get(s_id, '')
    isom = isom_full.split('.')[0]
    if isom not in POINT_SYMBOLS: continue
        
    pts = []
    for child in obj:
        if 'coords' in child.tag.lower() and child.text:
            for p in child.text.strip().split(';'):
                parts = p.strip().split()
                if len(parts) >= 2:
                    try: pts.append((float(parts[0])/1000, -float(parts[1])/1000))
                    except ValueError: pass
            break
            
    if len(pts) == 1:
        oom_x, oom_y = pts[0]
        gy, gx = oom_to_grid(oom_x, oom_y)
        if (gx, gy) not in grid_to_oom:
            grid_to_oom[(gx, gy)] = (oom_x, oom_y)

print(f"Nacteno {len(grid_to_oom)} mapovacich bodu.")

# Patch JSONs
directories = [
    os.path.join(cache_dir, "postupy"),
    os.path.join(cache_dir, "schvalene_postupy")
]

fixed_count = 0
for d in directories:
    if not os.path.exists(d): continue
    for jfile in glob.glob(os.path.join(d, "*.json")):
        with open(jfile, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        modified = False
        
        for key in ["start", "end"]:
            if key in data:
                pt = data[key]
                if "oom_x" not in pt:
                    gx, gy = pt["gx"], pt["gy"]
                    if (gx, gy) in grid_to_oom:
                        pt["oom_x"], pt["oom_y"] = grid_to_oom[(gx, gy)]
                        modified = True
                    else:
                        # Pokud neni v mape z nejakeho duvodu, aproximujeme jako stred bunky
                        pt["oom_x"] = min_x + (gx + 0.5) * grid_size
                        pt["oom_y"] = min_y + (gy + 0.5) * grid_size
                        modified = True
                        
        if modified:
            with open(jfile, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            fixed_count += 1

print(f"✅ Opraveno {fixed_count} souboru.")
