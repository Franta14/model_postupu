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

# Vycisteni starych postupu
import glob
stare_soubory = glob.glob(os.path.join(OUTPUT_DIR, "*.json"))
for sf in stare_soubory:
    os.remove(sf)
print(f"Smazano {len(stare_soubory)} starych postupu.")

# 1. Nacteni dat
try:
    cost_grid = np.load(os.path.join(cache_dir, "cenova_mapa.npy"))
    elev_grid = np.load(os.path.join(cache_dir, "vyskova_mapa.npy"))
    louka_mask = np.load(os.path.join(cache_dir, "louka_mask.npy"))
    map_mask = np.load(os.path.join(cache_dir, "map_mask.npy"))
    meta = np.load(os.path.join(cache_dir, "cenova_mapa_meta.npy"))
    cal = np.load(os.path.join(cache_dir, "kalibrace.npy"))
    
    min_x, min_y, max_x, max_y, grid_size = meta
    cal_a, cal_b, cal_c, cal_d, cal_e, cal_f = cal
    height, width = cost_grid.shape
    
    # Lehke vyhlazeni elevation jako ve staviteli
    from scipy.ndimage import gaussian_filter
    elev_grid = gaussian_filter(elev_grid, sigma=2)
except FileNotFoundError:
    print("Soubory v cache nenalezeny. Spustte nejprve setup_mapa.py")
    sys.exit(1)

# Nacteni vektorovych os cest pro vizualni snap
road_lines_grid = []
try:
    import pickle
    from shapely.geometry import LineString
    with open(os.path.join(cache_dir, "cesty_vektory.pkl"), "rb") as f:
        cesty_raw = pickle.load(f)
    for pts_oom in cesty_raw:
        if len(pts_oom) >= 2:
            # OOM souradnice -> grid souradnice
            pts_grid = []
            for ox, oy in pts_oom:
                gx = (ox - min_x) / grid_size
                gy = (oy - min_y) / grid_size
                pts_grid.append((gx, gy))  # Shapely: (x, y)
            road_lines_grid.append(LineString(pts_grid))
    print(f"[Cesty] Nacteno {len(road_lines_grid)} vektorovych os cest pro vizualni snap.")
except FileNotFoundError:
    print("[!] Vektory cest nenalezeny, snap nebude aktivni. Spustte setup_mapa.py.")

# Crossing penalties (prikopy, srazy)
crossing_grid = None
crossing_path = os.path.join(cache_dir, "crossing_penalties.npy")
if os.path.exists(crossing_path):
    crossing_grid = np.load(crossing_path)
    print(f"[Crossing] Penalties nacteny ({int(np.count_nonzero(crossing_grid))} bunek).")
