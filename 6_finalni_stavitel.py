import numpy as np
import matplotlib.pyplot as plt
import math
import os
import sys
import time
from PIL import Image
from matplotlib.widgets import Slider, Button
from scipy.ndimage import binary_dilation, gaussian_filter, map_coordinates
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra as sp_dijkstra
import config
import generator_engine
import metriky

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
    # Nacteni gridu
    cost_grid_base = np.load(os.path.join(cache_dir, "cenova_mapa.npy"))
    elev_grid = np.load(os.path.join(cache_dir, "vyskova_mapa.npy"))
    
    # Jemne vyhlazeni (model uz je predhlazen v setup_mapa.py, sigma=10)
    elev_grid = gaussian_filter(elev_grid, sigma=2)
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

    def spocitat_metriky_wrap(self, cesta, working_grid_base):
        """Wrapper kolem sdileneho metriky.spocitat_metriky - identicky jako v 9_generator_postupu."""
        val_kopce = self.slider_kopce.val
        return metriky.spocitat_metriky(
            cesta, working_grid_base, elev_grid, grid_size, NASOBIC_MERITKA, val_kopce=val_kopce
        )

    def vykresli_trasu(self, cesta, barva, label, bod_A, bod_B, smooth=True):
        """Vyhladí a vykreslí jednu trasu na mapu."""
        if smooth and ZAPNOUT_VYHLAZENI:
            cesta_viz = generator_engine.vyhlad_cestu(cesta, cost_grid_base, vyhlazeni=VYHLAZENI_BUNEK)
        else:
            cesta_viz = cesta
        
        # Pridani prirozene vlnovitosti v lesnich usecich
        cesta_viz = self._pridej_prirozene_odchylky(cesta_viz, cost_grid_base)

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
    
    def _pridej_prirozene_odchylky(self, cesta, grid):
        """
        Přidá jemné, přirozené odchylky do lesních úseků trasy.
        Na cestách/pěšinách (cost < 1.09) trasa zůstává rovná.
        V lese se přidají sinusové mikro-vlny kolmo na směr postupu.
        Přechody cesta↔les jsou plynulé (fade in/out přes 15 bodů).
        """
        if len(cesta) < 10:
            return cesta
        
        h, w = grid.shape
        pts = [(float(p[0]), float(p[1])) for p in cesta]
        n = len(pts)
        
        # Deterministický seed z pozice trasy (stejná trasa = stejná vlnovitost)
        seed_val = int(abs(pts[0][0] * 1000 + pts[0][1] * 7 + pts[-1][0] * 13 + pts[-1][1] * 31)) % (2**31)
        rng = np.random.RandomState(seed_val)
        
        # 3 harmonické pro přirozený tvar
        phases = rng.uniform(0, 2 * math.pi, size=3)
        freqs = [0.04, 0.09, 0.17]
        amps_ratio = [0.55, 0.30, 0.15]
        
        # 1) Spočítat "surovou" amplitudu pro každý bod podle terénu
        raw_amp = np.zeros(n)
        for i in range(n):
            py, px = pts[i]
            y_int = max(0, min(h - 1, int(py)))
            x_int = max(0, min(w - 1, int(px)))
            cost = grid[y_int, x_int]
            if cost < 1.09:
                raw_amp[i] = 0.0        # cesta/pěšina
            elif cost < 1.20:
                raw_amp[i] = 2.0        # bílý les
            elif cost < 1.50:
                raw_amp[i] = 3.0        # polooles
            else:
                raw_amp[i] = 4.5        # hustník
        
        # 2) Vyhladit amplitudu klouzavým průměrem (fade in/out na hranicích terénu)
        fade_window = 15
        smooth_amp = np.convolve(raw_amp, np.ones(fade_window) / fade_window, mode='same')
        # Start a cíl bez odchylek
        smooth_amp[:5] = 0.0
        smooth_amp[-5:] = 0.0
        
        # 3) Aplikovat odchylky kolmo na směr postupu
        nova = list(pts)
        for i in range(1, n - 1):
            amp = smooth_amp[i]
            if amp < 0.1:
                continue
            
            # Sinusová vlna
            odchylka = 0.0
            for k in range(3):
                odchylka += amps_ratio[k] * math.sin(freqs[k] * i + phases[k])
            odchylka *= amp
            
            # Směr postupu (širší span pro hladkost)
            span = min(8, i, n - 1 - i)
            dy = pts[i + span][0] - pts[i - span][0]
            dx = pts[i + span][1] - pts[i - span][1]
            dist_dir = math.hypot(dy, dx)
            if dist_dir < 0.5:
                continue
            
            nx_perp = -dy / dist_dir
            ny_perp = dx / dist_dir
            
            new_py = pts[i][0] + odchylka * ny_perp
            new_px = pts[i][1] + odchylka * nx_perp
            
            ny_int = max(0, min(h - 1, int(new_py)))
            nx_int = max(0, min(w - 1, int(new_px)))
            if grid[ny_int, nx_int] < 9000.0:
                nova[i] = (new_py, new_px)
        
        # 4) Finální vyhlazení pro odstranění zbývajících ostrých rohů
        vyhlazena = [nova[0]]
        for i in range(1, n - 1):
            a = max(0, i - 2)
            b = min(n, i + 3)
            avg_y = sum(nova[j][0] for j in range(a, b)) / (b - a)
            avg_x = sum(nova[j][1] for j in range(a, b)) / (b - a)
            vyhlazena.append((avg_y, avg_x))
        vyhlazena.append(nova[-1])
        
        # Zachovat přesně start a cíl
        vyhlazena[0] = cesta[0]
        vyhlazena[-1] = cesta[-1]
        return vyhlazena

    # =================================================================
    # HLAVNI VYPOCET: Iterative Penalty (hledani vice variant)
    # =================================================================
    def spocitat_trasy(self):
        self.hotovo = True
        self.ax.set_title("POCITAM TRASY (Iterative Penalty)...", color="red", fontweight="bold")
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

        t_celkovy_start = time.time()
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
        maska = generator_engine.vytvor_masku_elipsy(
            start, goal, height, width,
            rozsireni=0.6
        )
        pocet_pixelu = int(np.sum(maska))
        celkem_pixelu = height * width
        print(f"      Elipsa: {pocet_pixelu:,} pixelu "
              f"({100*pocet_pixelu/celkem_pixelu:.1f}% mapy) | "
              f"{time.time()-t0:.2f}s", flush=True)

        # ==============================================================
        # FAZE 2: Generovani variant (Iterative Penalty)
        # ==============================================================
        print("   Faze 2: Generovani variant...", flush=True)
        t0 = time.time()

        vybrane = []
        prijate_cesty = []
        working_grid = cost_grid_base.copy()
        
        for pokus in range(3):
            t_iter = time.time()
            dist_forward, parents_y_f, parents_x_f = generator_engine.dijkstra_heatmap(
                working_grid, elev_grid, start, maska, grid_size, NASOBIC_MERITKA, kopce_vaha=val_kopce,
                direction='forward'
            )
            
            if np.isinf(dist_forward[g_y, g_x]):
                if len(vybrane) == 0:
                    print("   CHYBA: Cil neni dosazitelny ze Startu!")
                    self.ax.set_title("NENALEZENO!" + self.navod_hotovo, color="red", fontweight="bold")
                    self.fig.canvas.draw_idle()
                    return
                else:
                    break
                    
            trasa = generator_engine.trasuj_cestu(parents_y_f, parents_x_f, start, goal)
            if not trasa:
                break
                
            trasa_vyhlazena = generator_engine.vyhlad_cestu(trasa, cost_grid_base, vyhlazeni=3)
            
            shoda = generator_engine.merit_podobnost(trasa_vyhlazena, prijate_cesty, height, width, PODOBNOST_RADIUS)
            if pokus > 0 and shoda > 0.8:
                print(f"      [Pokus {pokus+1} zahozen] prilis podobna (shoda {shoda*100:.0f}%)")
                continue
                
            prijate_cesty.append(trasa_vyhlazena)
            
            vzd, prev, usili, usili_real, road_ratio = self.spocitat_metriky_wrap(trasa_vyhlazena, cost_grid_base)
            vybrane.append((usili_real, vzd, prev, trasa_vyhlazena))
            
            print(f"      ✅ Var {len(vybrane)} (pokus {pokus+1}): {vzd/1000:.2f} km | +{prev:.0f}m | road={road_ratio*100:.0f}% | cas_vypoctu: {time.time()-t_iter:.2f}s", flush=True)
            
            working_grid = generator_engine.penalizuj_grid(working_grid, trasa_vyhlazena, PODOBNOST_RADIUS * 2)

        print(f"   Celkem nalezeno {len(vybrane)} variant | {time.time()-t0:.2f}s", flush=True)

        # ==============================================================
        # VYKRESLENI
        # ==============================================================
        nalezeno = 0
        for usili, vzd, prev, cesta in vybrane:
            vzd_km = vzd / 1000.0
            cas_s = metriky.vypocti_cas(usili, ZAKLADNI_TEMPO_MIN, ZAKLADNI_TEMPO_SEC)
            tempo_s_na_km = (cas_s / vzd) * 1000 if vzd > 0 else 0

            nalezeno += 1
            cas_str = metriky.formatuj_cas(cas_s)
            tempo_str = metriky.formatuj_cas(tempo_s_na_km)
            print(
                f"   Var {nalezeno}: {vzd_km:.2f} km | +{prev:.0f}m | {cas_str} ({tempo_str}/km)"
            )
            label = (
                f"Var {nalezeno}: {vzd_km:.2f} km | +{prev:.0f}m | {cas_str}"
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
            maska_seg = generator_engine.vytvor_masku_elipsy(seg_start, seg_goal, height, width, rozsireni=0.6)

            # Dijkstra z bodu A segmentu
            val_kopce = self.slider_kopce.val
            dist_seg, parents_y_seg, parents_x_seg = generator_engine.dijkstra_heatmap(
                cost_grid_base, elev_grid, seg_start, maska_seg, grid_size, NASOBIC_MERITKA, kopce_vaha=val_kopce, direction='forward'
            )

            # Kontrola dosazitelnosti
            if np.isinf(dist_seg[g_y, g_x]):
                print(f"Nelze najít cestu pro úsek {i + 1}")
                self.ax.set_title("CHYBA VLASTNÍ TRASY", color="red", fontweight="bold")
                return

            # Trasovani po gradientu
            cesta_usek = generator_engine.trasuj_cestu(parents_y_seg, parents_x_seg, seg_start, seg_goal)

            if cesta_usek is None:
                print(f"Nelze najít cestu pro úsek {i + 1}")
                self.ax.set_title("CHYBA VLASTNÍ TRASY", color="red", fontweight="bold")
                return
                
            cesta_usek = generator_engine.vyhlad_cestu(cesta_usek, cost_grid_base, vyhlazeni=3)

            if i > 0:
                cesta_celkova.extend(cesta_usek[1:])
            else:
                cesta_celkova.extend(cesta_usek)

        # Metriky
        vzd, prev, usili_algo, usili_real, road_ratio = self.spocitat_metriky_wrap(cesta_celkova, cost_grid_base)

        vzd_km = vzd / 1000.0
        cas_s = metriky.vypocti_cas(usili_real, ZAKLADNI_TEMPO_MIN, ZAKLADNI_TEMPO_SEC)
        tempo_s_na_km = (cas_s / vzd) * 1000 if vzd > 0 else 0
        cas_str = metriky.formatuj_cas(cas_s)
        tempo_str = metriky.formatuj_cas(tempo_s_na_km)

        label = f"Vlastní: {vzd_km:.2f} km | +{prev:.0f}m | {cas_str}"
        print(f"\n   Vlastni trasa: {vzd_km:.2f} km | +{prev:.0f}m | {cas_str} ({tempo_str}/km)")

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
