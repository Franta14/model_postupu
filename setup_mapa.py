"""
setup_mapa.py - Automaticka priprava mapy (spustit 1x per nova mapa)

Co dela:
  1. Vypocita kalibraci PNG <-> OOM automaticky z .pgw + XML kontrol
  2. Vygeneruje cenovou mrizku terenu z .omap
  3. Vygeneruje vyskovou mrizku z vrstevnic v .omap
  4. Vse ulozi do cache/NazevMapy/ pro okamzite opetovne pouziti

Spusteni:  python setup_mapa.py
"""

import os, sys, math, time, json
import xml.etree.ElementTree as ET
import numpy as np
import requests
from shapely.geometry import Point, LineString, Polygon, MultiLineString
from shapely.ops import unary_union, nearest_points
from shapely.prepared import prep
from scipy.ndimage import binary_dilation, binary_erosion
from scipy.interpolate import griddata
from scipy.optimize import minimize, least_squares
from pyproj import Transformer

import config

# ============================================================
# POMOC: Nazev cache slozky = nazev .omap bez pripony
# ============================================================
map_name   = os.path.splitext(os.path.basename(config.OMAP_FILE))[0]
cache_dir  = os.path.join(config.CACHE_DIR, map_name)
os.makedirs(cache_dir, exist_ok=True)

cache_cenova  = os.path.join(cache_dir, "cenova_mapa.npy")
cache_meta    = os.path.join(cache_dir, "cenova_mapa_meta.npy")
cache_vyskova = os.path.join(cache_dir, "vyskova_mapa.npy")
cache_kalib   = os.path.join(cache_dir, "kalibrace.npy")

def vse_v_cache():
    soubory = [cache_cenova, cache_meta, cache_vyskova, cache_kalib]
    if not all(os.path.exists(s) for s in soubory):
        return False
    omap_mtime = os.path.getmtime(config.OMAP_FILE)
    return all(os.path.getmtime(s) > omap_mtime for s in soubory)

if vse_v_cache():
    print(f"✅ Cache pro mapu '{map_name}' je aktualni. Neni co delat.")
    print("   Rovnou spust:  python 6_finalni_stavitel.py")
    sys.exit(0)

print(f"🚀 Pripravuji mapu: {map_name}")
print(f"   Cache: {cache_dir}\n")


# ============================================================
# KROK 1: KALIBRACE  PNG pixel -> OOM souradnice
# ============================================================
print("📐 Krok 1/3: Vypocitavam kalibraci PNG <-> OOM...")

# 1a) Nacteni .pgw: pixel -> projekce (S-JTSK)
with open(config.PGW_FILE) as f:
    vals = [float(line.strip()) for line in f if line.strip()]
pgw_a, pgw_d, pgw_b, pgw_e, pgw_c, pgw_f = vals
# Transformace: world_x = pgw_a*col + pgw_b*row + pgw_c
#               world_y = pgw_d*col + pgw_e*row + pgw_f

# 1b) Nacteni XML kontrol: GPS -> OOM
transformer = Transformer.from_crs("EPSG:4326", "EPSG:5514", always_xy=True)
tree_xml = ET.parse(config.XML_FILE)
root_xml = tree_xml.getroot()

# Odstranim namespace prefix pro jednodussi hledani
for elem in root_xml.iter():
    if '}' in elem.tag:
        elem.tag = elem.tag.split('}', 1)[1]

controls_world = []  # S-JTSK souradnice
controls_oom   = []  # OOM mm souradnice

for ctrl in root_xml.findall('.//Control'):
    pos  = ctrl.find('Position')
    mpos = ctrl.find('MapPosition')
    if pos is None or mpos is None:
        continue
    lon = float(pos.attrib.get('lng', pos.attrib.get('lon', 0)))
    lat = float(pos.attrib['lat'])
    mx  = float(mpos.attrib['x'])
    my  = float(mpos.attrib['y'])
    w_x, w_y = transformer.transform(lon, lat)
    controls_world.append([w_x, w_y])
    controls_oom.append([mx, my])