else:
    print("[!] Crossing penalties nenalezeny, prikopy/srazy ignorovany.")

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
print("Extrahuji validní kontrolní body z OMAP...")
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
        
        # Filtrujeme kontroly mimo mapu (okraj papíru/legenda)
        if not map_mask[gy, gx]:
            continue
            
        # Filtrujeme kontroly přímo na louce nebo ve velmi těsné blízkosti (10 metrů = 2 pixely)
        radius_louka = 2
        y_min_l = max(0, gy - radius_louka)
        y_max_l = min(height, gy + radius_louka + 1)
        x_min_l = max(0, gx - radius_louka)
        x_max_l = min(width, gx + radius_louka + 1)
        if np.any(louka_mask[y_min_l:y_max_l, x_min_l:x_max_l]):
            continue
        
        if cost_grid[gy, gx] < 1.4: # Filtrujeme temne hustniky
            # 1 bunka gridu = 5 metru
            # Zpevnena/lesni cesta (0.6, 0.8): 30 m = 6 px
            # Pesina (0.9): 20 m = 4 px
            # Prusek (0.95): ignorovat
            
            # Kontrola pro pesiny a vetsi cesty (20m = 4px)
            radius_20m = 4
            y_min_20 = max(0, gy - radius_20m)
            y_max_20 = min(height, gy + radius_20m + 1)
            x_min_20 = max(0, gx - radius_20m)
            x_max_20 = min(width, gx + radius_20m + 1)
            subgrid_20m = cost_grid[y_min_20:y_max_20, x_min_20:x_max_20]
            Y, X = np.ogrid[y_min_20-gy:y_max_20-gy, x_min_20-gx:x_max_20-gx]
            mask_20m = X**2 + Y**2 <= radius_20m**2
            
            # Kontrola pro velke cesty (30m = 6px)
            radius_30m = 6
            y_min_30 = max(0, gy - radius_30m)
            y_max_30 = min(height, gy + radius_30m + 1)
            x_min_30 = max(0, gx - radius_30m)
            x_max_30 = min(width, gx + radius_30m + 1)
            subgrid_30m = cost_grid[y_min_30:y_max_30, x_min_30:x_max_30]
            Y, X = np.ogrid[y_min_30-gy:y_max_30-gy, x_min_30-gx:x_max_30-gx]
            mask_30m = X**2 + Y**2 <= radius_30m**2
            
            # Vyrazeni pokud je v mask_20m jakakoliv cesta krome prusku (cost <= 1.10)
            # Pruskuv cost je 1.14, cili 1.11 je bezpecny threshold
            if np.any(subgrid_20m[mask_20m] <= 1.11): 
                continue
                
            # Vyrazeni pokud je v mask_30m velka cesta (cost <= 1.05)
            # Zpevnena 1.00, Lesni 1.05
            if np.any(subgrid_30m[mask_30m] <= 1.06):
                continue
                
            valid_points.append({'isom': isom, 'gx': gx, 'gy': gy, 'oom_x': oom_x, 'oom_y': oom_y})

print(f"Nalezeno {len(valid_points)} bodů ve sjízdném terénu.")

# 3. Kresleni do mapy
print("Načítám PNG mapu pro vykreslování...")
orig_img = Image.open(config.PNG_FILE)
# Vytvorime crop funkci
def draw_leg_image(p1, p2, routes, filename):
    img = orig_img.copy()
    draw = ImageDraw.Draw(img, 'RGBA')
    
    c1, r1 = grid_to_img(p1['gy'], p1['gx'])
    c2, r2 = grid_to_img(p2['gy'], p2['gx'])
    
    # Vypocet bounding boxu (orez)
    # Rozšiřujeme o 400 pixelů (rezerva) na všechny strany
    min_c = min(c1, c2) - 400
    max_c = max(c1, c2) + 400
    min_r = min(r1, r2) - 400
    max_r = max(r1, r2) + 400

    # Zahrneme do výřezu i samotné trasy (pro případ obrovských obíhaček)
    for route in routes:
        for py, px in route:
            c, r = grid_to_img(py, px)
            if c < min_c + 300: min_c = c - 300
            if c > max_c - 300: max_c = c + 300
            if r < min_r + 300: min_r = r - 300
            if r > max_r - 300: max_r = r + 300
    
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


# ================================================================
# 4. MASIVNÍ GENEROVÁNÍ POSTUPŮ – PLNÉ POKRYTÍ MAPY
# ================================================================
import time

DELKOVE_ROZSAHY = config.DELKOVE_ROZSAHY
real_width = width * grid_size * config.NASOBIC_MERITKA
real_height = height * grid_size * config.NASOBIC_MERITKA
area_km2 = (real_width * real_height) / 1_000_000.0
# Auto-scaling: max 12 kandidatu na km2, ale nikdy vice nez 600 celkem
MAX_KANDIDATU = min(int(area_km2 * config.HUSTOTA_KANDIDATU_KM2), 1500)
print(f"Rozloha mapy: {area_km2:.2f} km^2 -> Cílový počet kandidátů: {MAX_KANDIDATU} (max 1500, hustota {config.HUSTOTA_KANDIDATU_KM2}/km^2)")


