"""
14_export_thumbnails.py
Generuje předgenerované PNG náhledy (thumbnaily) pro dlaždice v mobilní aplikaci.
Pro každou mapu vytvoří thumbnail s výřezem kolem bounding boxu všech postupů.
Pro každý jednotlivý postup vytvoří individuální thumbnail.
"""
import os
import sys
import json
import glob
import math
from PIL import Image, ImageDraw, ImageFilter
import numpy as np
try:
    from scipy.ndimage import gaussian_filter
except ImportError:
    # Záložní jednoduchý filtr pokud scipy chybí
    def gaussian_filter(arr, sigma=3.0):
        return arr

import config

if sys.platform == "win32":
    import io
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

Image.MAX_IMAGE_PIXELS = None

# Cílový poměr stran 4:5 (šířka:výška, IG portrait)
TARGET_ASPECT = 4 / 5
# Velikost výstupního thumbnailu (zvýšena na 3000 pro maximální ostrost i při vysokém zoomu na Retina displejích)
THUMB_WIDTH = 3000
THUMB_HEIGHT = int(THUMB_WIDTH / TARGET_ASPECT)  # = 3750
# JPEG kvalita (93 pro precizní ostrost linií bez artefaktů)
JPEG_QUALITY = 93
# Výchozí zoom kamery na úvodní stránce (700 % = detailní záběr mapy s čitelnými vrstevnicemi a kameny)
DEFAULT_MAP_ZOOM = 700

# Padding pro vyříznutí mapy kolem postupu (zajišťuje dostatek "masa" pro zoom bez přejetí mimo mapu)
BBOX_PADDING_RATIO = 0.35  # Velmi těsný ořez pro co největší detail

# Maximální šířka výřezu originální mapy pro zaručení vysokého detailu i u dlouhých postupů
MAX_CROP_WIDTH = 1600


def load_geojson_coords(geojson_path):
    """Načte všechny souřadnice z GeoJSON souboru (body i linie)."""
    with open(geojson_path, "r", encoding="utf-8") as f:
        geojson = json.load(f)

    coords = []
    for feature in geojson.get("features", []):
        geom = feature.get("geometry", {})
        if geom["type"] == "Point":
            coords.append(geom["coordinates"])
        elif geom["type"] == "LineString":
            coords.extend(geom["coordinates"])
    return coords


def geojson_to_pixel(coords, scale):
    """Převede GeoJSON souřadnice zpět na pixelové souřadnice v originální mapě."""
    pixels = []
    for c in coords:
        col = c[0] * scale
        row = -c[1] * scale
        pixels.append((col, row))
    return pixels


def compute_bbox(pixel_coords):
    """Spočítá bounding box z pixelových souřadnic."""
    cols = [p[0] for p in pixel_coords]
    rows = [p[1] for p in pixel_coords]
    return min(cols), min(rows), max(cols), max(rows)


def crop_to_aspect(bbox, img_width, img_height, aspect_ratio=TARGET_ASPECT, padding_ratio=BBOX_PADDING_RATIO):
    """Rozšíří bounding box na cílový poměr stran s paddingem, zarovná do hranic obrázku."""
    min_col, min_row, max_col, max_row = bbox
    
    # Přidáme padding
    width = max_col - min_col
    height = max_row - min_row
    pad_w = max(width * padding_ratio, 50)
    pad_h = max(height * padding_ratio, 50)
    
    min_col -= pad_w
    min_row -= pad_h
    max_col += pad_w
    max_row += pad_h
    
    # Aktuální rozměry
    width = max_col - min_col
    height = max_row - min_row
    current_aspect = width / height if height > 0 else 1
    
    # Přizpůsobíme na cílový poměr stran
    if current_aspect > aspect_ratio:
        # Příliš široký → zvýšíme výšku
        new_height = width / aspect_ratio
        diff = new_height - height
        min_row -= diff / 2
        max_row += diff / 2
    else:
        # Příliš vysoký → zvýšíme šířku
        new_width = height * aspect_ratio
        diff = new_width - width
        min_col -= diff / 2
        max_col += diff / 2
    
    width = max_col - min_col
    height = max_row - min_row

    # Zrušeno omezování přes MAX_CROP_WIDTH – chceme, aby se VŽDY
    # vešel celý postup (celý bbox bodů postupu) do obrázku dlaždice.

    return int(max(0, min_col)), int(max(0, min_row)), int(min(img_width, max_col)), int(min(img_height, max_row))