if len(controls_world) < 3:
    print(f"❌ Potrebuji alespon 3 kontroly v XML, naslo se jen {len(controls_world)}.")
    sys.exit(1)

print(f"   Nalezeno {len(controls_world)} kontrol pro kalibraci.")

controls_world = np.array(controls_world)
controls_oom   = np.array(controls_oom)

# 1c) Proložení afinni transformace: world -> OOM  (metodou nejmensich ctvercu)
n = len(controls_world)
A = np.zeros((2*n, 6))
b_vec = np.zeros(2*n)
for i in range(n):
    wx, wy = controls_world[i]
    A[2*i,   :3] = [wx, wy, 1]
    A[2*i+1, 3:] = [wx, wy, 1]
    b_vec[2*i]   = controls_oom[i, 0]
    b_vec[2*i+1] = controls_oom[i, 1]

params, _, _, _ = np.linalg.lstsq(A, b_vec, rcond=None)
m11, m12, tx, m21, m22, ty = params

# Kontrola kvality kalibrace
fx = m11*controls_world[:,0] + m12*controls_world[:,1] + tx
fy = m21*controls_world[:,0] + m22*controls_world[:,1] + ty
rmse = float(np.sqrt(np.mean((fx - controls_oom[:,0])**2 + (fy - controls_oom[:,1])**2)))
print(f"   Kalibrace world->OOM: RMSE = {rmse:.2f} mm ({rmse/1000:.4f} m)")

# 1d) Slozeni transformace: pixel -> world -> OOM
# OOM_x = m11*(pgw_a*col + pgw_b*row + pgw_c) + m12*(pgw_d*col + pgw_e*row + pgw_f) + tx
cal_a = m11*pgw_a + m12*pgw_d  # koef. pro col -> OOM_x
cal_b = m11*pgw_b + m12*pgw_e  # koef. pro row -> OOM_x
cal_c = m11*pgw_c + m12*pgw_f + tx  # offset OOM_x
cal_d = m21*pgw_a + m22*pgw_d  # koef. pro col -> OOM_y
cal_e = m21*pgw_b + m22*pgw_e  # koef. pro row -> OOM_y
cal_f = m21*pgw_c + m22*pgw_f + ty  # offset OOM_y

kalibrace = np.array([cal_a, cal_b, cal_c, cal_d, cal_e, cal_f])
np.save(cache_kalib, kalibrace)
print(f"   ✅ Kalibrace ulozena.")


# ============================================================
# KROK 2: CENOVA MRIZKA (tereny z .omap)
# ============================================================
print("\n🗺️  Krok 2/3: Generuji cenovou mrizku terenu...")

GRID_SIZE_M       = 0.5
SIRKA_CESTY       = 0.5
SIRKA_ZDI         = 1.0

COST_DICT = {
    "Cesta (Zpevnena)":        0.915,
    "Cesta (Lesni)":           0.965,
    "Pesina":                  1.027,
    "Paseky":                  1.080,
    "Prusek":                  1.105,
    "Bily les":                1.172,
    "Bazina":                  1.317,
    "Voda":                    1.318,
    "Hustnik 1 (Svetly)":      1.360,
    "Podrost (Srafy)":         1.418,
    "Hustnik 2 (Stredni)":     1.502,
    "Hustnik 3 (Tmave)":       1.830,
    "Kamenne pole":            1.840,
    "Nepruchodna zed / plot":  9999.0,
    "Nepruchodna budova":      9999.0,
    "Nepruchodna voda":        9999.0,
}
DEFAULT_COST = COST_DICT["Bily les"]

tree = ET.parse(config.OMAP_FILE)
root = tree.getroot()
symbol_map = {
    elem.attrib.get('id'): elem.attrib.get('code')
    for elem in root.iter()
    if 'symbol' in elem.tag.lower()
}