def is_viable_pair(p1, p2):
    """Vrací Obstacle Score. Pokud je skóre < 0 (neprůchodná voda, budovy, nebo málo metrů), vrací -1.0."""
    # 1. Kontrola nepřekonatelných překážek (voda, budovy)
    n = 10
    impassable = 0
    for t in np.linspace(0.1, 0.9, n):
        y = max(0, min(height - 1, int(p1['gy'] + t * (p2['gy'] - p1['gy']))))
        x = max(0, min(width - 1, int(p1['gx'] + t * (p2['gx'] - p1['gx']))))
        if cost_grid[y, x] >= 9000:
            impassable += 1
    if impassable >= n * 0.4:
        return -1.0

    # 2. Výpočet Skóre Překážky
    obstacle_score = generator_engine.zjisti_narocnost_primky(
        p1, p2, cost_grid, elev_grid, grid_size, config.NASOBIC_MERITKA, louka_mask
    )
    
    return obstacle_score


def vzdalenost_m_ctrl(c1, c2):
    """Vzdálenost dvou kontrol v metrech."""
    dy = (c1['gy'] - c2['gy']) * grid_size * config.NASOBIC_MERITKA
    dx = (c1['gx'] - c2['gx']) * grid_size * config.NASOBIC_MERITKA
    return np.sqrt(dy**2 + dx**2)


import math

def get_signature(pos):
    """Vypočítá otisk (Signature) postupu pro deduplikaci."""
    p1 = pos['p1']
    p2 = pos['p2']
    
    # Střed (těžiště) v metrech
    mid_y = (p1['gy'] + p2['gy']) / 2.0 * grid_size * config.NASOBIC_MERITKA
    mid_x = (p1['gx'] + p2['gx']) / 2.0 * grid_size * config.NASOBIC_MERITKA
    
    # Úhel v radiánech (0 až PI, protože směr A->B je stejný problém jako B->A)
    dy = p2['gy'] - p1['gy']
    dx = p2['gx'] - p1['gx']
    angle = math.atan2(dy, dx)
    if angle < 0:
        angle += math.pi
    
    # Délka v metrech
    length = pos['dist_m']
    
    return mid_y, mid_x, angle, length

def jsou_podobne(pos1, pos2):
    """
    Dva postupy jsou podobné (duplicitní), pokud se odehrávají ve stejné oblasti,
    mají podobný směr a podobnou délku.
    """
    y1, x1, a1, l1 = get_signature(pos1)
    y2, x2, a2, l2 = get_signature(pos2)
    
    # 1. Kontrola těžiště (zda jsou ve stejném lese) - normálně 400 m
    # Pro velmi dlouhé postupy (>1200m) jsme tolerantnější a vyhodíme je, jen pokud
    # se jejich středy shodují v rozmezí 150m (jinak se jich totiž spousta vymlátí)
    dist_centers = math.sqrt((y1 - y2)**2 + (x1 - x2)**2)
    min_dist_centers = 300.0 if max(l1, l2) < 1200 else 150.0
    if dist_centers > min_dist_centers:
        return False
        
    # 2. Kontrola délky (zda jde o podobně dlouhý postup) - rozdíl max 30%
    len_ratio = abs(l1 - l2) / max(l1, l2) if max(l1, l2) > 0 else 0
    if len_ratio > 0.30:
        return False
        
    # 3. Kontrola směru (zda běží podobným směrem) - rozdíl max 25 stupňů
    angle_diff = abs(a1 - a2)
    # Kruhová diference (0..PI)
    if angle_diff > math.pi / 2:
        angle_diff = math.pi - angle_diff
        
    angle_deg = math.degrees(angle_diff)
    if angle_deg > 25.0:
        return False
        
    return True


# ── FÁZE 1: Generování kandidátních párů ──────────────────────

dijkstra_base_grid = cost_grid.copy()

print("=" * 60)
print("  MASIVNI GENEROVANI POSTUPU")
print("=" * 60)
print()
print("Faze 1/4: Generuji kandidatni pary...")
random.seed()

candidates_by_range = {i: [] for i in range(len(DELKOVE_ROZSAHY))}
SAMPLING_ATTEMPTS = 500_000

