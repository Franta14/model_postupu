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
    print(f"📏 Načteno {len(road_lines_grid)} vektorových os cest pro vizuální snap.")
except FileNotFoundError:
    print("⚠️ Vektory cest nenalezeny, snap nebude aktivní. Spusťte setup_mapa.py.")

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
            valid_points.append({'isom': isom, 'gx': gx, 'gy': gy, 'oom_x': oom_x, 'oom_y': oom_y})

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


# ================================================================
# 4. MASIVNÍ GENEROVÁNÍ POSTUPŮ – PLNÉ POKRYTÍ MAPY
# ================================================================
import time

DELKOVE_ROZSAHY = config.DELKOVE_ROZSAHY
MAX_KANDIDATU = config.MAX_KANDIDATU


def is_viable_pair(p1, p2):
    """Odmítne páry kde >40% přímky je neprůchodná (zdi, voda)."""
    n = 10
    impassable = 0
    for t in np.linspace(0.1, 0.9, n):
        y = max(0, min(height - 1, int(p1['gy'] + t * (p2['gy'] - p1['gy']))))
        x = max(0, min(width - 1, int(p1['gx'] + t * (p2['gx'] - p1['gx']))))
        if cost_grid[y, x] >= 9000:
            impassable += 1
    return impassable < n * 0.4


def vzdalenost_m_ctrl(c1, c2):
    """Vzdálenost dvou kontrol v metrech."""
    dy = (c1['gy'] - c2['gy']) * grid_size * config.NASOBIC_MERITKA
    dx = (c1['gx'] - c2['gx']) * grid_size * config.NASOBIC_MERITKA
    return np.sqrt(dy**2 + dx**2)


def jsou_podobne(pos1, pos2):
    """Dva postupy jsou podobné pokud mají blízké starty+cíle a podobnou délku."""
    d_ss = vzdalenost_m_ctrl(pos1['p1'], pos2['p1'])
    d_ee = vzdalenost_m_ctrl(pos1['p2'], pos2['p2'])
    d_se = vzdalenost_m_ctrl(pos1['p1'], pos2['p2'])
    d_es = vzdalenost_m_ctrl(pos1['p2'], pos2['p1'])

    max_d = config.DEDUP_CTRL_RADIUS
    similar_forward = d_ss < max_d and d_ee < max_d
    similar_reverse = d_se < max_d and d_es < max_d

    if not (similar_forward or similar_reverse):
        return False

    len_ratio = abs(pos1['dist_m'] - pos2['dist_m']) / max(pos1['dist_m'], pos2['dist_m'])
    return len_ratio < config.DEDUP_LEN_RATIO


# ── FÁZE 1: Generování kandidátních párů ──────────────────────