kategorie = {k: [] for k in COST_DICT}
contour_lines_raw = []   # pro vyskovy model
text_objects_raw  = []   # popisky vrstevnic

for obj in root.iter():
    tag = obj.tag.lower()

    # --- Textove objekty (popisky vrstevnic) ---
    if 'text' in tag and 'object' not in tag:
        # Zkusi ziskat text a souradnice
        txt_val = obj.text or ""
        txt_val = txt_val.strip()
        if txt_val:
            try:
                elev_val = float(txt_val)
                # Koordinaty bereme z nadrazeneho <object> - resime nize
                text_objects_raw.append({'val': elev_val, 'obj': obj})
            except ValueError:
                pass

    if 'object' not in tag:
        continue

    isom_full = symbol_map.get(obj.attrib.get('symbol', ''), '')
    isom = isom_full.split('.')[0]
    pts  = []
    text_content = None

    for child in obj:
        child_tag = child.tag.lower()
        if 'coords' in child_tag and child.text:
            for p in child.text.strip().split(';'):
                parts = p.strip().split()
                if len(parts) >= 2:
                    try:
                        pts.append((float(parts[0])/1000, -float(parts[1])/1000))
                    except ValueError:
                        pass
            break

    for child in obj:
        if 't' == child.tag.lower() or 'text' in child.tag.lower():
            text_content = (child.text or '').strip()
            break

    if not pts:
        continue

    # --- Vrstevnice: 101=bežna, 102=indexova (103=pomocna IGNORUJEME pro interpolaci) ---
    if isom in ['101', '102'] and len(pts) >= 2:
        elev_known = None
        if text_content:
            try:
                elev_known = float(text_content)
            except ValueError:
                pass
        contour_lines_raw.append({
            'geom': LineString(pts),
            'is_index': (isom == '102'),
            'elevation': elev_known
        })

    # --- Carove objekty terenu ---
    if len(pts) >= 2:
        ter_lin = None
        if isom in ['501', '502', '503']:    ter_lin = "Cesta (Zpevnena)"
        elif isom == '504':                  ter_lin = "Cesta (Lesni)"
        elif isom in ['505', '506', '507']: ter_lin = "Pesina"
        elif isom in ['508', '509']:         ter_lin = "Prusek"
        elif isom in ['201', '516', '518']: ter_lin = "Nepruchodna zed / plot"
        if ter_lin:
            buf = SIRKA_ZDI if ter_lin == "Nepruchodna zed / plot" else SIRKA_CESTY
            kategorie[ter_lin].append(LineString(pts).buffer(buf))

    # --- Plošne objekty terenu ---
    if len(pts) >= 3:
        poly = Polygon(pts)
        if not poly.is_valid:
            poly = poly.buffer(0)
        ter_pol = None
        if isom in ['403', '404']:           ter_pol = "Paseky"
        elif isom == '406':                  ter_pol = "Hustnik 1 (Svetly)"
        elif isom == '408':                  ter_pol = "Hustnik 2 (Stredni)"
        elif isom == '410':                  ter_pol = "Hustnik 3 (Tmave)"
        elif isom in ['407', '409']:         ter_pol = "Podrost (Srafy)"
        elif isom in ['208','209','210','211','212']: ter_pol = "Kamenne pole"
        elif isom == '311':                  ter_pol = "Bazina"
        elif isom in ['301', '302']:         ter_pol = "Nepruchodna voda"
        elif isom.startswith('30'):          ter_pol = "Voda"
        elif isom in ['520','521','526','709']: ter_pol = "Nepruchodna budova"
        if ter_pol:
            kategorie[ter_pol].append(poly)

# Sloucime a pripravime geometrie
merged_geom   = {}
prepared_geom = {}
for k, v in kategorie.items():
    if v:
        u = unary_union(v)
        merged_geom[k]   = u
        prepared_geom[k] = prep(u)

