import os, sys, json, math, glob
import numpy as np
from scipy.ndimage import map_coordinates, gaussian_filter

import config
import metriky

# Zjisteni cache slozky
map_name = os.path.splitext(os.path.basename(config.OMAP_FILE))[0]
cache_dir = os.path.join(config.CACHE_DIR, map_name)
schvalene_dir = os.path.join(cache_dir, "schvalene_postupy")
export_dir = os.path.join("export", "livelox")
map_export_dir = os.path.join(export_dir, "data", map_name)
os.makedirs(map_export_dir, exist_ok=True)

print(f"Hledam schvalene postupy v: {schvalene_dir}")
json_files = glob.glob(os.path.join(schvalene_dir, "*.json"))
if not json_files:
    print("Zadne schvalene postupy nenalezeny!")
    sys.exit(1)

# Nacteni mapovych dat
cost_grid = np.load(os.path.join(cache_dir, "cenova_mapa.npy"))
meta = np.load(os.path.join(cache_dir, "cenova_mapa_meta.npy"))
min_x, min_y, max_x, max_y, grid_size = meta

elev_grid = np.load(os.path.join(cache_dir, "vyskova_mapa.npy"))
elev_grid = gaussian_filter(elev_grid, sigma=2)

kalibrace = np.load(os.path.join(cache_dir, "kalibrace.npy"))
cal_a, cal_b, cal_c, cal_d, cal_e, cal_f = kalibrace
A_mat = np.array([[cal_a, cal_b], [cal_d, cal_e]])
A_inv = np.linalg.inv(A_mat)

offset_file = os.path.join(cache_dir, "kalibrace_offset.npy")
offset_dx, offset_dy = 0.0, 0.0
if os.path.exists(offset_file):
    offset_dx, offset_dy = np.load(offset_file)

def grid_to_img(r, c):
    OOM_x = min_x + c * grid_size
    OOM_y = min_y + r * grid_size
    b = np.array([OOM_x - cal_c, OOM_y - cal_f])
    col, row = A_inv.dot(b)
    # Aplikace AI kalibracniho posunu pro dokonale vycentrovani na cesty
    col += offset_dx
    row += offset_dy
    return float(col), float(row)

export_index = []

