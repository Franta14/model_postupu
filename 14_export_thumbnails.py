"""
14_export_thumbnails.py
Generuje předgenerované PNG náhledy (thumbnaily) pro dlaždice v mobilní aplikaci.
Pro každou mapu vytvoří thumbnail s výřezem kolem bounding boxu všech postupů.
Pro každý jednotlivý postup vytvoří individuální thumbnail.
"""
import os
import json
import glob
import math
from PIL import Image, ImageDraw
import config

Image.MAX_IMAGE_PIXELS = None

# Cílový poměr stran 4:5 (šířka:výška, IG portrait)
TARGET_ASPECT = 4 / 5
# Velikost výstupního thumbnailu (zvýšena pro masivní zoom a detailní panning ve frontendu)
THUMB_WIDTH = 2500
THUMB_HEIGHT = int(THUMB_WIDTH / TARGET_ASPECT)  # = 1250
# JPEG kvalita (85 = dobrý kompromis ostrost vs. velikost)
JPEG_QUALITY = 85

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


def geojson_to_pixel(coords, scale, offset_x, offset_y):
    """Převede GeoJSON souřadnice zpět na pixelové souřadnice v originální mapě."""
    pixels = []
    for c in coords:
        col = c[0] * scale - offset_x
        row = -c[1] * scale - offset_y
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
        pixels = geojson_to_pixel(coords, scale, config.MAP_OFFSET_X, config.MAP_OFFSET_Y)
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
    
    map_thumb_path = os.path.join(thumbs_dir, "map_homolka.jpg")
    thumb.save(map_thumb_path, "JPEG", quality=JPEG_QUALITY, optimize=True)
    file_size = os.path.getsize(map_thumb_path) / 1024
    print(f"    ✅ Uloženo: {map_thumb_path} ({THUMB_WIDTH}×{THUMB_HEIGHT}, {file_size:.1f} KB)")
    
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
        
        # --- Kresleni postupu (spojnice a kolecka) ---
        overlay = Image.new("RGBA", cropped.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)
        line_w = max(2, int(cropped.width * 0.003))
        radius = max(5, int(cropped.width * 0.012))
        color = (179, 0, 255, 200)  # OCAD fialova, polopruhledna
        
        def pt(c):
            col = c[0] * scale - config.MAP_OFFSET_X
            row = -c[1] * scale - config.MAP_OFFSET_Y
            return (col - crop_box[0], row - crop_box[1])
            
        features = per_postup_features[basename]
        # 1. Kresleni spojnice (vzdusna cara mezi startem a cilem)
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
            dist = math.hypot(x2 - x1, y2 - y1)
            # Utneme čáru těsně u okraje kružnice
            cut = radius + line_w + 2
            if dist > 2 * cut:
                nx = (x2 - x1) / dist
                ny = (y2 - y1) / dist
                nx1 = x1 + nx * cut
                ny1 = y1 + ny * cut
                nx2 = x2 - nx * cut
                ny2 = y2 - ny * cut
                draw.line([nx1, ny1, nx2, ny2], fill=color, width=line_w)
                
            route_meta[basename] = {
                "start": [(x1 / cropped.width) * 100, (y1 / cropped.height) * 100],
                "end": [(x2 / cropped.width) * 100, (y2 / cropped.height) * 100]
            }
                    
        # 2. Kresleni start, cil, kontrol
        for f in features:
            geom = f.get("geometry", {})
            props = f.get("properties", {})
            if geom.get("type") == "Point" and props.get("type") in ["start", "end", "control"]:
                x, y = pt(geom.get("coordinates", []))
                draw.ellipse([x - radius, y - radius, x + radius, y + radius], outline=color, width=line_w)
                if props.get("type") == "end":
                    inner = max(2, radius - line_w - 4)
                    draw.ellipse([x - inner, y - inner, x + inner, y + inner], outline=color, width=max(2, line_w//2))
                    
        composite = Image.alpha_composite(cropped.convert("RGBA"), overlay).convert("RGB")
        # ---------------------------------------------
        
        thumb = composite.resize((THUMB_WIDTH, THUMB_HEIGHT), Image.Resampling.LANCZOS)
        
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
    thumbs_meta = {
        "maps": {
            "homolka": "thumbs/map_homolka.jpg"
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