print("Vytvářím mapu přírodního vlnění (low-frequency noise)...")
np.random.seed(42) # Pevný seed pro konzistenci vlnění mezi běhy
noise_raw = np.random.uniform(-1, 1, size=(height // 30 + 1, width // 30 + 1))
from scipy.ndimage import zoom
noise_smooth = zoom(noise_raw, 30)[:height, :width]
noise_min, noise_max = noise_smooth.min(), noise_smooth.max()
# Škálování na multiplier [0.97, 1.03] (+- 3%) pro rozbití přímek
noise_scaled = 0.97 + (noise_smooth - noise_min) / (noise_max - noise_min) * 0.06
dijkstra_base_grid = cost_grid * noise_scaled

print("=" * 60)
print("  MASIVNI GENEROVANI POSTUPU")
print("=" * 60)
print()
print("Faze 1/4: Generuji kandidatni pary...")
random.seed()

candidates_by_range = {i: [] for i in range(len(DELKOVE_ROZSAHY))}
SAMPLING_ATTEMPTS = 100_000

for _ in range(SAMPLING_ATTEMPTS):
    p1, p2 = random.sample(valid_points, 2)
    dist_grid = np.sqrt((p1['gx'] - p2['gx'])**2 + (p1['gy'] - p2['gy'])**2)
    dist_m = dist_grid * grid_size * config.NASOBIC_MERITKA

    for i, (lo, hi) in enumerate(DELKOVE_ROZSAHY):
        if lo <= dist_m <= hi:
            if is_viable_pair(p1, p2):
                candidates_by_range[i].append((p1, p2, dist_m))
            break

# Stratifikovaný výběr: rovnoměrně z každého rozsahu
per_range = MAX_KANDIDATU // len(DELKOVE_ROZSAHY)
candidates = []
for i in range(len(DELKOVE_ROZSAHY)):
    cands = candidates_by_range[i]
    random.shuffle(cands)
    selected_from_range = cands[:per_range]
    lo, hi = DELKOVE_ROZSAHY[i]
    print(f"   {lo:>4}-{hi:>4}m: {len(cands):>5} nalezeno, {len(selected_from_range):>3} vybrano")
    candidates.extend(selected_from_range)

# Doplnění zbývajících slotů z přebytku
remaining_slots = MAX_KANDIDATU - len(candidates)
if remaining_slots > 0:
    overflow = []
    for i in range(len(DELKOVE_ROZSAHY)):
        overflow.extend(candidates_by_range[i][per_range:])
    random.shuffle(overflow)
    candidates.extend(overflow[:remaining_slots])

random.shuffle(candidates)
print(f"   Celkem: {len(candidates)} kandidatu k vyhodnoceni.\n")


# ── FÁZE 2: Dijkstra analýza + skóre zajímavosti ─────────────
print(f"Faze 2/4: Dijkstra analyza ({len(candidates)} kandidatu)...")
t_start = time.time()

scored_postupy = []
skipped_boring = 0

for idx, (p1, p2, dist_m) in enumerate(candidates):
    # Progress
    if idx % 25 == 0:
        elapsed = time.time() - t_start
        if idx > 0:
            eta = (elapsed / idx) * (len(candidates) - idx)
            print(f"   [{idx:>3}/{len(candidates)}] {len(scored_postupy)} zajimavych | ~{eta:.0f}s zbyva", flush=True)
        else:
            print(f"   [{idx:>3}/{len(candidates)}] Startuji...", flush=True)

    mask = generator_engine.vytvor_masku_elipsy(
        (p1['gy'], p1['gx']), (p2['gy'], p2['gx']),
        height, width, rozsireni=0.6
    )

    routes = []
    routes_metadata = []
    penalized_grid = dijkstra_base_grid.copy()

    for v in range(3):
        dist_map, py, px = generator_engine.dijkstra_heatmap(
            penalized_grid, elev_grid,
            (p1['gy'], p1['gx']), mask, grid_size,
            config.NASOBIC_MERITKA, kopce_vaha=5.0, direction='forward'
        )

        route = generator_engine.trasuj_cestu(
            py, px, (p1['gy'], p1['gx']), (p2['gy'], p2['gx'])
        )
        if not route:
            break

        route_smooth = generator_engine.vyhlad_cestu(route, cost_grid, vyhlazeni=3)

        podobnost = generator_engine.merit_podobnost(
            route_smooth, routes, height, width, config.PODOBNOST_RADIUS
        )
        if v > 0 and podobnost > 0.8:
            continue

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
            penalized_grid, route_smooth, config.PODOBNOST_RADIUS * 2
        )

    if len(routes) < 2:
        skipped_boring += 1
        continue

    # Skóre zajímavosti
    # 1. Divergence: symetrická průměrná nepodobnost
    pairwise_sims = []
    for i in range(len(routes)):
        for j in range(i + 1, len(routes)):
            s_ij = generator_engine.merit_podobnost(
                routes[i], [routes[j]], height, width, config.PODOBNOST_RADIUS
            )
            s_ji = generator_engine.merit_podobnost(
                routes[j], [routes[i]], height, width, config.PODOBNOST_RADIUS
            )
            pairwise_sims.append((s_ij + s_ji) / 2)
    divergence = 1.0 - np.mean(pairwise_sims)

    # 2. Vyváženost: poměr nejrychlejší/nejpomalejší
    times = [rm['cas_s'] for rm in routes_metadata]
    balance = min(times) / max(times) if max(times) > 0 else 0

    # 3. Bonus za 3 varianty
    count_bonus = 1.0 + 0.25 * (len(routes) - 2)

    score = divergence * balance * count_bonus

    if score < config.MIN_ZAJIMAVOST:
        skipped_boring += 1
        continue

    scored_postupy.append({
        'p1': p1,
        'p2': p2,
        'dist_m': dist_m,
        'routes': routes,
        'routes_metadata': routes_metadata,
        'score': score,
        'divergence': divergence,
        'balance': balance,
        'n_variants': len(routes)
    })

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
        os.remove(os.path.join(OUTPUT_DIR, f))
        old_count += 1
if old_count:
    print(f"   Smazano {old_count} starych souboru.")

for i, postup in enumerate(selected):
    p1, p2 = postup['p1'], postup['p2']

    # Snap na vektorové osy cest (čistě vizuální)
    routes_viz = []
    for rm in postup['routes_metadata']:
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