def compute_map_drift(cropped_img, norm_route_pts=None, zoom=DEFAULT_MAP_ZOOM):
    """
    Vypočítá optimální trajektorii kamery (startX/Y, midX/Y, endX/Y) pro dlaždici na homepage.
    - Analyzuje bílé / nezmapované okraje mapy a striktně se jim vyhýbá.
    - Směruje kameru do aktivních zón s nejvyšší hustotou kontrol a postupů.
    - Zajišťuje jemný, pomalý a filmově plynulý drift.
    """
    W, H = 100, 125
    small = cropped_img.resize((W, H), Image.Resampling.BOX)
    arr = np.array(small, dtype=np.float32)
    
    # Detekce bílého / prázdného okraje
    is_white = (arr[:, :, 0] > 232) & (arr[:, :, 1] > 232) & (arr[:, :, 2] > 232) & (np.ptp(arr, axis=2) < 22)
    
    # Detailní mapa: saturace a kontrast mapových prvků (vrstevnice, cesty, les)
    color_var = np.std(arr, axis=2)
    darkness = 255.0 - np.mean(arr, axis=2)
    detail_map = (color_var * 0.6 + darkness * 0.4) * (~is_white)
    if np.max(detail_map) > 0:
        detail_map /= np.max(detail_map)
        
    # Hustota postupů na mapě
    route_map = np.zeros((H, W), dtype=np.float32)
    if norm_route_pts and len(norm_route_pts) > 0:
        for (nx, ny) in norm_route_pts:
            col = int(round(nx * (W - 1)))
            row = int(round(ny * (H - 1)))
            if 0 <= col < W and 0 <= row < H:
                route_map[row, col] += 1.0
        route_map = gaussian_filter(route_map, sigma=4.5)
        if np.max(route_map) > 0:
            route_map /= np.max(route_map)
    else:
        route_map = detail_map.copy()
        
    # Velikost zobrazeného výřezu při zoomu (např. 700% -> viewport je 14.3% šířky i výšky)
    vp_pct = 100.0 / (zoom / 100.0)
    win_w = max(4, int(round(W * (vp_pct / 100.0))))
    win_h = max(4, int(round(H * (vp_pct / 100.0))))
    half_w = win_w // 2
    half_h = win_h // 2
    
    scores = np.zeros((H, W), dtype=np.float32)
    white_ratios = np.ones((H, W), dtype=np.float32)
    
    for r in range(half_h, H - half_h):
        for c in range(half_w, W - half_w):
            sub_w = is_white[r - half_h : r + half_h + 1, c - half_w : c + half_w + 1]
            w_ratio = np.mean(sub_w)
            white_ratios[r, c] = w_ratio
            # Striktní podmínka: maximálně 2 % bílého okraje v celém zorném poli
            if w_ratio <= 0.02:
                r_val = np.mean(route_map[r - half_h : r + half_h + 1, c - half_w : c + half_w + 1])
                d_val = np.mean(detail_map[r - half_h : r + half_h + 1, c - half_w : c + half_w + 1])
                score = (1.0 - w_ratio * 30.0) * (r_val * 3.0 + d_val * 0.5)
                scores[r, c] = max(0.001, score)
                
    if np.max(scores) == 0:
        min_w = np.min(white_ratios[half_h : H - half_h, half_w : W - half_w])
        best_pos = np.argwhere(white_ratios == min_w)
        r_best, c_best = best_pos[0]
        c1, r1 = c_best, r_best
        c2, r2 = c_best, r_best
        cm, rm = c_best, r_best
    else:
        threshold = np.percentile(scores[scores > 0], 80)
        top_candidates = np.argwhere(scores >= threshold)
        
        # Cílová vzdálenost pro jemný, decentní a pomalý drift (~7-9% šířky mapy)
        target_dist = 8.5
        best_pair = None
        best_diff = 999.0
        
        for r1_cand, c1_cand in top_candidates[::2]:
            for r2_cand, c2_cand in top_candidates[::2]:
                d = np.hypot(c2_cand - c1_cand, r2_cand - r1_cand)
                if 5.0 <= d <= 12.0:
                    diff = abs(d - target_dist)
                    if diff < best_diff:
                        best_diff = diff
                        best_pair = ((c1_cand, r1_cand), (c2_cand, r2_cand))
                        
        if best_pair is None:
            max_idx = np.argmax(scores)
            br, bc = np.unravel_index(max_idx, scores.shape)
            c1, r1 = bc - 3, br - 3
            c2, r2 = bc + 3, br + 3
        else:
            (c1, r1), (c2, r2) = best_pair
            
        # Půlka cesty s jemným organickým zakřivením
        cm = int(round((c1 + c2) / 2.0 + (r2 - r1) * 0.15))
        rm = int(round((r1 + r2) / 2.0 - (c2 - c1) * 0.15))
        
        if not (half_h <= rm < H - half_h and half_w <= cm < W - half_w and white_ratios[rm, cm] <= 0.03):
            cm = int(round((c1 + c2) / 2.0))
            rm = int(round((r1 + r2) / 2.0))

    half_vp = (vp_pct / 200.0)
    max_t = -(100.0 - vp_pct)
    def to_css(col, row):
        cx = col / float(W)
        cy = row / float(H)
        sx = max(max_t, min(0.0, -(cx - half_vp) * 100.0))
        sy = max(max_t, min(0.0, -(cy - half_vp) * 100.0))
        return round(float(sx), 1), round(float(sy), 1)

    sx, sy = to_css(c1, r1)
    ex, ey = to_css(c2, r2)
    mx, my = to_css(cm, rm)
    return {
        'zoom': zoom,
        'startX': sx, 'startY': sy,
        'midX': mx, 'midY': my,
        'endX': ex, 'endY': ey
    }