for _ in range(SAMPLING_ATTEMPTS):
    p1, p2 = random.sample(valid_points, 2)
    dist_grid = np.sqrt((p1['gx'] - p2['gx'])**2 + (p1['gy'] - p2['gy'])**2)
    dist_m = dist_grid * grid_size * config.NASOBIC_MERITKA

    for i, (lo, hi) in enumerate(DELKOVE_ROZSAHY):
        if lo <= dist_m <= hi:
            score = is_viable_pair(p1, p2)
            # Extrémně tvrdý limit pro Skóre Překážky. 
            # Bílý les na rovině má skóre 0. 
            # 50 bodů znamená buď menší kopec, kousek hustníku nebo spoustu cest okolo.
            if score > 50:
                candidates_by_range[i].append((p1, p2, dist_m, score))
            break

# Stratifikovaný výběr: náhodně z elitních kandidátů
# Dáme 50% kapacity nejdelším postupům, zbytek rovnoměrně
candidates = []
for i in range(len(DELKOVE_ROZSAHY)):
    cands = candidates_by_range[i]
    random.shuffle(cands)
    
    # Alokace kapacity (poslední rozsah dostane víc)
    if i == len(DELKOVE_ROZSAHY) - 1:
        per_range = int(MAX_KANDIDATU * 0.5)
    else:
        per_range = int(MAX_KANDIDATU * 0.25)
        
    selected_from_range = cands[:per_range]
    lo, hi = DELKOVE_ROZSAHY[i]
    print(f"   {lo:>4}-{hi:>4}m: {len(cands):>5} nalezeno elitních, {len(selected_from_range):>3} vybrano")
    # Přidat do celkových kandidátů (ořízneme skóre)
    candidates.extend([(c[0], c[1], c[2]) for c in selected_from_range])

# Doplnění zbývajících slotů z přebytku (pokud v některé kategorii nebylo dost)
remaining_slots = MAX_KANDIDATU - len(candidates)
if remaining_slots > 0:
    overflow = []
    for i in range(len(DELKOVE_ROZSAHY)):
        # Vezmeme ty, kteří se nedostali do per_range
        if i == len(DELKOVE_ROZSAHY) - 1:
            per_range_used = int(MAX_KANDIDATU * 0.5)
        else:
            per_range_used = int(MAX_KANDIDATU * 0.25)
        overflow.extend(candidates_by_range[i][per_range_used:])
    random.shuffle(overflow)
    candidates.extend([(c[0], c[1], c[2]) for c in overflow[:remaining_slots]])

random.shuffle(candidates)
print(f"   Celkem: {len(candidates)} kandidatu k vyhodnoceni.\n")


# ── FÁZE 2: Dijkstra analýza + skóre zajímavosti ─────────────
print(f"Faze 2/4: Dijkstra analyza ({len(candidates)} kandidatu)...")
t_start = time.time()

scored_postupy = []
skipped_boring = 0


import concurrent.futures

