import os
import json
import glob
import math
import numpy as np
import config
import shutil
import argparse
import sys

if sys.platform == "win32":
    import io
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

def convert_to_geojson():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache-dir', required=True)
    parser.add_argument('--map-id', required=True)
    parser.add_argument('--map-name', required=True)
    parser.add_argument('--terrain', required=True)
    parser.add_argument('--png-file', required=True)
    parser.add_argument('--offset-x', type=float, default=0.0)
    parser.add_argument('--offset-y', type=float, default=0.0)
    args = parser.parse_args()

    print("🚀 Starting GeoJSON export for Mobile App...")
    cache_dir = args.cache_dir
    input_dir = os.path.join(cache_dir, "schvalene_postupy")
    archiv_dir = os.path.join(cache_dir, "archiv_postupu")
    
    # Get metadata for grid_size conversion
    cache_cenova = os.path.join(cache_dir, "cenova_mapa_meta.npy")
    if not os.path.exists(cache_cenova):
        print("❌ Metadata cenova_mapa_meta.npy neexistuje!")
        return
        
    metadata = np.load(cache_cenova)
    min_x = metadata[0]
    min_y = metadata[1]
    grid_size = metadata[4]
    
    kalibrace = np.load(os.path.join(cache_dir, "kalibrace.npy"))
    cal_a, cal_b, cal_c, cal_d, cal_e, cal_f = kalibrace
    A = np.array([[cal_a, cal_b], [cal_d, cal_e]])

    # Automatické načtení přesného kalibračního posunu z cache (pokud existuje)
    offset_file = os.path.join(cache_dir, "kalibrace_offset.npy")
    if os.path.exists(offset_file):
        cal_dx, cal_dy = np.load(offset_file)
        offset_x = float(cal_dx)
        offset_y = float(cal_dy)
        print(f"🎯 Automaticky načten kalibrační offset: dx={offset_x:.3f} px, dy={offset_y:.3f} px")
    else:
        offset_x = args.offset_x
        offset_y = args.offset_y
        print(f"ℹ️ Použit výchozí offset: dx={offset_x:.3f} px, dy={offset_y:.3f} px")
    
    out_dir = os.path.join("export", "postupy")
    os.makedirs(out_dir, exist_ok=True)
    
    index_data = []
    index_path = os.path.join(out_dir, "postupy_index.json")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            try:
                existing = json.load(f)
                index_data = [x for x in existing if x.get("map_id") != args.map_id]
            except Exception:
                pass
    
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    img = Image.open(args.png_file)
    w, h = img.size
    max_zoom = 5
    scale = 2 ** max_zoom
    
    def to_lnglat(gy, gx):
        OOM_x = min_x + (gx + 0.5) * grid_size
        OOM_y = min_y + (gy + 0.5) * grid_size
        b = np.array([OOM_x - cal_c, OOM_y - cal_f])
        col, row = np.linalg.solve(A, b)
        
        px_x = (float(col) + offset_x) / scale
        px_y = (float(row) + offset_y) / scale
        return [px_x, -px_y]
        
    files = glob.glob(os.path.join(input_dir, "*.json"))
    if not files:
        print(f"❌ Žádné schválené postupy ve složce {input_dir}")
        return

    for idx, jfile in enumerate(files):
        with open(jfile, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        basename = os.path.basename(jfile)
        geojson_filename = basename.replace(".json", ".geojson")
        
        features = []
        
        start_pt = data["start"]
        if "oom_x" in start_pt and "oom_y" in start_pt:
            OOM_x = start_pt["oom_x"]
            OOM_y = start_pt["oom_y"]
            b = np.array([OOM_x - cal_c, OOM_y - cal_f])
            col, row = np.linalg.solve(A, b)
            px_x = (float(col) + offset_x) / scale
            px_y = (float(row) + offset_y) / scale
            start_coord = [px_x, -px_y]
        else:
            start_coord = to_lnglat(start_pt["gy"], start_pt["gx"])

        features.append({
            "type": "Feature",
            "geometry": { "type": "Point", "coordinates": start_coord },
            "properties": { "type": "start", "isom": start_pt.get("isom", "Start") }
        })
        
        end_pt = data["end"]
        if "oom_x" in end_pt and "oom_y" in end_pt:
            OOM_x = end_pt["oom_x"]
            OOM_y = end_pt["oom_y"]
            b = np.array([OOM_x - cal_c, OOM_y - cal_f])
            col, row = np.linalg.solve(A, b)
            px_x = (float(col) + offset_x) / scale
            px_y = (float(row) + offset_y) / scale
            end_coord = [px_x, -px_y]
        else:
            end_coord = to_lnglat(end_pt["gy"], end_pt["gx"])

        features.append({
            "type": "Feature",
            "geometry": { "type": "Point", "coordinates": end_coord },
            "properties": { "type": "end", "isom": end_pt.get("isom", "End") }
        })
        
        colors = ["#ff4444", "#4444ff", "#44ff44", "#ffaa00", "#aa00ff"]
        variants_meta = []
        
        for v_idx, variant in enumerate(data.get("variants", [])):
            coords = []
            for point in variant["cesta"]:
                coords.append(to_lnglat(point[0], point[1]))
                
            color = colors[v_idx % len(colors)]
            
            features.append({
                "type": "Feature",
                "geometry": { "type": "LineString", "coordinates": coords },
                "properties": {
                    "type": "variant", "id": v_idx + 1, "color": color,
                    "vzdal_m": variant["vzdal_m"], "prevyseni_m": variant["prevyseni_m"],
                    "cas_s": variant["cas_s"], "tempo_str": variant.get("tempo_str", "")
                }
            })
            
            variants_meta.append({
                "id": v_idx + 1, "color": color, "vzdal_m": variant["vzdal_m"],
                "prevyseni_m": variant["prevyseni_m"], "cas_s": variant["cas_s"],
                "tempo_str": variant.get("tempo_str", "")
            })
            
        geojson = {
            "type": "FeatureCollection",
            "features": features
        }
        
        out_file = os.path.join(out_dir, geojson_filename)
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(geojson, f, indent=2)
            
        # OPRAVENÉ HLEDÁNÍ PNG OBRÁZKŮ V ARCHIVU
        png_basename = "schvaleno_" + basename.replace(".json", ".png")
        png_src = os.path.join(archiv_dir, png_basename)
        
        if os.path.exists(png_src):
            png_dst = os.path.join(out_dir, basename.replace(".json", ".png"))
            shutil.copy2(png_src, png_dst)
        else:
            print(f"⚠️ Nenalezen náhled: {png_src}")
            
        index_data.append({
            "id": idx + 1,
            "map_id": args.map_id,
            "map_name": args.map_name,
            "terrain": args.terrain,
            "file": geojson_filename,
            "dist_m": data.get("dist_m", 0),
            "variants_count": len(variants_meta),
            "variants": variants_meta
        })
        
    with open(os.path.join(out_dir, "postupy_index.json"), "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2)
        
    print(f"✅ Exported {len(index_data)} procedures and thumbnails.")

if __name__ == "__main__":
    convert_to_geojson()

