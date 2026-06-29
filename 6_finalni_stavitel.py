import numpy as np
import matplotlib.pyplot as plt
import math
import os
import sys
import time
from PIL import Image
from matplotlib.widgets import Slider, Button
from scipy.ndimage import binary_dilation
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra as sp_dijkstra
import config

# =====================================================================
# --- NASTAVENI (vse nacteno z config.py) ---
# =====================================================================
map_image_file = config.PNG_FILE
POCET_VARIANT = config.POCET_VARIANT
ZAPNOUT_VYHLAZENI = config.ZAPNOUT_VYHLAZENI
VYHLAZENI_BUNEK = config.VYHLAZENI_BUNEK
ZAKLADNI_TEMPO_MIN = config.ZAKLADNI_TEMPO_MIN
ZAKLADNI_TEMPO_SEC = config.ZAKLADNI_TEMPO_SEC
NASOBIC_MERITKA = config.NASOBIC_MERITKA
CENA_LESNI_CESTY = config.CENA_LESNI_CESTY
PODOBNOST_RADIUS = config.PODOBNOST_RADIUS

map_name = os.path.splitext(os.path.basename(config.OMAP_FILE))[0]
cache_dir = os.path.join(config.CACHE_DIR, map_name)

print(f"🚀 Startuji AI stavitel (Dijkstra Heatmap) | Mapa: {map_name}")

zakladni_tempo_desetinne = ZAKLADNI_TEMPO_MIN + (ZAKLADNI_TEMPO_SEC / 60.0)

# =====================================================================
# 1. NACTENI DAT Z CACHE
# =====================================================================
try:
    cost_grid_base = np.load(os.path.join(cache_dir, "cenova_mapa.npy"))
    elev_grid = np.load(os.path.join(cache_dir, "vyskova_mapa.npy"))
    meta = np.load(os.path.join(cache_dir, "cenova_mapa_meta.npy"))
    min_x, min_y, max_x, max_y, grid_size = meta
    height, width = cost_grid_base.shape
except FileNotFoundError:
    print(f"❌ Cache pro mapu '{map_name}' nenalezena.")
    print("   Nejprve spust:  python setup_mapa.py")
    sys.exit(1)

# =====================================================================
# 2. KALIBRACE (automaticky z cache - zadne klikani)
# =====================================================================
try:
    cal = np.load(os.path.join(cache_dir, "kalibrace.npy"))
    cal_a, cal_b, cal_c, cal_d, cal_e, cal_f = cal
except FileNotFoundError:
    print(f"❌ Kalibrace pro mapu '{map_name}' nenalezena.")
    print("   Nejprve spust:  python setup_mapa.py")
    sys.exit(1)


def img_to_grid(col, row):
    """PNG pixel (col, row) -> (grid_row, grid_col)"""
    oom_x = cal_a * col + cal_b * row + cal_c
    oom_y = cal_d * col + cal_e * row + cal_f
    gx = (oom_x - min_x) / grid_size
    gy = (oom_y - min_y) / grid_size
    return max(0, min(height - 1, int(gy))), max(0, min(width - 1, int(gx)))


def grid_to_img(grid_row, grid_col):
    """(grid_row, grid_col) -> PNG pixel (col, row) - inverzni transformace"""
    oom_x = min_x + grid_col * grid_size
    oom_y = min_y + grid_row * grid_size
    # Inverze afinni transformace 2x2
    det = cal_a * cal_e - cal_b * cal_d
    if abs(det) < 1e-12:
        return 0, 0
    col = (cal_e * (oom_x - cal_c) - cal_b * (oom_y - cal_f)) / det
    row = (cal_a * (oom_y - cal_f) - cal_d * (oom_x - cal_c)) / det
    return col, row


# =====================================================================
# 3. JADRO: DIJKSTRA HEATMAP (Protnutí izochron)
# =====================================================================

# 16-smerovy pohyb presunut primo do vektorizovane funkce


def vytvor_masku_elipsy(start, goal, h, w, rozsireni=0.45):
    """
    Vektorizovana tvorba binarni masky povolene oblasti (elipsa).

    start, goal: (row, col) pixely v gridu
    h, w: rozmery gridu
    rozsireni: kolma poloosa jako podil vzdalenosti Start-Cil
    """
    sy, sx = start
    gy, gx = goal

    # Stred a osa elipsy
    stred_y = (sy + gy) / 2.0
    stred_x = (sx + gx) / 2.0
    osa_dy = gy - sy
    osa_dx = gx - sx
    osa_delka = math.hypot(osa_dy, osa_dx)
    if osa_delka < 1.0:
        osa_delka = 1.0

    # Normalizovany smer a kolmice
    osa_ny = osa_dy / osa_delka
    osa_nx = osa_dx / osa_delka
    perp_ny = -osa_nx
    perp_nx = osa_ny

    # Dynamicke rozsireni pro dlouhe postupy
    # Zaklad 0.45, ale pro postupy nad 2000 bunek logaritmicky roste
    PRAH_BUNEK = 2000
    if osa_delka > PRAH_BUNEK:
        rozsireni = rozsireni + 0.12 * math.log2(osa_delka / PRAH_BUNEK)
        rozsireni = min(rozsireni, 0.85)  # Bezpecnostni strop

    # Poloosy: podelna o trochu delsi nez pulka vzdalenosti, kolma = rozsireni
    poloosa_podelna = osa_delka * 0.55
    poloosa_kolma = osa_delka * rozsireni

    # Minimalni poloosy – zvyseno pro lepsi pokryti krátkych postupu
    poloosa_podelna = max(poloosa_podelna, 300)
    poloosa_kolma = max(poloosa_kolma, 250)

    # Vektorizovany test elipsy pres meshgrid
    rows = np.arange(h, dtype=np.float32)
    cols = np.arange(w, dtype=np.float32)
    yy, xx = np.meshgrid(rows, cols, indexing='ij')

    rel_y = yy - stred_y
    rel_x = xx - stred_x

    # Projekce do souradnic elipsy
    proj_podelna = rel_y * osa_ny + rel_x * osa_nx
    proj_kolma = rel_y * perp_ny + rel_x * perp_nx

    # Test elipsy: (p/a)^2 + (q/b)^2 <= 1
    elipsa_test = (proj_podelna / poloosa_podelna) ** 2 + \
                  (proj_kolma / poloosa_kolma) ** 2
    maska = elipsa_test <= 1.0

    return maska