# Zjistime rozsah mapy
all_geoms = [g for g in merged_geom.values() if not g.is_empty]
if not all_geoms:
    print("❌ Nenasly se zadne objekty v .omap souboru!")
    sys.exit(1)

vse = unary_union(all_geoms)
# Rozsir o vrstevnice
if contour_lines_raw:
    all_c = unary_union([c['geom'] for c in contour_lines_raw])
    vse = unary_union([vse, all_c.buffer(0.1)])

min_x, min_y, max_x, max_y = vse.bounds
grid_w = int(np.ceil((max_x - min_x) / GRID_SIZE_M))
grid_h = int(np.ceil((max_y - min_y) / GRID_SIZE_M))
print(f"   Mrizka: {grid_w} x {grid_h} bunek")

priority_order = [
    "Nepruchodna zed / plot", "Nepruchodna budova", "Nepruchodna voda",
    "Cesta (Zpevnena)", "Cesta (Lesni)", "Pesina", "Prusek",
    "Voda", "Kamenne pole", "Bazina",
    "Hustnik 3 (Tmave)", "Hustnik 2 (Stredni)", "Podrost (Srafy)",
    "Hustnik 1 (Svetly)", "Paseky"
]

cost_grid = np.full((grid_h, grid_w), DEFAULT_COST, dtype=np.float32)
t0 = time.time()
skip_krok2 = False
if os.path.exists(cache_cenova) and os.path.exists(cache_meta):
    print("   ✅ Cenova mrizka nalezena v cache, preskakuji pomaly vypocet...")
    cost_grid = np.load(cache_cenova)
    skip_krok2 = True

if not skip_krok2:
    for y_idx in range(grid_h):
        real_y = min_y + y_idx * GRID_SIZE_M
        if y_idx % 300 == 0:
            pct = y_idx / grid_h * 100
            elapsed = time.time() - t0
            eta = (elapsed / max(y_idx, 1)) * (grid_h - y_idx)
            print(f"   -> {pct:.0f}%  (zbývá ~{eta:.0f}s)")
        for x_idx in range(grid_w):
            real_x = min_x + x_idx * GRID_SIZE_M
            pt = Point(real_x, real_y)
            for teren in priority_order:
                if teren in prepared_geom and prepared_geom[teren].contains(pt):
                    cost_grid[y_idx, x_idx] = COST_DICT[teren]
                    break

    # Dilatace + eroze cest
    kernel = np.ones((3, 3), bool)
    maska = (cost_grid > 0.8) & (cost_grid < 1.1)
    maska = binary_dilation(maska, structure=kernel)
    maska = binary_erosion(maska, structure=kernel, iterations=1)
    maska = binary_erosion(maska, structure=np.array([[0,1,0],[1,1,1],[0,1,0]], bool), iterations=1)
    for y in range(grid_h):
        for x in range(grid_w):
            if maska[y, x] and cost_grid[y, x] < 9000.0:
                cost_grid[y, x] = COST_DICT["Cesta (Lesni)"]

    np.save(cache_cenova, cost_grid)
    metadata = np.array([min_x, min_y, max_x, max_y, GRID_SIZE_M])
    np.save(cache_meta, metadata)
    print(f"   ✅ Cenova mrizka ulozena ({time.time()-t0:.0f}s).")


# ============================================================
# KROK 3: VYSKOVA MRIZKA (z vrstevnic .omap)
# ============================================================
print("\n⛰️  Krok 3/3: Generuji vyskovou mrizku z vrstevnic...")

print("   Stahuji referencni vyskovou mrizku z API (opentopodata.org)...")
# Vytvoreni mrizky bodu (20x20) pres celou mapu (400 bodu celkem)
grid_pts_x = np.linspace(min_x, max_x, 20)
grid_pts_y = np.linspace(min_y, max_y, 20)
xx_api, yy_api = np.meshgrid(grid_pts_x, grid_pts_y)
api_oom_pts = np.c_[xx_api.ravel(), yy_api.ravel()]