for file_idx, json_file in enumerate(json_files):
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    out_variants = []
    
    start_gy = data['start']['gy']
    start_gx = data['start']['gx']
    spx, spy = grid_to_img(start_gy, start_gx)
    
    end_gy = data['end']['gy']
    end_gx = data['end']['gx']
    epx, epy = grid_to_img(end_gy, end_gx)
    
    for v_idx, var in enumerate(data.get('variants', [])):
        cesta = var.get('cesta', [])
        if not cesta: continue
        
        # Extrahujeme elevacni data
        y_c = [p[0] for p in cesta]
        x_c = [p[1] for p in cesta]
        z_raw = map_coordinates(elev_grid, [y_c, x_c], order=1)
        # Odstraněno: pohyblivý průměr přes řídké lomy
        z_smooth = z_raw.astype(np.float64)
        
        points = []
        cumulative_time = 0.0
        
        # Pocatecni bod
        px, py = grid_to_img(cesta[0][0], cesta[0][1])
        points.append({
            'x': px, 'y': py,
            'time': 0.0,
            'pace': 0.0,
            'ele': float(z_smooth[0])
        })
        
        # Iterace bodu
        for j in range(1, len(cesta)):
            p1, p2 = cesta[j - 1], cesta[j]
            dy_px = p2[0] - p1[0]
            dx_px = p2[1] - p1[1]
            dist_px = math.hypot(dy_px, dx_px)
            dist_m = dist_px * grid_size * config.NASOBIC_MERITKA
            
            y1, x1 = int(p1[0]), int(p1[1])
            y2, x2 = int(p2[0]), int(p2[1])
            
            c1 = min(3.0, cost_grid[y1, x1])
            c2 = min(3.0, cost_grid[y2, x2])
            
            # Použijeme průměr počátečního a koncového bodu úseku, stejně jako Dijkstra
            # Tím se vyhneme problému se zaokrouhlováním do vedlejších pixelů mimo úzké cesty.
            terren_cost = c1 * 0.5 + c2 * 0.5
                
            z1, z2 = z_smooth[j - 1], z_smooth[j]
            dz = z2 - z1
            sklon = dz / dist_m if dist_m > 0.1 else 0.0
            
            # Ochrana proti mikroschodum a SRTM anomaliim
            is_on_road = c1 < 1.22 and c2 < 1.22
            max_sklon = 0.08 if is_on_road else 0.40
            min_sklon = -0.08 if is_on_road else -0.40
            sklon = max(min_sklon, min(max_sklon, sklon))
            
            val_kopce = 5.0
            if sklon > 0.02:
                sklon_efektivni = sklon - 0.02
                lin_penalta = val_kopce * 1.5 * sklon_efektivni
                exp_penalta = val_kopce * 5.0 * ((sklon_efektivni - 0.15) ** 1.5) if sklon_efektivni > 0.15 else 0.0
                hm = 1.0 + lin_penalta + exp_penalta
            elif sklon < -0.02:
                limit_zrychleni = -0.25
                if sklon >= limit_zrychleni:
                    hm = 1.0 + (sklon * 0.5)
                else:
                    hm = 1.0 + (limit_zrychleni * 0.5) + ((abs(sklon) - abs(limit_zrychleni)) * 1.5)
            else:
                hm = 1.0
                
            step_effort_base = dist_m * terren_cost * hm
            step_time = metriky.vypocti_cas(step_effort_base, config.ZAKLADNI_TEMPO_MIN, config.ZAKLADNI_TEMPO_SEC)
            cumulative_time += step_time
            
            pace = (step_time / dist_m * 1000) if dist_m > 0 else 0
            
            px, py = grid_to_img(p2[0], p2[1])
            points.append({
                'x': px, 'y': py,
                'time': float(cumulative_time),
                'pace': float(pace),
                'ele': float(z2)
            })
            
        out_variants.append({
            'color': v_idx,
            'total_time': cumulative_time,
            'total_dist': var.get('vzdal_m', 0),
            'points': points
        })
        
    route_id = f"postup_{file_idx}"
    out_data = {
        'id': route_id,
        'filename': os.path.basename(json_file),
        'start': {'x': spx, 'y': spy},
        'end': {'x': epx, 'y': epy},
        'variants': out_variants
    }
    
    out_path = os.path.join(map_export_dir, f"{route_id}.json")
    with open(out_path, 'w') as f:
        json.dump(out_data, f)
        
    export_index.append({
        'id': route_id,
        'name': os.path.basename(json_file).replace('.json', ''),
        'file': f"data/{map_name}/{route_id}.json"
    })

index_path = os.path.join(map_export_dir, "index.json")
with open(index_path, 'w') as f:
    json.dump(export_index, f)

# Aktualizace centrálního registru map
maps_json_path = os.path.join(export_dir, "data", "maps.json")
maps_data = []
if os.path.exists(maps_json_path):
    try:
        with open(maps_json_path, 'r', encoding='utf-8') as f:
            maps_data = json.load(f)
    except:
        pass

# Pokud uz tam je, odstranime ji, at ji muzeme pridat na konec (nejnovejsi)
maps_data = [m for m in maps_data if m.get('id') != map_name]

maps_data.append({
    'id': map_name,
    'name': map_name.replace('_', ' '),
    'image': f"../../{config.PNG_FILE}",
    'indexFile': f"data/{map_name}/index.json",
    'count': len(export_index)
})

with open(maps_json_path, 'w', encoding='utf-8') as f:
    json.dump(maps_data, f, ensure_ascii=False, indent=2)

print(f"Exportovano {len(export_index)} postupu do {map_export_dir} s mapou {config.PNG_FILE}")