def dijkstra_heatmap(grid, elev, source, mask, gs, kopce_vaha=25.0, direction='forward'):
    """
    Vektorizovana Dijkstra expanze pres celou povolenou oblast.
    Vyuziva scipy.sparse.csgraph.dijkstra pro maximalni vykon (C/Cython).
    """
    h, w = grid.shape
    N = h * w
    sy, sx = source
    source_idx = int(sy * w + sx)

    DIRECTIONS = [
        (0, 1, gs, False), (1, 0, gs, False), (0, -1, gs, False), (-1, 0, gs, False),
        (1, 1, gs * 1.4142, False), (-1, 1, gs * 1.4142, False), 
        (1, -1, gs * 1.4142, False), (-1, -1, gs * 1.4142, False),
        (1, 2, gs * 2.2361, True), (2, 1, gs * 2.2361, True),
        (-1, 2, gs * 2.2361, True), (-2, 1, gs * 2.2361, True),
        (1, -2, gs * 2.2361, True), (2, -1, gs * 2.2361, True),
        (-1, -2, gs * 2.2361, True), (-2, -1, gs * 2.2361, True)
    ]

    is_road = grid < 1.05
    row_indices = []
    col_indices = []
    data_weights = []

    y_coords, x_coords = np.nonzero(mask)

    for dy, dx, step_dist, is_knight in DIRECTIONS:
        valid = (y_coords + dy >= 0) & (y_coords + dy < h) & (x_coords + dx >= 0) & (x_coords + dx < w)
        
        cy = y_coords[valid]
        cx = x_coords[valid]
        ny = cy + dy
        nx = cx + dx
        
        valid_dest = mask[ny, nx]
        cy = cy[valid_dest]
        cx = cx[valid_dest]
        ny = ny[valid_dest]
        nx = nx[valid_dest]
        
        if len(cy) == 0:
            continue

        if is_knight:
            mid_y = cy + (dy // 2)
            mid_x = cx + (dx // 2)
            
            wall_check = grid[mid_y, mid_x] < 9000.0
            cy = cy[wall_check]
            cx = cx[wall_check]
            ny = ny[wall_check]
            nx = nx[wall_check]
            mid_y = mid_y[wall_check]
            mid_x = mid_x[wall_check]
            
            terren_cost = grid[cy, cx] * 0.2 + grid[mid_y, mid_x] * 0.3 + grid[ny, nx] * 0.5
        else:
            terren_cost = grid[cy, cx] * 0.35 + grid[ny, nx] * 0.65
            
        valid_terren = terren_cost < 9000.0
        cy = cy[valid_terren]
        cx = cx[valid_terren]
        ny = ny[valid_terren]
        nx = nx[valid_terren]
        terren_cost = terren_cost[valid_terren]
        
        if len(cy) == 0:
            continue

        # --- DIAGNOSTIKA & OPRAVA CHYBEJICI STICKINESS ---
        # 1) Definice "rychle cesty" rozsirena na < 1.09, coz zachyti i mensi pesiny (napr. cost 1.08)
        # 2) Pro knight tahy musime garantovat, ze i stredovy (mid) pixel lezi na ceste.
        # Pokud neni, runner_next_road bude False, ztrati slevu a dostane penalizaci za opusteni cesty!
        is_rc = grid[cy, cx] < 1.09
        is_rn = grid[ny, nx] < 1.09
        is_rm = grid[mid_y, mid_x] < 1.09 if is_knight else is_rn

        if direction == 'forward':
            dz = elev[ny, nx] - elev[cy, cx]
            is_runner_on_road = is_rc
            is_runner_next_road = is_rn & is_rm
        else:
            dz = elev[cy, cx] - elev[ny, nx]
            is_runner_on_road = is_rn
            is_runner_next_road = is_rc & is_rm

        # Oprava kopcu: krok musi byt prepocitan na metry (zohledneni grid_size)!
        dist_m = step_dist * grid_size
        sklon = dz / dist_m
        hill_multiplier = np.ones_like(sklon)
        
        up_mask = sklon > 0.02
        sklon_ef = sklon[up_mask] - 0.02
        lin_penalta = kopce_vaha * 0.02 * sklon_ef
        exp_penalta = np.where(sklon_ef > 0.15, kopce_vaha * 0.2 * ((sklon_ef - 0.15) ** 1.5), 0.0)
        hill_multiplier[up_mask] = 1.0 + lin_penalta + exp_penalta
        
        down_mask = sklon < -0.02
        sklon_down = sklon[down_mask]
        limit_zrychleni = -0.25
        
        mild_down = sklon_down >= limit_zrychleni
        steep_down = ~mild_down
        
        hm_down = np.empty_like(sklon_down)
        hm_down[mild_down] = 1.0 + (sklon_down[mild_down] * 0.5)
        
        maximalni_zrychleni = 1.0 + (limit_zrychleni * 0.5)
        prebytek_sklonu = np.abs(sklon_down[steep_down]) - abs(limit_zrychleni)
        hm_down[steep_down] = maximalni_zrychleni + (prebytek_sklonu * 1.5)
        hill_multiplier[down_mask] = hm_down

        step_effort = step_dist * terren_cost * hill_multiplier
        
        both_road = is_runner_on_road & is_runner_next_road
        step_effort[both_road] *= 0.92
        
        exit_road = is_runner_on_road & (~is_runner_next_road)
        step_effort[exit_road] += step_dist * 0.40

        row_indices.append(cy * w + cx)
        col_indices.append(ny * w + nx)
        data_weights.append(step_effort)

    if not row_indices:
        return np.full((h, w), np.inf, dtype=np.float64), np.full((h, w), -1, dtype=np.int32), np.full((h, w), -1, dtype=np.int32)

    row_arr = np.concatenate(row_indices)
    col_arr = np.concatenate(col_indices)
    data_arr = np.concatenate(data_weights)

    graph = coo_matrix((data_arr, (row_arr, col_arr)), shape=(N, N))

    dist_1d, pred_1d = sp_dijkstra(graph, directed=True, indices=source_idx, return_predecessors=True)

    dist = dist_1d.reshape((h, w))
    
    parents_y = np.full((h, w), -1, dtype=np.int32)
    parents_x = np.full((h, w), -1, dtype=np.int32)
    
    valid_pred = pred_1d >= 0
    pred_y = pred_1d[valid_pred] // w
    pred_x = pred_1d[valid_pred] % w
    
    valid_indices = np.nonzero(valid_pred)[0]
    valid_curr_y = valid_indices // w
    valid_curr_x = valid_indices % w
    
    parents_y[valid_curr_y, valid_curr_x] = pred_y
    parents_x[valid_curr_y, valid_curr_x] = pred_x

    return dist, parents_y, parents_x


def trasuj_cestu(parents_y, parents_x, start, goal):
    """
    Trasovani optimalni cesty zpatky od cile ke startu pomoci matice predku.
    """
    path = []
    cy, cx = goal
    sy, sx = start

    while (int(cy), int(cx)) != (int(sy), int(sx)):
        path.append((cy, cx))
        py, px = parents_y[int(cy), int(cx)], parents_x[int(cy), int(cx)]
        if py == -1 or px == -1: return None
        cy, cx = py, px

    path.append((sy, sx))
    path.reverse() # Chceme Start -> Cil
    return path


def penalizuj_grid(grid, trasa, sirka_px):
    """
    Vytvori kopii cenove mrizky a zdrazi teren podel zadane trasy.
    Kolem pixelu trasy vytvori binarni masku (dilatace o sirka_px bunek)
    a prida penalizaci = vynasobi naklady na pruchod * 1.5.
    """
    h, w = grid.shape
    grid_pen = grid.copy()

    # Vytvor binarni masku trasy
    trasa_maska = np.zeros((h, w), dtype=bool)
    for py, px in trasa:
        y_int = max(0, min(h - 1, int(py)))
        x_int = max(0, min(w - 1, int(px)))
        trasa_maska[y_int, x_int] = True

    # Dilatace – rozsir masku kolem trasy
    struct = np.ones((3, 3), dtype=bool)
    iteraci = max(1, sirka_px // 2)
    zona = binary_dilation(trasa_maska, structure=struct, iterations=iteraci)

    # Zvyseni ceny terenu o 50%
    grid_pen[zona] *= 1.5

    return grid_pen


def merit_podobnost(cesta_nova, prijate_cesty, h, w, radius):
    """Zmeri prostorovou shodu nove trasy vuci jiz prijatym trasam."""
    if not prijate_cesty:
        return 0.0
    maska = np.zeros((h, w), dtype=bool)
    r = radius
    for co in prijate_cesty:
        for py, px in co[::4]:
            y, x = int(py), int(px)
            maska[
                max(0, y - r): min(h, y + r + 1),
                max(0, x - r): min(w, x + r + 1),
            ] = True
    nova_arr = np.array(cesta_nova, dtype=int)
    py = np.clip(nova_arr[:, 0], 0, h - 1)
    px = np.clip(nova_arr[:, 1], 0, w - 1)
    sdil = np.sum(maska[py, px])
    return sdil / max(1, len(cesta_nova))


def _penalizuj_heatmapu(penalty_grid, trasa, radius, hodnota):
    """Prida plynulou penalizaci (gradient) do penalty_grid v okoli zadane trasy."""
    h, w = penalty_grid.shape
    
    # 1) Vytvoreni kruhoveho gradientoveho jadra (kernel)
    y, x = np.ogrid[-radius:radius+1, -radius:radius+1]
    dist = np.sqrt(x**2 + y**2)
    # Linearni upadek, ale s rovnou plosinou (plateau) uprostred,
    # aby se nevyplatilo "uskakovat" jen kousek vedle cesty
    plateau_r = radius * 0.4
    kernel_base = np.where(
        dist <= plateau_r,
        1.0,
        np.maximum(0, 1.0 - (dist - plateau_r) / (radius - plateau_r))
    )
    
    body_k_penalizaci = trasa[::3]
    total_pts = len(body_k_penalizaci)
    # 15 % trasy (z obou stran) bude ochranna zona (fade-out), min 5 bodu
    ochrana_bodu = max(5, int(total_pts * 0.15)) 
    
    for i, (ty, tx) in enumerate(body_k_penalizaci):
        y_int, x_int = int(ty), int(tx)
        
        # 2) Fade-out zony kolem startu a cile
        if i < ochrana_bodu:
            fade_factor = i / ochrana_bodu
        elif i > total_pts - 1 - ochrana_bodu:
            fade_factor = max(0, (total_pts - 1 - i)) / ochrana_bodu
        else:
            fade_factor = 1.0
            
        # Plynule jadro pro dany bod
        kernel = kernel_base * (hodnota * fade_factor)
        
        y_min = max(0, y_int - radius)
        y_max = min(h, y_int + radius + 1)
        x_min = max(0, x_int - radius)
        x_max = min(w, x_int + radius + 1)
        
        ky_min = radius - (y_int - y_min)
        ky_max = radius + (y_max - y_int)
        kx_min = radius - (x_int - x_min)
        kx_max = radius + (x_max - x_int)
        
        if y_max > y_min and x_max > x_min:
            # POUZIJEME MAXIMUM MISTO SCITANI - ZABRANI TO VYTVORENI NEPROSTUPNE ZDI
            # Umozni to krizit se s trasou uprostred postupu
            vyrez_penalty = penalty_grid[y_min:y_max, x_min:x_max]
            vyrez_kernel = kernel[ky_min:ky_max, kx_min:kx_max]
            penalty_grid[y_min:y_max, x_min:x_max] = np.maximum(vyrez_penalty, vyrez_kernel)


def vyhlad_cestu(cesta_pixely, grid, vyhlazeni=3):
    """
    Kontextualni vyhlazeni trasy.

    Na cestach (cost < 1.05): plne vyhlazeni pro plynule krivky.
    V terenu (cost >= 1.05): minimalni nebo zadne vyhlazeni,
    trasa presne kopiruje Dijkstrovu stopu.
    """
    if len(cesta_pixely) < 3 or vyhlazeni <= 0:
        return cesta_pixely

    pts = list(cesta_pixely)
    start_orig = pts[0]
    cil_orig = pts[-1]
    h, w = grid.shape

    nova = []
    for i in range(len(pts)):
        py, px = pts[i]
        y_int = max(0, min(h - 1, int(py)))
        x_int = max(0, min(w - 1, int(px)))
        cost = grid[y_int, x_int]

        # 1) Zjistime jestli ma smysl vubec vyhlazovat
        if cost < 1.09:
            okno = vyhlazeni    # cesty a pesiny
        elif cost < 1.5:
            okno = 1            # lehky teren
        else:
            okno = 0            # tezky teren/les - nechat presne podle Dijkstry

        if okno == 0:
            nova.append((py, px))
        else:
            # Vypocet klouzaveho prumeru (vyhlazeneho bodu)
            a = max(0, i - okno)
            b = min(len(pts), i + okno + 1)
            avg_y = sum(p[0] for p in pts[a:b]) / (b - a)
            avg_x = sum(p[1] for p in pts[a:b]) / (b - a)
            
            # --- DIAGNOSTIKA & OPRAVA CHYBY "ZKRACENI ROHU DO LESA" ---
            # Zkontrolujeme cenu puvodniho bodu a cenu "vyhlazeneho" bodu
            sm_y_int = max(0, min(h - 1, int(avg_y)))
            sm_x_int = max(0, min(w - 1, int(avg_x)))
            sm_cost = grid[sm_y_int, sm_x_int]
            
            # Pokud vyhlazeny bod padne do lesa/pomalejsiho terenu.
            # Zprisnena kontrola: Bily les (1.0) a cesta (0.965) maji rozdil jen 3.6%. 
            # Pokud puvodni bod byl na ceste (< 1.05), vyhlazeny MUSI byt take na ceste.
            # Nebo obecne nesmi byt pomalejsi o vice nez 2% (misto puvodnich 10%).
            byl_na_ceste = cost < 1.05
            je_na_ceste = sm_cost < 1.05
            
            if (byl_na_ceste and not je_na_ceste) or (sm_cost > cost * 1.02):
                nova.append((py, px))
            else:
                nova.append((avg_y, avg_x))

    nova[0] = start_orig
    nova[-1] = cil_orig
    return nova


# =====================================================================
# 4. INTERAKTIVNI VYKRESLENI A ANALYZA TRATE
# =====================================================================
print("🖼️ Nacitam mapu...")


class AplikaceStavitel:
    def __init__(self):
        self.img = Image.open(map_image_file)
        self.img.load()  # Nacte cely obrazek do RAM, aby byl crop okamzity
        self.orig_w, self.orig_h = self.img.size
        
        self.fig, self.ax = plt.subplots(figsize=(14, 10))
        self.fig.canvas.manager.set_window_title(
            "AI Elitni stavitel - Dijkstra Heatmap"
        )
        plt.subplots_adjust(bottom=0.14)

        print("⚙️ Vykresluji mapu na monitor (dynamické rozlišení)...")
        # Vykreslime jen pocatecni downsample
        crop_arr = self._get_crop(0, self.orig_w, 0, self.orig_h)
        self.im = self.ax.imshow(crop_arr, interpolation="nearest", extent=[0, self.orig_w, self.orig_h, 0])

        # Pripojeni na udalosti hybani a zoomovani
        self.ax.callbacks.connect('xlim_changed', self._on_zoom)
        self.ax.callbacks.connect('ylim_changed', self._on_zoom)

        # --- UI WIDGETY (Sliders) ---
        axcolor = 'lightgoldenrodyellow'
        self.ax_kopce = plt.axes([0.15, 0.05, 0.55, 0.025], facecolor=axcolor)
        self.slider_kopce = Slider(self.ax_kopce, 'Penalizace Kopců', 1.0, 30.0, valinit=5.0)

        self.ax_btn = plt.axes([0.78, 0.04, 0.12, 0.05])
        self.btn_prepocitat = Button(self.ax_btn, 'Přepočítat [R]', color=axcolor, hovercolor='0.975')
        self.btn_prepocitat.on_clicked(self.prepocti_akce)

        self.body = []
        self.vykreslene_body = []
        self.vykreslene_trasy = []
        self.hotovo = False

        # Stavove promenne pro vlastni trasu
        self.rezim_vlastni_trasy = False

    def _get_crop(self, x0, x1, y0, y1):
        x0, x1 = max(0, int(x0)), min(self.orig_w, int(x1))
        y0, y1 = max(0, int(y0)), min(self.orig_h, int(y1))
        if x1 <= x0 or y1 <= y0:
            return np.zeros((1, 1, 3), dtype=np.uint8)
        crop = self.img.crop((x0, y0, x1, y1))
        cw, ch = crop.size
        ratio = min(2000.0 / cw, 2000.0 / ch)
        if ratio < 1.0:
            crop = crop.resize((int(cw * ratio), int(ch * ratio)), Image.Resampling.BILINEAR)
        return np.array(crop)

    def _on_zoom(self, event_ax):
        if getattr(self, '_updating_zoom', False):
            return
        
        self._updating_zoom = True
        try:
            xlim = event_ax.get_xlim()
            ylim = event_ax.get_ylim()
            
            # Omezit souradnice na realnou velikost mapy
            x0 = max(0, min(xlim))
            x1 = min(self.orig_w, max(xlim))
            y0 = max(0, min(ylim))
            y1 = min(self.orig_h, max(ylim))
            
            if x1 > x0 and y1 > y0:
                self.im.set_data(self._get_crop(x0, x1, y0, y1))
                self.im.set_extent([x0, x1, y1, y0])
        finally:
            self._updating_zoom = False
        self.vlastni_body = []
        self.vykreslene_vlastni_body = []

        self.navod_zadavani = "\n[LEVÉ tl. = Zadat bod] | [PRAVÉ tl. = Zpět]"
        self.navod_hotovo = "\n[MEZERNÍK = Nový postup] | [V = Vlastní trasa] | [R = Přepočítat]"

        self.ax.set_title(
            "Zadej Start a Cíl (2 body)" + self.navod_zadavani, fontweight="bold"
        )

        self.fig.canvas.mpl_connect("button_press_event", self.onclick)
        self.fig.canvas.mpl_connect("key_press_event", self.onkey)

    def prepocti_akce(self, event=None):
        if len(self.body) == 2:
            print("\n🔄 Přepočítávám s novými parametry ze sliderů...")
            # Smazeme jen stare vygenerovane trasy, vstupni body nechame
            for p in self.vykreslene_trasy:
                p.remove()
            self.vykreslene_trasy.clear()

            # Smazeme starou legendu
            leg = self.ax.get_legend()
            if leg:
                leg.remove()

            self.spocitat_trasy()
            self.fig.canvas.draw_idle()

    def prekreslit_body(self):
        for p in self.vykreslene_body:
            p.remove()
        self.vykreslene_body.clear()

        if len(self.body) > 1:
            cara_x = [p[0] for p in self.body]
            cara_y = [p[1] for p in self.body]
            (c,) = self.ax.plot(cara_x, cara_y, "m--", linewidth=2, alpha=0.5)
            self.vykreslene_body.append(c)

        for i, (x, y) in enumerate(self.body):
            (m,) = self.ax.plot(x, y, "mo", markersize=8, zorder=5)
            t = self.ax.text(
                x + 10,
                y + 10,
                "Start" if i == 0 else "Cíl",
                color="magenta",
                fontweight="bold",
                zorder=6,
                bbox=dict(facecolor="white", alpha=0.6, edgecolor="none", pad=1),
            )
            self.vykreslene_body.extend([m, t])
        self.fig.canvas.draw_idle()

    def prekreslit_vlastni_body(self):
        for p in self.vykreslene_vlastni_body:
            p.remove()
        self.vykreslene_vlastni_body.clear()

        for i, (x, y) in enumerate(self.vlastni_body):
            (m,) = self.ax.plot(x, y, "o", color="orange", markersize=6, zorder=5)
            t = self.ax.text(x + 10, y + 10, str(i + 1), color="orange", fontweight="bold", zorder=6)
            self.vykreslene_vlastni_body.extend([m, t])

        self.fig.canvas.draw_idle()

    def smazat_vse(self):
        self.body.clear()
        self.hotovo = False
        self.rezim_vlastni_trasy = False
        self.vlastni_body.clear()

        for p in self.vykreslene_trasy:
            p.remove()
        self.vykreslene_trasy.clear()

        for p in self.vykreslene_vlastni_body:
            p.remove()
        self.vykreslene_vlastni_body.clear()

        leg = self.ax.get_legend()
        if leg:
            leg.remove()
        self.prekreslit_body()
        self.ax.set_title(
            "Zadej Start a Cíl (2 body)" + self.navod_zadavani, fontweight="bold"
        )
        self.fig.canvas.draw_idle()

    def onclick(self, event):
        if event.inaxes != self.ax:
            return
        if self.fig.canvas.toolbar.mode != "":
            return

        # Obsluha klikani pro rezim vlastni trasy
        if self.rezim_vlastni_trasy:
            if event.button == 1:  # Leve tlacitko (Pridat bod)
                self.vlastni_body.append((event.xdata, event.ydata))
                self.prekreslit_vlastni_body()
            elif event.button == 3:  # Prave tlacitko (Zpet bod)
                if self.vlastni_body:
                    self.vlastni_body.pop()
                    self.prekreslit_vlastni_body()
            return

        # Ochrana vypocitanych AI tras pred smazanim
        if self.hotovo:
            return

        # Vychozi zadavani Start / Cil
        if event.button == 1:
            if len(self.body) < 2:
                self.body.append((event.xdata, event.ydata))
                self.prekreslit_body()

                if len(self.body) == 2:
                    self.spocitat_trasy()
        elif event.button == 3:
            if self.body:
                self.body.pop()
                self.prekreslit_body()

    def onkey(self, event):
        key = event.key.lower() if event.key else ""

        # Obsluha klaves pro rezim vlastni trasy
        if self.rezim_vlastni_trasy:
            if key == "enter":
                self.spocitat_vlastni_trasu()
                self.rezim_vlastni_trasy = False
            elif key == "escape":
                self.rezim_vlastni_trasy = False
                self.vlastni_body.clear()
                self.prekreslit_vlastni_body()
                self.ax.set_title("HOTOVO!" + self.navod_hotovo, color="green", fontweight="bold")
                self.fig.canvas.draw_idle()
            return

        if self.hotovo:
            if key == "v":
                # Prepnuti do rezimu zadavani vlastni trasy
                self.rezim_vlastni_trasy = True
                self.vlastni_body.clear()
                self.prekreslit_vlastni_body()
                self.ax.set_title("REŽIM VLASTNÍ TRASY: Naklikej body a potvrď [ENTER] (Zrušit: ESC)", color="orange", fontweight="bold")
                self.fig.canvas.draw_idle()
            elif key in ["escape", "backspace", " ", "delete"]:
                self.smazat_vse()
            elif key == "r":
                self.prepocti_akce()

    def spocitat_metriky(self, cesta, working_grid_base):
        """Vypocet vzdalenosti, prevyseni, usili a podilu cest pro trasu."""
        vzd = prev = usili = road_dist = 0.0
        val_kopce = self.slider_kopce.val
        
        for j in range(1, len(cesta)):
            p1, p2 = cesta[j - 1], cesta[j]
            dg = math.hypot(p2[1] - p1[1], p2[0] - p1[0]) * grid_size
            vzd += dg * NASOBIC_MERITKA
            if working_grid_base[int(p2[0]), int(p2[1])] < 1.05:
                road_dist += dg * NASOBIC_MERITKA
            z1 = elev_grid[int(p1[0]), int(p1[1])]
            z2 = elev_grid[int(p2[0]), int(p2[1])]
            if z2 > z1:
                prev += z2 - z1
                
            sk = (z2 - z1) / (dg * NASOBIC_MERITKA) if dg > 0.1 else 0
            
            if sk > 0.02:
                sklon_efektivni = sk - 0.02
                lin_penalta = val_kopce * 0.02 * sklon_efektivni
                if sklon_efektivni > 0.15:
                    exp_penalta = val_kopce * 0.2 * ((sklon_efektivni - 0.15) ** 1.5)
                else:
                    exp_penalta = 0.0
                hm = 1.0 + lin_penalta + exp_penalta
            elif sk < -0.02:
                limit_zrychleni = -0.25
                if sk >= limit_zrychleni:
                    hm = 1.0 + (sk * 0.5)
                else:
                    maximalni_zrychleni = 1.0 + (limit_zrychleni * 0.5)
                    prebytek_sklonu = abs(sk) - abs(limit_zrychleni)
                    hm = maximalni_zrychleni + (prebytek_sklonu * 1.5)
            else:
                hm = 1.0
                
            usili += dg * working_grid_base[int(p2[0]), int(p2[1])] * hm
        road_ratio = road_dist / vzd if vzd > 0 else 0.0
        return vzd, prev, usili, road_ratio

    def vykresli_trasu(self, cesta, barva, label, bod_A, bod_B, smooth=True):
        """Vyhladí a vykreslí jednu trasu na mapu."""
        if smooth and ZAPNOUT_VYHLAZENI:
            cesta_viz = vyhlad_cestu(cesta, cost_grid_base, vyhlazeni=VYHLAZENI_BUNEK)
        else:
            cesta_viz = cesta

        wx, wy = [], []
        for py, px in cesta_viz:
            u, v = grid_to_img(py, px)
            wx.append(u)
            wy.append(v)
        if len(wx) > 1:
            wx[0], wy[0] = bod_A[0], bod_A[1]
            wx[-1], wy[-1] = bod_B[0], bod_B[1]

        (l1,) = self.ax.plot(wx, wy, color=barva, linewidth=4, alpha=0.9, label=label)
        (l2,) = self.ax.plot(wx, wy, color="white", linewidth=1, alpha=0.8)
        self.vykreslene_trasy.extend([l1, l2])

    # =================================================================
    # HLAVNI VYPOCET: Dijkstra Heatmap (Protnuti izochron)
    # =================================================================
    def spocitat_trasy(self):
        self.hotovo = True
        self.ax.set_title("POCITAM TRASY (Dijkstra Heatmap)...", color="red", fontweight="bold")
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

        t_celkovy_start = time.time()
        working_grid = cost_grid_base  # Bez kopie – Dijkstra grid NEMENI
        colors = ["#DD0000", "#00AA00", "#0055DD"]

        bod_A, bod_B = self.body[0], self.body[1]
        s_y, s_x = img_to_grid(bod_A[0], bod_A[1])
        g_y, g_x = img_to_grid(bod_B[0], bod_B[1])
        start = (s_y, s_x)
        goal = (g_y, g_x)

        val_kopce = self.slider_kopce.val

        print(f"\n{'='*60}")
        print(f"Resim postup: Start [{s_y},{s_x}] -> Cil [{g_y},{g_x}]")

        # ==============================================================
        # FAZE 1: Omezeni prostoru (elipsa)
        # ==============================================================
        print("   Faze 1: Vytvarim masku elipsy...", flush=True)
        t0 = time.time()
        maska = vytvor_masku_elipsy(
            start, goal, height, width,
            rozsireni=config.ELIPSA_KOLMA_POLOOSA
        )
        pocet_pixelu = int(np.sum(maska))
        celkem_pixelu = height * width
        print(f"      Elipsa: {pocet_pixelu:,} pixelu "
              f"({100*pocet_pixelu/celkem_pixelu:.1f}% mapy) | "
              f"{time.time()-t0:.2f}s", flush=True)

        # ==============================================================
        # FAZE 2: Dijkstra VPRED (ze Startu)
        # ==============================================================
        print("   Faze 2: Dijkstra VPRED ze Startu...", flush=True)
        t0 = time.time()
        dist_forward, parents_y_f, parents_x_f = dijkstra_heatmap(
            working_grid, elev_grid, start, maska, grid_size, val_kopce,
            direction='forward'
        )
        print(f"      Dokonceno | {time.time()-t0:.2f}s", flush=True)

        # Kontrola dosazitelnosti
        if np.isinf(dist_forward[g_y, g_x]):
            print("   CHYBA: Cil neni dosazitelny ze Startu!")
            self.ax.set_title(
                "NENALEZENO!" + self.navod_hotovo, color="red", fontweight="bold"
            )
            self.fig.canvas.draw_idle()
            return

        # ==============================================================
        # FAZE 3: Dijkstra ZPET (z Cile)
        # ==============================================================
        print("   Faze 3: Dijkstra ZPET z Cile...", flush=True)
        t0 = time.time()
        dist_backward, parents_y_b, parents_x_b = dijkstra_heatmap(
            working_grid, elev_grid, goal, maska, grid_size, val_kopce,
            direction='backward'
        )
        print(f"      Dokonceno | {time.time()-t0:.2f}s", flush=True)

        # ==============================================================
        # FAZE 4: Generovani variant (Heatmapa + penalizace)
        # ==============================================================
        print("   Faze 4: Generovani variant...", flush=True)
        t0 = time.time()

        vybrane = []
        prijate_cesty = []

        # Heatmapa = soucet forward + backward casu
        heatmap = dist_forward + dist_backward
        optimalni_cas = dist_forward[g_y, g_x]

        # Dynamicky casovy limit: delsi postupy maji vetsi toleranci
        # (obihacka po silnici muze byt procentualne "drazsi" ale realne rychlejsi)
        delka_postupu = math.hypot(g_y - s_y, g_x - s_x)
        zakladni_odchylka = config.MAX_CAS_ODCHYLKA  # 0.30
        if delka_postupu > 2000:
            extra = 0.10 * math.log2(delka_postupu / 2000)
            zakladni_odchylka = min(zakladni_odchylka + extra, 0.55)
        limit_cas = optimalni_cas * (1.0 + zakladni_odchylka)

        # --- Var 1: Optimalni trasa (primo z dopredne mapy) ---
        var1 = trasuj_cestu(parents_y_f, parents_x_f, start, goal)
        if var1:
            vzd, prev, usili, road_ratio = self.spocitat_metriky(var1, working_grid)
            var1 = vyhlad_cestu(var1, working_grid, vyhlazeni=3)
            vybrane.append((usili, vzd, prev, var1))
            prijate_cesty.append(var1)
            print(f"      ✅ Var 1: {vzd/1000:.2f} km | "
                  f"+{prev:.0f}m | road={road_ratio*100:.0f}%", flush=True)

        # --- Var 2+: Hledani alternativ pres penalizovanou heatmapu ---
        heatmap_penalty = np.zeros((height, width), dtype=np.float64)
        # Penalizacni radius skaluje inverzne s delkou postupu (zmensen, aby netvoril obri stity)
        pen_r_zaklad = int(PODOBNOST_RADIUS * 1.5)
        if delka_postupu > 2000:
            pen_r = max(10, int(pen_r_zaklad * (2000 / delka_postupu) ** 0.5))
        else:
            pen_r = pen_r_zaklad
        # Penalizacni hodnota: drasticky snizena, aby trasy mohly prochazet uprostred,
        # pokud se i tak vejdou do 65% limitu. Ted je to spise 'vyhybej se' nez 'zabrana'.
        pen_hodnota = optimalni_cas * 0.04

        # Penalizuj Var 1
        if prijate_cesty:
            _penalizuj_heatmapu(heatmap_penalty, prijate_cesty[-1],
                                pen_r, pen_hodnota)

        for var_idx in range(1, POCET_VARIANT):
            # Heatmapa + kumulativni penalizace
            heatmap_pen = heatmap + heatmap_penalty
            # Hledame jen pixely s rozumnym casem (originalni heatmapa!)
            heatmap_search = np.where(
                maska & (heatmap <= limit_cas), heatmap_pen, np.inf
            )

            nalezeno_var = False
            for attempt in range(200):
                min_idx = np.argmin(heatmap_search)
                min_y, min_x = np.unravel_index(min_idx, (height, width))

                if np.isinf(heatmap_search[min_y, min_x]):
                    break

                # Trasuj cestu pres tento pivot
                cesta_f = trasuj_cestu(parents_y_f, parents_x_f, start, (min_y, min_x))
                cesta_b = trasuj_cestu(parents_y_b, parents_x_b, goal, (min_y, min_x))

                if not cesta_f or not cesta_b:
                    heatmap_search[min_y, min_x] = np.inf
                    continue

                trasa = cesta_f[:-1] + cesta_b[::-1]
                
                # Metriky MUSI byt spocitany z originalni grid trasy pred vyhlazenim
                # (vyhlazeni vytvari sub-pixely s nekonecnym sklonem)
                vzd, prev, usili, road_ratio = self.spocitat_metriky(trasa, working_grid)
                trasa = vyhlad_cestu(trasa, working_grid, vyhlazeni=3)

                # Tvrda kontrola duplikatu
                shoda = merit_podobnost(trasa, prijate_cesty, height, width, PODOBNOST_RADIUS)
                if shoda > config.MAX_SHODA:
                    heatmap_search[min_y, min_x] = np.inf
                    continue

                # Prijato!
                vybrane.append((usili, vzd, prev, trasa))
                prijate_cesty.append(trasa)
                _penalizuj_heatmapu(heatmap_penalty, trasa,
                                    pen_r, pen_hodnota)
                print(f"      ✅ Var {len(vybrane)}: {vzd/1000:.2f} km | "
                      f"+{prev:.0f}m | road={road_ratio*100:.0f}%", flush=True)
                nalezeno_var = True
                break

            if not nalezeno_var:
                break

        print(f"   Celkem nalezeno {len(vybrane)} variant | {time.time()-t0:.2f}s", flush=True)

        # ==============================================================
        # VYKRESLENI
        # ==============================================================
        nalezeno = 0
        for usili, vzd, prev, cesta in vybrane:
            vzd_km = vzd / 1000.0
            cas_min = (
                usili
                * NASOBIC_MERITKA
                * (zakladni_tempo_desetinne / (1000.0 * CENA_LESNI_CESTY))
            )
            cas_c = int(cas_min)
            cas_v = int((cas_min - cas_c) * 60)
            t_m = int(cas_min / vzd_km) if vzd_km > 0 else 0
            t_v = int(((cas_min / vzd_km) - t_m) * 60) if vzd_km > 0 else 0

            nalezeno += 1
            print(
                f"   Var {nalezeno}: {vzd_km:.2f} km | +{prev:.0f}m | {cas_c}:{cas_v:02d} ({t_m}:{t_v:02d}/km)"
            )
            label = (
                f"Var {nalezeno}: {vzd_km:.2f} km | +{prev:.0f}m | {cas_c}:{cas_v:02d}"
            )

            barva = colors[(nalezeno - 1) % len(colors)]
            self.vykresli_trasu(cesta, barva, label, bod_A, bod_B)

        t_celkovy = time.time() - t_celkovy_start
        if nalezeno:
            self.ax.legend(
                loc="upper left",
                title="Postupy a Casy",
                fontsize=10,
                title_fontsize=12,
                facecolor="white",
                framealpha=0.9,
                edgecolor="black",
            )
            self.ax.set_title(
                "HOTOVO!" + self.navod_hotovo, color="green", fontweight="bold"
            )
            print(f"\nHotovo! Vykresleno {nalezeno}/{POCET_VARIANT} variant "
                  f"za {t_celkovy:.1f}s.")
        else:
            self.ax.set_title(
                "NENALEZENO!" + self.navod_hotovo, color="red", fontweight="bold"
            )
            print("\nNenasla se zadna varianta.")

        self.fig.canvas.draw_idle()

    # =================================================================
    # VLASTNI TRASA (segmentovana pres prujezdni body)
    # =================================================================
    def spocitat_vlastni_trasu(self):
        self.ax.set_title("POCITAM VLASTNI TRASU...", color="orange", fontweight="bold")
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

        # Sestaveni posloupnosti: Start -> Prujezdni body -> Cil
        vsechny_body = [self.body[0]] + self.vlastni_body + [self.body[1]]

        cesta_celkova = []
        for i in range(len(vsechny_body) - 1):
            bod_A_seg = vsechny_body[i]
            bod_B_seg = vsechny_body[i + 1]
            s_y, s_x = img_to_grid(bod_A_seg[0], bod_A_seg[1])
            g_y, g_x = img_to_grid(bod_B_seg[0], bod_B_seg[1])

            seg_start = (s_y, s_x)
            seg_goal = (g_y, g_x)

            # Maska pro segment (individualni elipsa)
            maska_seg = vytvor_masku_elipsy(
                seg_start, seg_goal, height, width, rozsireni=0.50
            )

            # Dijkstra z bodu A segmentu
            val_kopce = self.slider_kopce.val
            dist_seg, parents_y_seg, parents_x_seg = dijkstra_heatmap(
                cost_grid_base, elev_grid, seg_start, maska_seg, grid_size, val_kopce, direction='forward'
            )

            # Kontrola dosazitelnosti
            if np.isinf(dist_seg[g_y, g_x]):
                print(f"Nelze najít cestu pro úsek {i + 1}")
                self.ax.set_title("CHYBA VLASTNÍ TRASY", color="red", fontweight="bold")
                return

            # Trasovani po gradientu
            cesta_usek = trasuj_cestu(parents_y_seg, parents_x_seg, seg_start, seg_goal)

            if cesta_usek is None:
                print(f"Nelze najít cestu pro úsek {i + 1}")
                self.ax.set_title("CHYBA VLASTNÍ TRASY", color="red", fontweight="bold")
                return
                
            cesta_usek = vyhlad_cestu(cesta_usek, cost_grid_base, vyhlazeni=3)

            if i > 0:
                cesta_celkova.extend(cesta_usek[1:])
            else:
                cesta_celkova.extend(cesta_usek)

        # Metriky
        vzd, prev, usili, road_ratio = self.spocitat_metriky(cesta_celkova, cost_grid_base)

        vzd_km = vzd / 1000.0
        cas_min = usili * NASOBIC_MERITKA * (zakladni_tempo_desetinne / (1000.0 * CENA_LESNI_CESTY))
        cas_c = int(cas_min)
        cas_v = int((cas_min - cas_c) * 60)
        t_m = int(cas_min / vzd_km) if vzd_km > 0 else 0
        t_v = int(((cas_min / vzd_km) - t_m) * 60) if vzd_km > 0 else 0

        label = f"Vlastní: {vzd_km:.2f} km | +{prev:.0f}m | {cas_c}:{cas_v:02d}"
        print(f"\n   Vlastni trasa: {vzd_km:.2f} km | +{prev:.0f}m | {cas_c}:{cas_v:02d} ({t_m}:{t_v:02d}/km)")

        # Vizualizace
        self.vykresli_trasu(cesta_celkova, "#FFA500", label, self.body[0], self.body[1], smooth=False)

        # Aktualizace legendy
        leg = self.ax.get_legend()
        if leg:
            leg.remove()
        self.ax.legend(
            loc="upper left",
            title="Postupy a Casy",
            fontsize=10,
            title_fontsize=12,
            facecolor="white",
            framealpha=0.9,
            edgecolor="black",
        )

        # Uklid pomocnych oranzovych kolecek prujezdnich bodu
        for p in self.vykreslene_vlastni_body:
            p.remove()
        self.vykreslene_vlastni_body.clear()

        self.ax.set_title("HOTOVO!" + self.navod_hotovo, color="green", fontweight="bold")
        self.fig.canvas.draw_idle()




app = AplikaceStavitel()
plt.show()