def generate_thumbnails():
    print("🖼️ Generuji náhledy dlaždic (thumbnaily)...")
    
    # Načteme originální mapu
    print(f"  Načítám mapu {config.PNG_FILE}...")
    img = Image.open(config.PNG_FILE).convert("RGB")
    img_w, img_h = img.size
    print(f"  Rozměry mapy: {img_w}×{img_h}")
    
    # Spočítáme scale (stejně jako v 12_export_geojson.py)
    max_zoom = math.ceil(math.log2(max(img_w, img_h) / 512))
    scale = 2 ** max_zoom
    print(f"  Max zoom: {max_zoom}, scale: {scale}")
    
    # Načteme GeoJSON soubory
    geojson_dir = os.path.join("export", "postupy")
    geojson_files = sorted(glob.glob(os.path.join(geojson_dir, "*.geojson")))
    
    if not geojson_files:
        print("⚠ Žádné GeoJSON soubory nenalezeny!")
        return
    
    print(f"  Nalezeno {len(geojson_files)} postupů.")
    
    # Výstupní složka
    thumbs_dir = os.path.join("export", "thumbs")
    os.makedirs(thumbs_dir, exist_ok=True)
    
    # Sesbíráme všechny pixelové souřadnice ze všech postupů (pro mapový thumbnail)
    all_pixels = []
    per_postup_pixels = {}
    per_postup_features = {}
    
    for geojson_file in geojson_files:
        basename = os.path.basename(geojson_file).replace(".geojson", "")
        with open(geojson_file, "r", encoding="utf-8") as f:
            features = json.load(f).get("features", [])
        per_postup_features[basename] = features
        
        coords = load_geojson_coords(geojson_file)
        pixels = geojson_to_pixel(coords, scale)
        all_pixels.extend(pixels)
        per_postup_pixels[basename] = pixels
    
    # 1) Thumbnail per mapa (bounding box všech postupů)
    print("\n  📐 Generuji thumbnail pro celou mapu (Homolka)...")
    bbox = compute_bbox(all_pixels)
    print(f"    Bounding box: col={bbox[0]:.0f}-{bbox[2]:.0f}, row={bbox[1]:.0f}-{bbox[3]:.0f}")
    
    crop_box = crop_to_aspect(bbox, img_w, img_h)
    print(f"    Crop box (4:5): left={crop_box[0]}, top={crop_box[1]}, right={crop_box[2]}, bottom={crop_box[3]}")
    
    cropped = img.crop(crop_box)
    thumb = cropped.resize((THUMB_WIDTH, THUMB_HEIGHT), Image.Resampling.LANCZOS)
    
    # Doostření pro maximální ostrost a čitelnost mapových prvků
    thumb = thumb.filter(ImageFilter.UnsharpMask(radius=1.3, percent=140, threshold=1))
    
    map_thumb_path = os.path.join(thumbs_dir, "map_homolka.jpg")
    thumb.save(map_thumb_path, "JPEG", quality=JPEG_QUALITY, optimize=True)
    file_size = os.path.getsize(map_thumb_path) / 1024
    print(f"    ✅ Uloženo: {map_thumb_path} ({THUMB_WIDTH}×{THUMB_HEIGHT}, {file_size:.1f} KB)")
    
    # Výpočet inteligentního a bezpečného driftu bez bílých okrajů
    print("    🧭 Počítám automatickou trajektorii kamery (vyhýbání se bílým okrajům)...")
    crop_w = crop_box[2] - crop_box[0]
    crop_h = crop_box[3] - crop_box[1]
    norm_pts = [((p[0] - crop_box[0]) / crop_w, (p[1] - crop_box[1]) / crop_h) for p in all_pixels]
    map_drift = compute_map_drift(cropped, norm_pts)
    print(f"    🎯 Automatický drift: {map_drift}")
    
    # 2) Thumbnail per postup (individuální bounding box)
    print(f"\n  📐 Generuji individuální thumbnaily pro {len(per_postup_pixels)} postupů...")
    route_meta = {}
    for basename, pixels in per_postup_pixels.items():
        if len(pixels) < 2:
            print(f"    ⚠ {basename}: příliš málo souřadnic, přeskakuji")
            continue
        
        bbox = compute_bbox(pixels)
        crop_box = crop_to_aspect(bbox, img_w, img_h)
        
        cropped = img.crop(crop_box)
        
        # --- Kresleni postupu (spojnice a kolecka) BYLO ODSTRANĚNO ---
        # Nyní kreslíme trasu plně dynamicky na frontendu pomocí SVG,
        # takže do JPEG se už trasa "nevypéká".
        
        def pt(c):
            col = c[0] * scale
            row = -c[1] * scale
            return (col - crop_box[0], row - crop_box[1])
            
        features = per_postup_features[basename]
        start_c = None
        end_c = None
        for f in features:
            geom = f.get("geometry", {})
            props = f.get("properties", {})
            if geom.get("type") == "Point":
                if props.get("type") == "start":
                    start_c = geom.get("coordinates", [])
                elif props.get("type") == "end":
                    end_c = geom.get("coordinates", [])
                    
        if start_c and end_c:
            x1, y1 = pt(start_c)
            x2, y2 = pt(end_c)
            route_meta[basename] = {
                "start": [(x1 / cropped.width) * 100, (y1 / cropped.height) * 100],
                "end": [(x2 / cropped.width) * 100, (y2 / cropped.height) * 100],
                "crop_scale": cropped.width / img_w  # Pro frontend normalizaci zoomu
            }
                    
        # 3) Vertikální 9:16 náhled pro sdílení v chatu (ve stylu IG Reel, vycentrovaný a orientovaný zdola nahoru)
        if start_c and end_c:
            c_start = (start_c[0] * scale, -start_c[1] * scale)
            c_end = (end_c[0] * scale, -end_c[1] * scale)
            dx = c_end[0] - c_start[0]
            dy = c_end[1] - c_start[1]
            dist_px = math.hypot(dx, dy)
            if dist_px > 0:
                ux = dx / dist_px
                uy = dy / dist_px
                cx_in = (c_start[0] + c_end[0]) / 2.0
                cy_in = (c_start[1] + c_end[1]) / 2.0

                # 2x supersampling pro ultra hladké antialiased vykreslení
                OUT_W, OUT_H = 1080, 1920
                W2, H2 = 2160, 3840
                cx2, cy2 = W2 / 2.0, H2 / 2.0
                
                iof_purple = (179, 0, 255) # #b300ff
                R2 = 64
                line_w2 = 11
                gap2 = 12
                edge_margin2 = 36 # téměř se dotýká horního a spodního okraje

                # Maximální možné přiblížení: kolečka se zespodu a shora skoro dotýkají okrajů karty
                target_route_h2 = H2 - 2 * (R2 + line_w2 / 2.0 + edge_margin2)

                zoom_factor2 = target_route_h2 / dist_px
                scale_in2 = 1.0 / zoom_factor2

                a = scale_in2 * (-uy)
                b = scale_in2 * (-ux)
                c = cx_in - a * cx2 - b * cy2
                d = scale_in2 * ux
                e = scale_in2 * (-uy)
                f = cy_in - d * cx2 - e * cy2

                card2 = img.transform((W2, H2), Image.Transform.AFFINE, data=(a, b, c, d, e, f), resample=Image.Resampling.BICUBIC)
                draw2 = ImageDraw.Draw(card2)
                pt_start2 = (cx2, cy2 + target_route_h2 / 2.0)
                pt_end2 = (cx2, cy2 - target_route_h2 / 2.0)

                # Spojnice a kolečka
                draw2.line([(pt_start2[0], pt_start2[1] - R2 - gap2), (pt_end2[0], pt_end2[1] + R2 + gap2)], fill=iof_purple, width=line_w2)
                draw2.ellipse([pt_start2[0] - R2, pt_start2[1] - R2, pt_start2[0] + R2, pt_start2[1] + R2], outline=iof_purple, width=line_w2)
                draw2.ellipse([pt_end2[0] - R2, pt_end2[1] - R2, pt_end2[0] + R2, pt_end2[1] + R2], outline=iof_purple, width=line_w2)

                final_share = card2.resize((OUT_W, OUT_H), Image.Resampling.LANCZOS)
                final_share = final_share.filter(ImageFilter.UnsharpMask(radius=1.2, percent=130, threshold=1))

                share_path = os.path.join(thumbs_dir, f"share_{basename}.jpg")
                final_share.save(share_path, "JPEG", quality=JPEG_QUALITY, optimize=True)
                route_meta[basename]["share_thumb"] = f"thumbs/share_{basename}.jpg"
                share_size = os.path.getsize(share_path) / 1024
                print(f"    📱 share_{basename}.jpg (9:16 IG reel, {share_size:.1f} KB)")

        
        thumb = cropped.resize((THUMB_WIDTH, THUMB_HEIGHT), Image.Resampling.LANCZOS)
        thumb = thumb.filter(ImageFilter.UnsharpMask(radius=1.3, percent=140, threshold=1))
        
        thumb_path = os.path.join(thumbs_dir, f"{basename}.jpg")
        thumb.save(thumb_path, "JPEG", quality=JPEG_QUALITY, optimize=True)
        file_size = os.path.getsize(thumb_path) / 1024
        print(f"    ✅ {basename}.jpg ({file_size:.1f} KB)")
    
    # 3) Aktualizujeme postupy_index.json s thumb cestami
    index_path = os.path.join(geojson_dir, "postupy_index.json")
    with open(index_path, "r", encoding="utf-8") as f:
        index_data = json.load(f)
    
    for entry in index_data:
        geojson_name = entry["file"].replace(".geojson", "")
        entry["thumb"] = f"thumbs/{geojson_name}.jpg"
    
    # Přidáme mapové thumbnail info a metadata tras pro animace
    import time
    thumbs_meta = {
        "version": int(time.time()),
        "maps": {
            "homolka": {
                "thumb": "thumbs/map_homolka.jpg",
                "drift": map_drift
            }
        },
        "routes": route_meta
    }
    
    thumbs_meta_path = os.path.join("export", "thumbs", "thumbs_meta.json")
    with open(thumbs_meta_path, "w", encoding="utf-8") as f:
        json.dump(thumbs_meta, f, indent=2)
    
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2)
    
    print(f"\n🎉 Hotovo! Vygenerováno {len(per_postup_pixels) + 1} thumbnailů do {thumbs_dir}/")


if __name__ == "__main__":
    generate_thumbnails()
