import os, sys, glob, json, math
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Button
from PIL import Image
import config
import generator_engine
import metriky

class KuratorNastroj:
    def __init__(self):
        self.map_name = os.path.splitext(os.path.basename(config.OMAP_FILE))[0]
        self.cache_dir = os.path.join(config.CACHE_DIR, self.map_name)
        self.postupy_dir = os.path.join(self.cache_dir, "postupy")
        self.schvalene_dir = os.path.join(self.cache_dir, "schvalene_postupy")
        os.makedirs(self.schvalene_dir, exist_ok=True)
        
        # Nacteni gridu pro pripadne prepocty (editace)
        print("Načítám data mapy pro případné úpravy...")
        self.cost_grid = np.load(os.path.join(self.cache_dir, "cenova_mapa.npy"))
        self.meta = np.load(os.path.join(self.cache_dir, "cenova_mapa_meta.npy"))
        self.elev_grid = np.load(os.path.join(self.cache_dir, "vyskova_mapa.npy"))
        self.min_x, self.min_y, self.max_x, self.max_y, self.grid_size = self.meta
        self.height, self.width = self.cost_grid.shape
        
        self.img = Image.open(config.PNG_FILE).convert('RGB')
        self.orig_w, self.orig_h = self.img.size
        
        # Nacteni JSONu postupů
        self.json_files = glob.glob(os.path.join(self.postupy_dir, "*.json"))
        if not self.json_files:
            print("Žádné postupy ke schválení! Spusť nejprve 9_generator_postupu.py")
            sys.exit(0)
            
        self.current_idx = 0
        self.current_data = None
        self.vykreslene_prvky = []
        self.edit_mode = False
        self.edit_points = []
        
        self.setup_ui()
        self.load_current()
        plt.show()

    def setup_ui(self):
        self.fig = plt.figure(figsize=(15, 8))
        self.fig.canvas.manager.set_window_title("Kurátorský Nástroj - Scrollienteering")
        
        # Mapa
        self.ax_map = plt.axes([0.02, 0.05, 0.65, 0.9])
        self.ax_map.axis('off')
        self.im_plot = self.ax_map.imshow(np.zeros((10,10,3), dtype=np.uint8))
        
        # Text pro tabulku
        self.ax_text = plt.axes([0.7, 0.6, 0.28, 0.35])
        self.ax_text.axis('off')
        self.txt_info = self.ax_text.text(0, 1, "", va='top', ha='left', fontsize=11, family='monospace')
        
        # Tlacitka
        ax_btn_ok = plt.axes([0.7, 0.45, 0.13, 0.05])
        self.btn_ok = Button(ax_btn_ok, 'Schválit (Y)', color='lightgreen')
        self.btn_ok.on_clicked(self.schvalit)
        
        ax_btn_del = plt.axes([0.85, 0.45, 0.13, 0.05])
        self.btn_del = Button(ax_btn_del, 'Zahodit (N)', color='lightcoral')
        self.btn_del.on_clicked(self.zahodit)
        
        ax_btn_edit = plt.axes([0.7, 0.38, 0.28, 0.05])
        self.btn_edit = Button(ax_btn_edit, 'Upravit variantu ručně (E)', color='lightblue')
        self.btn_edit.on_clicked(self.toggle_edit)
        
        # Info o poctu
        self.ax_count = plt.axes([0.7, 0.25, 0.28, 0.1])
        self.ax_count.axis('off')
        self.txt_count = self.ax_count.text(0.5, 0.5, "", va='center', ha='center', fontsize=14)
        
        self.fig.canvas.mpl_connect("key_press_event", self.on_key)
        self.fig.canvas.mpl_connect("button_press_event", self.on_click)
        self.fig.canvas.mpl_connect("scroll_event", self.on_scroll)
        
    def grid_to_img(self, r, c):
        OOM_x = self.min_x + c * self.grid_size
        OOM_y = self.min_y + r * self.grid_size
        kalibrace = np.load(os.path.join(self.cache_dir, "kalibrace.npy"))
        cal_a, cal_b, cal_c, cal_d, cal_e, cal_f = kalibrace
        A = np.array([[cal_a, cal_b], [cal_d, cal_e]])
        b = np.array([OOM_x - cal_c, OOM_y - cal_f])
        col, row = np.linalg.solve(A, b)
        return int(col), int(row)

    def load_current(self):
        if self.current_idx >= len(self.json_files):
            print("Všechny postupy prošly kurátorem!")
            sys.exit(0)
            
        with open(self.json_files[self.current_idx], 'r', encoding='utf-8') as f:
            self.current_data = json.load(f)
            
        self.edit_mode = False
        self.edit_points = []
        self.txt_count.set_text(f"Postup {self.current_idx + 1} / {len(self.json_files)}")
        self.vykresli_stav()
        
    def get_bbox(self):
        coords_x, coords_y = [], []
        # Pridat start a cil (pixel coords via grid_to_img)
        sy, sx = self.current_data['start']['gy'], self.current_data['start']['gx']
        ey, ex = self.current_data['end']['gy'], self.current_data['end']['gx']
        px, py = self.grid_to_img(sy, sx)
        coords_x.append(px); coords_y.append(py)
        px, py = self.grid_to_img(ey, ex)
        coords_x.append(px); coords_y.append(py)
        
        # Pridat trasy
        for var in self.current_data['variants']:
            for y, x in var['cesta']:
                px, py = self.grid_to_img(y, x)
                coords_x.append(px); coords_y.append(py)
                
        margin = 300
        min_x = max(0, min(coords_x) - margin)
        max_x = min(self.orig_w, max(coords_x) + margin)
        min_y = max(0, min(coords_y) - margin)
        max_y = min(self.orig_h, max(coords_y) + margin)
        
        return min_x, max_x, min_y, max_y

    def vykresli_stav(self):
        for p in self.vykreslene_prvky:
            p.remove()
        self.vykreslene_prvky.clear()
        
        # Oriznout mapu
        x0, x1, y0, y1 = self.get_bbox()
        crop = self.img.crop((x0, y0, x1, y1))
        self.im_plot.set_data(np.array(crop))
        self.im_plot.set_extent([x0, x1, y1, y0])
        self.ax_map.set_xlim(x0, x1)
        self.ax_map.set_ylim(y1, y0)
        
        # Tabulka
        dist = self.current_data['dist_m']
        text = f"VZDUŠNÁ VZDÁLENOST: {dist:.0f} m\n"
        text += "-"*48 + "\n"
        text += "VAR (BARVA) | VZDÁL. | PŘEV. | ČAS   | TEMPO\n"
        text += "-"*48 + "\n"
        
        colors = ['red', 'blue', 'green', 'orange', 'cyan']
        colors_cz = ['Červená', 'Modrá', 'Zelená', 'Oranžová', 'Azurová']
        
        for i, var in enumerate(self.current_data['variants']):
            c_name = colors_cz[i % len(colors_cz)]
            text += f"{i+1} ({c_name[:7]:7s}) | {var['vzdal_m']:4d}m | {var['prevyseni_m']:3d}m | {var['cas_s']//60:2d}:{var['cas_s']%60:02d} | {var['tempo_str']}\n"
            
            # Vykresleni cesty
            wx, wy = [], []
            for y, x in var['cesta']:
                px, py = self.grid_to_img(y, x)
                wx.append(px)
                wy.append(py)
            
            color = colors[i % len(colors)]
            (l,) = self.ax_map.plot(wx, wy, color=color, linewidth=4, alpha=0.6)
            self.vykreslene_prvky.append(l)
            
        self.txt_info.set_text(text)
        
        # Zvyrazneni start a cíl
        sy, sx = self.current_data['start']['gy'], self.current_data['start']['gx']
        ey, ex = self.current_data['end']['gy'], self.current_data['end']['gx']
        spx, spy = self.grid_to_img(sy, sx)
        epx, epy = self.grid_to_img(ey, ex)
        (m1,) = self.ax_map.plot(spx, spy, 'mo', markersize=12, fillstyle='none', markeredgewidth=3)
        (m2,) = self.ax_map.plot(epx, epy, 'mo', markersize=12, fillstyle='none', markeredgewidth=3)
        self.vykreslene_prvky.extend([m1, m2])
        
        # Edit mode UI
        if self.edit_mode:
            self.ax_map.set_title("Režim úprav: Klikej průjezdní body a zmáčkni ENTER pro výpočet.")
            if self.edit_points:
                ex, ey = zip(*self.edit_points)
                (ep,) = self.ax_map.plot(ex, ey, 'ro-', markersize=8)
                self.vykreslene_prvky.append(ep)
        else:
            self.ax_map.set_title("Náhled postupu")
            
        self.fig.canvas.draw_idle()

    def schvalit(self, event=None):
        if not self.current_data: return
        fname = os.path.basename(self.json_files[self.current_idx])
        dest = os.path.join(self.schvalene_dir, fname)
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(self.current_data, f, indent=4)
        print(f"✅ Postup uložen do: {dest}")
        self.dalsi()

    def zahodit(self, event=None):
        print("❌ Postup zahozen.")
        # Můžeme soubor i fyzicky smazat z postupy/
        try:
            os.remove(self.json_files[self.current_idx])
            # Smazeme i PNG
            png = self.json_files[self.current_idx].replace('.json', '.png')
            if os.path.exists(png):
                os.remove(png)
        except Exception as e:
            print(e)
        self.dalsi()
        
    def toggle_edit(self, event=None):
        self.edit_mode = not self.edit_mode
        self.edit_points = []
        self.vykresli_stav()

    def dalsi(self):
        self.current_idx += 1
        self.load_current()

    def img_to_grid(self, col, row):
        kalibrace = np.load(os.path.join(self.cache_dir, "kalibrace.npy"))
        cal_a, cal_b, cal_c, cal_d, cal_e, cal_f = kalibrace
        OOM_x = cal_a * col + cal_b * row + cal_c
        OOM_y = cal_d * col + cal_e * row + cal_f
        gx = (OOM_x - self.min_x) / self.grid_size
        gy = (OOM_y - self.min_y) / self.grid_size
        return max(0, min(self.height - 1, int(gy))), max(0, min(self.width - 1, int(gx)))

    def on_click(self, event):
        if not self.edit_mode or event.inaxes != self.ax_map:
            return
        if event.button == 1: # Left click
            self.edit_points.append((event.xdata, event.ydata))
            self.vykresli_stav()
        elif event.button == 3: # Right click - undo
            if self.edit_points:
                self.edit_points.pop()
                self.vykresli_stav()

    def on_scroll(self, event):
        if event.inaxes != self.ax_map: return
        base_scale = 1.2
        scale = base_scale if event.button == 'down' else 1.0 / base_scale
        xlim, ylim = self.ax_map.get_xlim(), self.ax_map.get_ylim()
        xdata, ydata = event.xdata, event.ydata
        new_xlim = [xdata - (xdata - xlim[0]) * scale, xdata + (xlim[1] - xdata) * scale]
        new_ylim = [ydata - (ydata - ylim[0]) * scale, ydata + (ylim[1] - ydata) * scale]
        self.ax_map.set_xlim(new_xlim)
        self.ax_map.set_ylim(new_ylim)
        self.fig.canvas.draw_idle()

    def vypocti_vlastni_trasu(self):
        if len(self.edit_points) < 1: return
        
        print("Trkám vlastní trasu...")
        body = []
        sy, sx = self.current_data['start']['gy'], self.current_data['start']['gx']
        body.append((sy, sx))
        
        for px, py in self.edit_points:
            body.append(self.img_to_grid(px, py))
            
        ey, ex = self.current_data['end']['gy'], self.current_data['end']['gx']
        body.append((ey, ex))
        
        celkova_cesta = []
        for i in range(len(body) - 1):
            py, px = generator_engine.dijkstra_heatmap(
                self.cost_grid, self.elev_grid, body[i], None, self.grid_size, config.NASOBIC_MERITKA, kopce_vaha=25.0, direction='forward'
            )[1:]
            
            cesta_useku = generator_engine.trasuj_cestu(py, px, body[i], body[i+1])
            if cesta_useku:
                # napojit bez duplikace bodu
                if celkova_cesta and celkova_cesta[-1] == cesta_useku[0]:
                    celkova_cesta.extend(cesta_useku[1:])
                else:
                    celkova_cesta.extend(cesta_useku)
                    
        if celkova_cesta:
            smooth = generator_engine.vyhlad_cestu(celkova_cesta, self.cost_grid, 3)
            vzd, prev, usili, usili_real, _ = metriky.spocitat_metriky(
                smooth, self.cost_grid, self.elev_grid, self.grid_size, config.NASOBIC_MERITKA, 5.0
            )
            cas_s = metriky.vypocti_cas(usili_real, config.ZAKLADNI_TEMPO_MIN, config.ZAKLADNI_TEMPO_SEC)
            tempo = (cas_s / vzd) * 1000 if vzd > 0 else 0
            
            self.current_data['variants'].append({
                "vzdal_m": round(vzd),
                "prevyseni_m": round(prev),
                "cas_s": round(cas_s),
                "tempo_str": metriky.formatuj_cas(tempo),
                "cesta": smooth
            })
            
            print("Vlastní trasa přidána!")
            self.edit_mode = False
            self.edit_points = []
            self.vykresli_stav()

    def on_key(self, event):
        if event.key.lower() == 'y': self.schvalit()
        elif event.key.lower() == 'n': self.zahodit()
        elif event.key.lower() == 'e': self.toggle_edit()
        elif event.key == 'enter' and self.edit_mode: self.vypocti_vlastni_trasu()

if __name__ == '__main__':
    KuratorNastroj()
