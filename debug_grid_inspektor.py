"""
debug_grid_inspektor.py  (v2 - rychla verze)
=============================================
Zobrazuje cenovy grid VEDLE mapy PNG.
Klikni na LEVY panel (cenovy grid) pro detail dane oblasti.

OVLADANI:
  Klik leve tlacitko na levy panel  →  zoom detail v pravem panelu
  'q' nebo zavrit okno               →  konec

BARVY LEVEHO PANELU:
  Tmave zelena   <  0.87   Cesta / pesina
  Svetle zelena  0.87-1.1  Prusek / bily les
  Zluta          1.1 -1.4  Hustnik svetly / bily les
  Oranzova       1.4 -2.0  Hustnik stredni / tmavý
  Cervena        2.0 -5.0  Kamen / ryha / potok
  Cerna          >= 9000   NEPRUCHODNE (zed, budova)
"""

import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import BoundaryNorm, ListedColormap
import os, sys
import config

# ── Nacteni dat ──────────────────────────────────────────────────────────────
map_name  = os.path.splitext(os.path.basename(config.OMAP_FILE))[0]
cache_dir = os.path.join(config.CACHE_DIR, map_name)

print("Nacitam cenovy grid...")
cost_grid = np.load(os.path.join(cache_dir, "cenova_mapa.npy"))
meta = np.load(os.path.join(cache_dir, "cenova_mapa_meta.npy"))
min_x, min_y, max_x, max_y, grid_size = meta
height, width = cost_grid.shape

print(f"Grid: {width} x {height} bunek, {grid_size} m/bunka")
print(f"Impassable: {int(np.sum(cost_grid >= 9000)):,} bunek")
print(f"Cesty:      {int(np.sum(cost_grid < 0.87)):,}  bunek")

# Cenova mapa pro vizualizaci - omezime 9999 na rozumnou hodnotu
display_grid = np.clip(cost_grid, 0, 10.0)

# Barevna mapa
BOUNDARIES = [0.0, 0.87, 1.10, 1.40, 2.00, 5.00, 10.01]
COLORS = ['#1a7a1a', '#90ee90', '#ffd700', '#ff8c00', '#cc2200', '#111111']
cmap = ListedColormap(COLORS)
norm = BoundaryNorm(BOUNDARIES, cmap.N)

LEGEND = [
    mpatches.Patch(color='#1a7a1a', label='< 0.87  Cesta/pesina'),
    mpatches.Patch(color='#90ee90', label='0.87-1.10  Bily les (lehky)'),
    mpatches.Patch(color='#ffd700', label='1.10-1.40  Hustnik svetly'),
    mpatches.Patch(color='#ff8c00', label='1.40-2.00  Hustnik tmavý'),
    mpatches.Patch(color='#cc2200', label='2.00-5.00  Kamen/ryha'),
    mpatches.Patch(color='#111111', label='>= 5.0  NEPRUCHODNE'),
]

# ── Okno ─────────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(16, 8))
fig.canvas.manager.set_window_title('Grid Inspektor v2')
fig.patch.set_facecolor('#1e1e1e')

ax_grid = axes[0]
ax_zoom = axes[1]

ax_grid.imshow(display_grid, cmap=cmap, norm=norm,
               origin='upper', interpolation='nearest', aspect='equal')
ax_grid.set_title('Cenovy grid — KLIKNI pro detail', color='white', fontsize=10)
ax_grid.tick_params(colors='white')
for spine in ax_grid.spines.values():
    spine.set_edgecolor('#555')

ax_zoom.set_facecolor('#111')
ax_zoom.set_title('Klikni na levy panel...', color='white', fontsize=10)
ax_zoom.axis('off')

fig.legend(handles=LEGEND, loc='lower center', ncol=6, fontsize=7,
           facecolor='#2a2a2a', labelcolor='white', edgecolor='#555')

click_marker = [None]
RADIUS = 30  # bunek do kazde strany

def on_click(event):
    if event.inaxes is not ax_grid:
        return
    if event.button != 1:
        return

    gx_c = int(event.xdata)
    gy_c = int(event.ydata)

    gx_c = max(RADIUS, min(width  - RADIUS - 1, gx_c))
    gy_c = max(RADIUS, min(height - RADIUS - 1, gy_c))

    patch = cost_grid[gy_c - RADIUS: gy_c + RADIUS + 1,
                      gx_c - RADIUS: gx_c + RADIUS + 1]
    disp  = np.clip(patch, 0, 10.0)

    ax_zoom.cla()
    ax_zoom.imshow(disp, cmap=cmap, norm=norm,
                   origin='upper', interpolation='nearest', aspect='equal')

    # Hodnoty bunek (jen pri dost malem zoomu)
    rows_p, cols_p = patch.shape
    if rows_p <= 45 and cols_p <= 45:
        for r in range(rows_p):
            for c in range(cols_p):
                v = patch[r, c]
                txt = 'X' if v >= 9000 else f'{v:.2f}'
                fc  = 'white' if (v >= 1.4 or v >= 9000) else 'black'
                ax_zoom.text(c, r, txt, ha='center', va='center',
                             fontsize=4.5, color=fc)

    # Kriz uprostred
    ax_zoom.plot(RADIUS, RADIUS, 'r+', markersize=16, markeredgewidth=2)

    val = cost_grid[gy_c, gx_c]
    val_str = 'NEPRUCHODNE (>= 9000)' if val >= 9000 else f'{val:.4f}'

    # Statistiky vyreze
    imp_pct  = 100 * np.sum(patch >= 9000) / patch.size
    road_pct = 100 * np.sum(patch < 0.87)  / patch.size

    ax_zoom.set_title(
        f'Bunka [{gy_c}, {gx_c}]  →  hodnota: {val_str}\n'
        f'Oblast {cols_p}×{rows_p} bunek = {cols_p*grid_size:.0f}×{rows_p*grid_size:.0f} m  |  '
        f'Nepruchodne: {imp_pct:.1f}%   Cesty: {road_pct:.1f}%',
        color='white', fontsize=8
    )
    ax_zoom.axis('on')
    ax_zoom.tick_params(colors='white')

    # Marker na hlavnim panelu
    if click_marker[0]:
        try:
            click_marker[0].remove()
        except Exception:
            pass
    click_marker[0] = ax_grid.plot(gx_c, gy_c, 'r+',
                                   markersize=12, markeredgewidth=1.5)[0]
    fig.canvas.draw_idle()

def on_key(event):
    if event.key == 'q':
        plt.close('all')

fig.canvas.mpl_connect('button_press_event', on_click)
fig.canvas.mpl_connect('key_press_event', on_key)

print()
print("=" * 50)
print("  GRID INSPEKTOR")
print("  Klikni na LEVY panel pro detail oblasti.")
print("  'q' = zavrit")
print("=" * 50)

plt.tight_layout(rect=[0, 0.06, 1, 1])
plt.show()