# OOM je lokalni (v mm). Z Kroku 1 zname transformaci world(S-JTSK) -> OOM:
# OOM = M * world + T, kde M = [[m11, m12], [m21, m22]] a T = [tx, ty]
# Zpetne: world = M_inv * (OOM - T)
try:
    M = np.array([[m11, m12], [m21, m22]])
    M_inv = np.linalg.inv(M)
    T = np.array([tx, ty])
    
    world_pts = []
    for x, y in api_oom_pts:
        w_pt = M_inv.dot(np.array([x, y]) - T)
        world_pts.append(w_pt)
        
    # Prevod world (S-JTSK) zpet na GPS pro API
    t_inv = Transformer.from_crs("EPSG:5514", "EPSG:4326", always_xy=True)
    api_gps_pts = [t_inv.transform(w[0], w[1]) for w in world_pts]
except Exception as e:
    print(f"   ⚠️  Chyba pri transformaci souradnic OOM->GPS: {e}")
    api_gps_pts = []

# API umoznuje max 100 bodu na request, takze rozdelime do davek (chunks)
api_elevations = []
chunk_size = 100
for i in range(0, len(api_gps_pts), chunk_size):
    chunk = api_gps_pts[i:i+chunk_size]
    loc_str = "|".join([f"{lat:.6f},{lon:.6f}" for lon, lat in chunk])
    try:
        url = f"https://api.opentopodata.org/v1/eudem25m?locations={loc_str}"
        r = requests.get(url, timeout=15)
        data = r.json()
        if data.get('status') == 'OK':
            for res in data['results']:
                val = res.get('elevation')
                api_elevations.append(val if val is not None else 0.0)
            print(f"      Stazeno {min(i+chunk_size, 400)}/400 bodu...")
        else:
            print(f"   ⚠️  API selhalo u davky {i}: {data.get('status')}")
            api_elevations.extend([0.0]*len(chunk))
    except Exception as e:
        print(f"   ⚠️  API nedostupne ({e}).")
        api_elevations.extend([0.0]*len(chunk))
    time.sleep(1.2) # Ochrana proti rate-limitingu (max 1 pozadavek za vterinu)
        
api_elevations = np.array(api_elevations)

print("   Generuji hladký výškový model přímo ze satelitních dat (ignoruji nekonzistentní OCAD vrstevnice)...")
if len(api_elevations) >= 4:
    x_coords = min_x + np.arange(grid_w) * GRID_SIZE_M
    y_coords = min_y + np.arange(grid_h) * GRID_SIZE_M
    xx, yy = np.meshgrid(x_coords, y_coords)
    grid_pts = np.c_[xx.ravel(), yy.ravel()]
    
    # Cubic interpolace vytvori plynule hladke kopce a udoli bez ostrych hran
    try:
        vyskova = griddata(api_oom_pts, api_elevations, grid_pts, method='cubic')
    except Exception:
        vyskova = griddata(api_oom_pts, api_elevations, grid_pts, method='linear')
        
    nan_mask = np.isnan(vyskova)
    if nan_mask.any():
        vyskova_nn = griddata(api_oom_pts, api_elevations, grid_pts, method='nearest')
        vyskova[nan_mask] = vyskova_nn[nan_mask]
    vyskova = vyskova.reshape((grid_h, grid_w)).astype(np.float32)
else:
    print("   ⚠️  Malo bodu z API, pouzivam nulovou vysku.")
    vyskova = np.zeros((grid_h, grid_w), dtype=np.float32)

np.save(cache_vyskova, vyskova)
print(f"   ✅ Vyskova mrizka ulozena.")

# ============================================================
# HOTOVO
# ============================================================
print(f"""
╔══════════════════════════════════════════════════════╗
║  ✅ MAPA '{map_name}' PRIPRAVENA!
║
║  Nyni spust:  python 6_finalni_stavitel.py
╚══════════════════════════════════════════════════════╝
""")