def _eval_candidate(args):
    idx, p1, p2, dist_m = args
    # Progress
    mask = generator_engine.vytvor_masku_elipsy(
        (p1['gy'], p1['gx']), (p2['gy'], p2['gx']),
        height, width, rozsireni=0.6
    )

    routes = []
    routes_metadata = []
    
    # Dynamické prahy podle vzdušné vzdálenosti
    import math
    vz_vzdal = math.sqrt((p1['gx'] - p2['gx'])**2 + (p1['gy'] - p2['gy'])**2) * grid_size * config.NASOBIC_MERITKA
    if vz_vzdal < 500:
        min_rozkol = 30.0
        threshold_m = 15.0
        max_shared = 0.50 # Přísnější na sdílenou trasu
    elif vz_vzdal > 1500:
        min_rozkol = 70.0
        threshold_m = 35.0
        max_shared = 0.35 # Dlouhé postupy musí mít velký rozkol
    else:
        ratio = (vz_vzdal - 500) / 1000.0
        min_rozkol = 30.0 + ratio * 40.0
        threshold_m = 15.0 + ratio * 20.0
        max_shared = 0.50 - ratio * 0.15

    penalized_grid = dijkstra_base_grid.copy()

    for v in range(3):
        dist_map, py, px = generator_engine.dijkstra_heatmap(
            penalized_grid, elev_grid,
            (p1['gy'], p1['gx']), mask, grid_size,
            config.NASOBIC_MERITKA, kopce_vaha=5.0, direction='forward',
            crossing_grid=crossing_grid
        )

        route = generator_engine.trasuj_cestu(
            py, px, (p1['gy'], p1['gx']), (p2['gy'], p2['gx'])
        )
        if not route:
            return None

        route_smooth = generator_engine.vyhlad_cestu(route, cost_grid, vyhlazeni=3)
        route_smooth = generator_engine.rozbij_primky(route_smooth, cost_grid, grid_size * config.NASOBIC_MERITKA)

        if v > 0:
            max_rozkol_val, avg_rozkol_val, shared_ratio = generator_engine.analyzuj_podobnost(route_smooth, routes, grid_size * config.NASOBIC_MERITKA, threshold_m=threshold_m)
            
            # 1. Břicho alespoň min_rozkol
            if max_rozkol_val < min_rozkol:
                return None
                
            # 2. NESMÍ sdílet víc jak max_shared délky trasy s ostatními
            # Pro dlouhé postupy (>1200m) jsme benevolentnější ke sdílení trasy
            allowed_shoda = config.MAX_SHODA
            if dist_m > 1200.0:
                allowed_shoda = 0.75 # Můžou sdílet až 75 % (místo 65 %)
                
            if shared_ratio > allowed_shoda:
                return None

        routes.append(route_smooth)

        vzd, prev, usili, usili_real, road_ratio = metriky.spocitat_metriky(
            route_smooth, cost_grid, elev_grid,
            grid_size, config.NASOBIC_MERITKA, val_kopce=5.0
        )
        cas_s = metriky.vypocti_cas(
            usili_real, config.ZAKLADNI_TEMPO_MIN, config.ZAKLADNI_TEMPO_SEC
        )
        tempo_s_na_km = (cas_s / vzd) * 1000 if vzd > 0 else 0

        routes_metadata.append({
            "vzdal_m": round(vzd),
            "prevyseni_m": round(prev),
            "cas_s": round(cas_s),
            "tempo_str": metriky.formatuj_cas(tempo_s_na_km),
            "cesta": route_smooth
        })

        penalized_grid = generator_engine.penalizuj_grid(
            penalized_grid, route_smooth, config.PODOBNOST_RADIUS * 2,
            grid=cost_grid  # Predavame original pro terrain-aware penalizaci
        )

    # Pro extrémně dlouhé postupy nám stačí i jen 2 dobré varianty!
    min_variants = config.POCET_VARIANT
    if dist_m > 1200.0:
        min_variants = 2
        
    if len(routes) < min_variants:
        return None

    # Skóre zajímavosti
    # 1. Divergence: průměrná Hausdorffova vzdálenost (max split) v metrech normovaná vůči 100m
    max_splits = []
    shared_ratios = []
    for i in range(1, len(routes)):
        split, avg, shared = generator_engine.analyzuj_podobnost(routes[i], routes[:i], grid_size * config.NASOBIC_MERITKA, threshold_m=threshold_m)
        max_splits.append(split)
        shared_ratios.append(shared)
        
    avg_split = np.mean(max_splits) if max_splits else 0.0
    divergence = avg_split / 100.0
    
    avg_shared = np.mean(shared_ratios) if shared_ratios else 0.0

    # 2. Vyváženost: poměr nejrychlejší/nejpomalejší
    times = [rm['cas_s'] for rm in routes_metadata]
    balance = min(times) / max(times) if max(times) > 0 else 0

    # 3. Bonus za 3 varianty
    count_bonus = 1.0 + 0.25 * (len(routes) - 2)

    # 4. Penalizace za sdílenou délku trasy (čím víc sdílí, tím nižší skóre)
    # 0% sdílení = 1.0, 65% sdílení = 0.35
    shared_penalty = 1.0 - avg_shared

    score = divergence * balance * count_bonus * shared_penalty

    if score < config.MIN_ZAJIMAVOST:
        return None

    return {
        'p1': p1,
        'p2': p2,
        'dist_m': dist_m,
        'routes': routes,
        'routes_metadata': routes_metadata,
        'score': score,
        'divergence': divergence,
        'balance': balance,
        'n_variants': len(routes)
    }



