"""
debug_elevation.py - Diagnostika presnosti vyskovych dat

Rezim 1 (vychozi): Zobrazi POUZE rasterizovane OCAD vrstevnice (cervene)
                    pres PNG mapu -> vizualni overeni pozic.
Rezim 2 (--model): Zobrazi vyskovy model (heatmapa + izolinie) pres PNG mapu.

Spusteni:
    python debug_elevation.py          # Pouze OCAD vrstevnice
    python debug_elevation.py --model  # Vyskovy model
"""

import os
import sys
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

try:
    import config
    map_image_file = config.PNG_FILE
    map_name = os.path.splitext(os.path.basename(config.OMAP_FILE))[0]
except ImportError:
    map_image_file = "mapa.png"
    map_name = "Homolka_Vojirov_20240917"


def load_common():
    """Nacte spolecna data (meta, kalibrace, obrazek)."""
    cache_dir = os.path.join("cache", map_name)
    meta_path = os.path.join(cache_dir, "cenova_mapa_meta.npy")
    cal_path = os.path.join(cache_dir, "kalibrace.npy")

    if not os.path.exists(meta_path):
        print(f"❌ Nenalezen soubor {meta_path}")
        return None
    
    meta = np.load(meta_path)
    cal = np.load(cal_path)
    min_x, min_y, max_x, max_y, grid_size = meta
    cal_a, cal_b, cal_c, cal_d, cal_e, cal_f = cal

    print("Načítám obrázek mapy...")
    if not os.path.exists(map_image_file):
        print(f"❌ Nenalezen obrázek mapy: {map_image_file}")
        return None
    img = mpimg.imread(map_image_file)

    return {
        'cache_dir': cache_dir,
        'min_x': min_x, 'min_y': min_y, 'grid_size': grid_size,
        'cal': (cal_a, cal_b, cal_c, cal_d, cal_e, cal_f),
        'img': img,
    }


def grid_to_img_coords(data, grid_data):
    """Prevede grid souradnice na PNG pixel souradnice."""
    h, w = grid_data.shape
    grid_rows, grid_cols = np.mgrid[0:h, 0:w]
    
    oom_x = data['min_x'] + grid_cols * data['grid_size']
    oom_y = data['min_y'] + grid_rows * data['grid_size']
    
    cal_a, cal_b, cal_c, cal_d, cal_e, cal_f = data['cal']
    det = cal_a * cal_e - cal_b * cal_d
    img_cols = (cal_e * (oom_x - cal_c) - cal_b * (oom_y - cal_f)) / det
    img_rows = (cal_a * (oom_y - cal_f) - cal_d * (oom_x - cal_c)) / det
    
    return img_cols, img_rows


def mode_contour_positions(data):
    """Rezim 1: Zobrazi raw OCAD vrstevnice (cervene) pres PNG mapu."""
    contour_path = os.path.join(data['cache_dir'], "contour_raster.npy")
    if not os.path.exists(contour_path):
        print(f"❌ Nenalezen soubor {contour_path}")
        print("   Spust nejprve: python setup_mapa.py")
        return

    print("Načítám rasterizované OCAD vrstevnice...")
    contour_raster = np.load(contour_path)
    
    img_cols, img_rows = grid_to_img_coords(data, contour_raster)
    
    print("Kreslím OCAD vrstevnice přes mapu...")
    fig, ax = plt.subplots(figsize=(14, 10))
    ax.imshow(data['img'])
    
    # Vykresleni OCAD vrstevnic jako cervene cary (scatter bodu)
    contour_mask = contour_raster > 0
    contour_rows, contour_cols = np.where(contour_mask)
    img_x = img_cols[contour_rows, contour_cols]
    img_y = img_rows[contour_rows, contour_cols]
    ax.scatter(img_x, img_y, color='red', s=0.8, alpha=0.9, marker='s')
    
    ax.set_title("DIAGNOSTIKA: Rasterizované OCAD vrstevnice (červené) vs. OB mapa",
                 fontsize=13, fontweight='bold')
    ax.axis('off')
    plt.tight_layout()
    print("Hotovo! Zobrazuji okno...")
    plt.show()


def mode_elevation_model(data):
    """Rezim 2: Zobrazi vyskovy model (heatmapa + izolinie) pres PNG mapu."""
    elev_path = os.path.join(data['cache_dir'], "vyskova_mapa.npy")
    if not os.path.exists(elev_path):
        print(f"❌ Nenalezen soubor {elev_path}")
        return

    print("Načítám výškový model...")
    elev_grid = np.load(elev_path)
    
    img_cols, img_rows = grid_to_img_coords(data, elev_grid)
    
    print("Kreslím heatmapu a vrstevnice nad mapou...")
    fig, ax = plt.subplots(figsize=(14, 10))
    ax.imshow(data['img'])
    
    ekv = getattr(config, 'EKVIDISTANCE_M', 5.0) if 'config' in dir() else 5.0
    elev_min = np.nanmin(elev_grid)
    elev_max = np.nanmax(elev_grid)
    levels = np.arange(np.floor(elev_min / ekv) * ekv,
                       np.ceil(elev_max / ekv) * ekv + ekv, ekv)
    
    contourf = ax.contourf(img_cols, img_rows, elev_grid,
                           levels=levels, alpha=0.4, cmap='jet')
    contours = ax.contour(img_cols, img_rows, elev_grid,
                          levels=levels, colors='black', linewidths=0.8, alpha=0.7)
    ax.clabel(contours, inline=True, fontsize=9, fmt='%1.0f m')
    
    cbar = plt.colorbar(contourf, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Nadmořská výška (m)", rotation=270, labelpad=15)
    
    # Prekrytí OCAD vrstevnic (oranzove body = presne pozice z .omap)
    contour_path = os.path.join(data['cache_dir'], "contour_raster.npy")
    if os.path.exists(contour_path):
        contour_raster = np.load(contour_path)
        c_mask = contour_raster > 0
        c_rows, c_cols = np.where(c_mask)
        c_img_x = img_cols[c_rows, c_cols]
        c_img_y = img_rows[c_rows, c_cols]
        ax.scatter(c_img_x, c_img_y, color='orange', s=0.3, alpha=0.7, marker='s',
                   label='OMAP vrstevnice')
    
    ax.set_title("Výškový model (černé izolinie) vs. OMAP vrstevnice (oranžové)",
                 fontsize=13, fontweight='bold')
    ax.axis('off')
    plt.tight_layout()
    print("Hotovo! Zobrazuji okno...")
    plt.show()


def main():
    data = load_common()
    if data is None:
        return
    
    if "--model" in sys.argv:
        mode_elevation_model(data)
    else:
        mode_contour_positions(data)


if __name__ == "__main__":
    main()
