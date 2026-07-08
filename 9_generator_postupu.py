import os
import sys
import xml.etree.ElementTree as ET
import numpy as np
import random
import json
import config
from PIL import Image, ImageDraw
import matplotlib.pyplot as plt
import generator_engine
import metriky

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer): return int(obj)
        if isinstance(obj, np.floating): return float(obj)
        if isinstance(obj, np.ndarray): return obj.tolist()
        return super(NumpyEncoder, self).default(obj)

# Nacteme engine pro hledani tras

map_name = os.path.splitext(os.path.basename(config.OMAP_FILE))[0]
cache_dir = os.path.join(config.CACHE_DIR, map_name)
OUTPUT_DIR = os.path.join(config.CACHE_DIR, map_name, "postupy")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 1. Nacteni dat
try:
    cost_grid = np.load(os.path.join(cache_dir, "cenova_mapa.npy"))
    elev_grid = np.load(os.path.join(cache_dir, "vyskova_mapa.npy"))
    meta = np.load(os.path.join(cache_dir, "cenova_mapa_meta.npy"))
    cal = np.load(os.path.join(cache_dir, "kalibrace.npy"))
    
    min_x, min_y, max_x, max_y, grid_size = meta
    cal_a, cal_b, cal_c, cal_d, cal_e, cal_f = cal
    height, width = cost_grid.shape
    
    # Lehke vyhlazeni elevation jako ve staviteli
    from scipy.ndimage import gaussian_filter
    elev_grid = gaussian_filter(elev_grid, sigma=2)
except FileNotFoundError:
    print("❌ Soubory v cache nenalezeny. Spustte nejprve setup_mapa.py")
    sys.exit(1)

def oom_to_grid(oom_x, oom_y):
    gx = (oom_x - min_x) / grid_size
    gy = (oom_y - min_y) / grid_size
    return max(0, min(height - 1, int(gy))), max(0, min(width - 1, int(gx)))

def grid_to_img(gy, gx):
    oom_x = min_x + gx * grid_size
    oom_y = min_y + gy * grid_size
    det = cal_a * cal_e - cal_b * cal_d
    if abs(det) < 1e-12: return 0, 0
    col = (cal_e * (oom_x - cal_c) - cal_b * (oom_y - cal_f)) / det
    row = (cal_a * (oom_y - cal_f) - cal_d * (oom_x - cal_c)) / det
    return int(col), int(row)

# 2. Extrakce validnich bodu
print("🗺️ Extrahuji validní kontrolní body z OMAP...")
tree = ET.parse(config.OMAP_FILE)
root = tree.getroot()

symbol_map = {}
for elem in root.iter():
    if 'symbol' in elem.tag.lower():
        s_id = elem.attrib.get('id')
        s_code = elem.attrib.get('code')
        if s_id and s_code: symbol_map[s_id] = s_code

POINT_SYMBOLS = {
    "109", "110", "111", "112", "115", # Terenní tvary (kupky, jámy)
    "203", "204", "205", "206",        # Kameny a skalky (vyloucena balvanova pole a shluky 207-212)
    "303", "311", "312", "313",        # Voda (prameny, studny, vyrazne objekty)
    "417", "418", "419",               # Vegetacni objekty
    "524", "525", "526", "527", "530", "531" # Umele objekty
}
valid_points = []

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
        if cost_grid[gy, gx] < 1.4: # Filtrujeme temne hustniky
            valid_points.append({'isom': isom, 'gx': gx, 'gy': gy})

print(f"✅ Nalezeno {len(valid_points)} bodů ve sjízdném terénu.")

# 3. Kresleni do mapy
print("🖼️ Načítám PNG mapu pro vykreslování...")
orig_img = Image.open(config.PNG_FILE)
# Vytvorime crop funkci
def draw_leg_image(p1, p2, routes, filename):
    img = orig_img.copy()
    draw = ImageDraw.Draw(img, 'RGBA')
    
    c1, r1 = grid_to_img(p1['gy'], p1['gx'])
    c2, r2 = grid_to_img(p2['gy'], p2['gx'])
    
    # Vypocet bounding boxu (orez) - 1 km okoli (1000 / scale)
    # Radeji orizneme +/- 800 pixelu od obou kontrol
    min_c = min(c1, c2) - 800
    max_c = max(c1, c2) + 800
    min_r = min(r1, r2) - 800
    max_r = max(r1, r2) + 800
    
    PURPLE = (200, 0, 200, 255)
    
    # Zjisteni velikosti kolecka (cca radius 35 px, tloustka 5 px)
    radius = 35
    thickness = 5
    
    # 1. Kresleni tras (volby)
    colors = [(255, 0, 0, 150), (0, 0, 255, 150), (0, 255, 0, 150)] # Cervena, Modra, Zelena
    for i, route in enumerate(routes):
        if not route: continue
        color = colors[i % len(colors)]
        
        # Převedeme trasu (v pixelech gridu) na pixely obrázku
        img_route = [grid_to_img(gy, gx) for gy, gx in route]
        
        if len(img_route) > 1:
            draw.line(img_route, fill=color, width=8, joint='curve')
            
    # 2. Spojnice (prerusená čára, přerušení blízko koleček)
    # Nakreslíme čáru, ale zkrátíme ji o radius kolečka na obou koncích
    dist = np.sqrt((c2-c1)**2 + (r2-r1)**2)
    if dist > radius * 2:
        dx, dy = (c2-c1)/dist, (r2-r1)/dist
        start_line = (c1 + dx*radius, r1 + dy*radius)
        end_line = (c2 - dx*radius, r2 - dy*radius)
        draw.line([start_line, end_line], fill=PURPLE, width=4)
        
    # 3. Kresleni startovniho trojuhelniku (Start)
    import math
    angle = math.atan2(r2-r1, c2-c1)
    # Trojuhelnik ukazuje k cili (rovnostranny trojuhelnik se stredem na kontrole)
    R = radius * 1.15
    angle1 = angle
    angle2 = angle + 2 * math.pi / 3
    angle3 = angle - 2 * math.pi / 3
    
    p1_t = (c1 + math.cos(angle1)*R, r1 + math.sin(angle1)*R)
    p2_t = (c1 + math.cos(angle2)*R, r1 + math.sin(angle2)*R)
    p3_t = (c1 + math.cos(angle3)*R, r1 + math.sin(angle3)*R)
    draw.polygon([p1_t, p2_t, p3_t], outline=PURPLE, fill=None, width=thickness)
    
    # 4. Kresleni ciloveho kolecka (Cil)
    draw.ellipse([c2-radius, r2-radius, c2+radius, r2+radius], outline=PURPLE, width=thickness)

    # Orez
    min_c, min_r = max(0, min_c), max(0, min_r)
    max_c, max_r = min(img.width, max_c), min(img.height, max_r)
    crop = img.crop((min_c, min_r, max_c, max_r))
    
    # Zmensit pokud je obri
    if crop.width > 1200 or crop.height > 1200:
        crop.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
        
    crop.save(filename, "PNG", optimize=True)