with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
    futures = [ex.submit(_eval_candidate, (i, p1, p2, d)) for i, (p1, p2, d) in enumerate(candidates)]
    
    for i, future in enumerate(concurrent.futures.as_completed(futures)):
        if i % 25 == 0:
            elapsed = time.time() - t_start
            if i > 0:
                eta = (elapsed / i) * (len(candidates) - i)
                print(f"   [{i:>3}/{len(candidates)}] {len(scored_postupy)} zajimavych | ~{eta:.0f}s zbyva", flush=True)
            else:
                print(f"   [{i:>3}/{len(candidates)}] Startuji...", flush=True)
                
        res = future.result()
        if res is not None:
            scored_postupy.append(res)
        else:
            skipped_boring += 1

elapsed_phase2 = time.time() - t_start
print(f"\n   Dokonceno za {elapsed_phase2:.0f}s.")
print(f"   {len(scored_postupy)} postupu nad hranici zajimavosti ({skipped_boring} vyrazeno).\n")


# ── FÁZE 3: Chytrý výběr (deduplikace) ───────────────────────
print("Faze 3/4: Chytry vyber (deduplikace)...")

scored_postupy.sort(key=lambda x: x['score'], reverse=True)

selected = []
remaining_pool = list(scored_postupy)

while remaining_pool:
    best = remaining_pool.pop(0)
    selected.append(best)
    remaining_pool = [p for p in remaining_pool if not jsou_podobne(best, p)]

# Zruseny limit: selected = selected

print(f"   {len(scored_postupy)} -> {len(selected)} unikatnich postupu")

# Statistiky
print(f"\n   Rozdeleni podle delky:")
for lo, hi in DELKOVE_ROZSAHY:
    in_range = [p for p in selected if lo <= p['dist_m'] <= hi]
    if in_range:
        avg_s = np.mean([p['score'] for p in in_range])
        print(f"   {lo:>4}-{hi:>4}m: {len(in_range):>3} postupu (prumerne skore {avg_s:.2f})")
print()


# ── FÁZE 4: Export ────────────────────────────────────────────
print(f"Faze 4/4: Ukladam {len(selected)} postupu...")

# Smazat staré soubory
old_count = 0
for f in os.listdir(OUTPUT_DIR):
    if f.startswith("postup_") and (f.endswith(".json") or f.endswith(".png")):
        try:
            os.remove(os.path.join(OUTPUT_DIR, f))
            old_count += 1
        except PermissionError:
            pass
if old_count:
    print(f"   Smazano {old_count} starych souboru.")

for i, postup in enumerate(selected):
    p1, p2 = postup['p1'], postup['p2']

    # Snap na vektorové osy cest (vizuálně a do JSON)
    routes_viz = []
    for v_idx, rm in enumerate(postup['routes_metadata']):
        snapped = generator_engine.snap_na_cesty(rm['cesta'], cost_grid, road_lines_grid)
        rm['cesta'] = snapped
        routes_viz.append(snapped)

    score_pct = int(postup['score'] * 100)
    base_fname = os.path.join(
        OUTPUT_DIR,
        f"postup_{i+1:03d}_{int(postup['dist_m'])}m_s{score_pct}"
    )

    draw_leg_image(p1, p2, routes_viz, base_fname + ".png")

    json_data = {
        "start": p1,
        "end": p2,
        "dist_m": postup['dist_m'],
        "score": round(postup['score'], 3),
        "divergence": round(postup['divergence'], 3),
        "balance": round(postup['balance'], 3),
        "n_variants": postup['n_variants'],
        "variants": postup['routes_metadata']
    }
    with open(base_fname + ".json", "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=4, cls=NumpyEncoder)

    if (i + 1) % 25 == 0 or i + 1 == len(selected):
        print(f"   [{i+1}/{len(selected)}] ulozeno...", flush=True)

total_time = time.time() - t_start
print(f"\n{'='*60}")
print(f"  HOTOVO! {len(selected)} zajimavych postupu")
print(f"  Cas: {total_time:.0f}s")
print(f"  Slozka: {OUTPUT_DIR}")
print(f"  Dalsi krok: python 10_kurator_nastroj.py")
print(f"{'='*60}")