# 4. Generovani tras
print("🚀 Hledám postupy...")
random.seed(123)

generated_count = 0
attempts = 0

print("Filtruji páry s vhodnou vzdáleností...")
valid_pairs = []
for i in range(50000):
    p1, p2 = random.sample(valid_points, 2)
    dist_grid = np.sqrt((p1['gx'] - p2['gx'])**2 + (p1['gy'] - p2['gy'])**2)
    dist_paper_mm = dist_grid * grid_size
    dist_m = dist_paper_mm * config.NASOBIC_MERITKA
    if 800 <= dist_m <= 1500:
        valid_pairs.append((p1, p2, dist_m))

print(f"Nalezeno {len(valid_pairs)} kandidátů na postupy.")

for p1, p2, dist_m in valid_pairs:
    if generated_count >= 5:
        break
    attempts += 1
        
    print(f"Hledám trasy pro {p1['isom']} -> {p2['isom']} ({dist_m:.0f}m)")
    
    mask = generator_engine.vytvor_masku_elipsy((p1['gy'], p1['gx']), (p2['gy'], p2['gx']), height, width, rozsireni=0.6)
    
    routes = []
    routes_metadata = []
    penalized_grid = cost_grid.copy()
    
    for v in range(3):
        dist_map, py, px = generator_engine.dijkstra_heatmap(
            penalized_grid, elev_grid, (p1['gy'], p1['gx']), mask, grid_size, config.NASOBIC_MERITKA, kopce_vaha=25.0, direction='forward'
        )
        
        route = generator_engine.trasuj_cestu(py, px, (p1['gy'], p1['gx']), (p2['gy'], p2['gx']))
        if not route:
            break
            
        route_smooth = generator_engine.vyhlad_cestu(route, cost_grid, vyhlazeni=3)
        
        # Otestovat podobnost s předchozími (pokud se to moc neliší, končíme)
        podobnost = generator_engine.merit_podobnost(route_smooth, routes, height, width, config.PODOBNOST_RADIUS)
        if v > 0 and podobnost > 0.8: # Prilis podobne, nenaslo to 2. volbu
            print(f"  Varianta {v+1} vyřazena (příliš podobná: {podobnost*100:.0f}%)")
            continue
            
        routes.append(route_smooth)
        
        # Spocitat metriky
        vzd, prev, usili, usili_real, road_ratio = metriky.spocitat_metriky(
            route_smooth, cost_grid, elev_grid, grid_size, config.NASOBIC_MERITKA, val_kopce=5.0
        )
        cas_s = metriky.vypocti_cas(usili_real, config.ZAKLADNI_TEMPO_MIN, config.ZAKLADNI_TEMPO_SEC)
        tempo_s_na_km = (cas_s / vzd) * 1000 if vzd > 0 else 0
        
        routes_metadata.append({
            "vzdal_m": round(vzd),
            "prevyseni_m": round(prev),
            "cas_s": round(cas_s),
            "tempo_str": metriky.formatuj_cas(tempo_s_na_km),
            "cesta": route_smooth # List of (y,x) coords
        })
        
        # Penalizovat pro dalsi hledani
        penalized_grid = generator_engine.penalizuj_grid(penalized_grid, route_smooth, config.PODOBNOST_RADIUS * 2)

    # Hodnotitel zajimavosti
    if len(routes) >= 2:
        print(f"  ✅ Nalezeny {len(routes)} smysluplné varianty! Generuji náhled a JSON...")
        base_fname = os.path.join(OUTPUT_DIR, f"postup_{generated_count+1}_{int(dist_m)}m")
        draw_leg_image(p1, p2, routes, base_fname + ".png")
        
        # Ulozit JSON
        json_data = {
            "start": p1,
            "end": p2,
            "dist_m": dist_m,
            "variants": routes_metadata
        }
        with open(base_fname + ".json", "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=4, cls=NumpyEncoder)
            
        generated_count += 1
    else:
        print("  ❌ Postup nemá reálné alternativy (nudný).")

print(f"🎉 Hotovo! Vygenerováno {generated_count} zajímavých postupů v {OUTPUT_DIR}")
