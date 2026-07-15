import os
import json
import glob
import math
import numpy as np
import config

def convert_to_geojson():
    print("🚀 Starting GeoJSON export for Mobile App...")
    input_dir = os.path.join("cache", "Homolka_Vojirov_20240917", "schvalene_postupy")
    
    # Get metadata for grid_size conversion
    cache_cenova = os.path.join("cache", "Homolka_Vojirov_20240917", "cenova_mapa_meta.npy")
    if not os.path.exists(cache_cenova):
        print("❌ Metadata cenova_mapa_meta.npy neexistuje!")
        return
        
    metadata = np.load(cache_cenova)
    min_x = metadata[0]
    min_y = metadata[1]
    grid_size = metadata[4]
    
    kalibrace = np.load(os.path.join("cache", "Homolka_Vojirov_20240917", "kalibrace.npy"))
    cal_a, cal_b, cal_c, cal_d, cal_e, cal_f = kalibrace
    A = np.array([[cal_a, cal_b], [cal_d, cal_e]])
    
    out_dir = os.path.join("export", "postupy")
    os.makedirs(out_dir, exist_ok=True)
    
    index_data = []
    
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    img = Image.open(config.PNG_FILE)
    w, h = img.size
    max_zoom = math.ceil(math.log2(max(w, h) / 256))
    scale = 2 ** max_zoom
    
    # Helper to convert (grid_y, grid_x) to (lng, lat) for CRS.Simple
    # Leaflet CRS.Simple maps (x, y) pixels at Zoom 0 to LngLat (x, -y)
    def to_lnglat(gy, gx):
        OOM_x = min_x + (gx + 0.5) * grid_size
        OOM_y = min_y + (gy + 0.5) * grid_size
        b = np.array([OOM_x - cal_c, OOM_y - cal_f])
        col, row = np.linalg.solve(A, b)
        
        px_x = (float(col) + config.MAP_OFFSET_X) / scale
        px_y = (float(row) + config.MAP_OFFSET_Y) / scale
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
        
        # Build GeoJSON feature collection
        features = []
        
        # 1. Start Point
        start_pt = data["start"]
        if "oom_x" in start_pt and "oom_y" in start_pt:
            OOM_x = start_pt["oom_x"]
            OOM_y = start_pt["oom_y"]
            b = np.array([OOM_x - cal_c, OOM_y - cal_f])
            col, row = np.linalg.solve(A, b)
            px_x = (float(col) + config.MAP_OFFSET_X) / scale
            px_y = (float(row) + config.MAP_OFFSET_Y) / scale
            start_coord = [px_x, -px_y]
        else:
            start_coord = to_lnglat(start_pt["gy"], start_pt["gx"])

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": start_coord
            },
            "properties": {
                "type": "start",
                "isom": start_pt.get("isom", "Start")
            }
        })
        
        # 2. End Point
        end_pt = data["end"]
        if "oom_x" in end_pt and "oom_y" in end_pt:
            OOM_x = end_pt["oom_x"]
            OOM_y = end_pt["oom_y"]
            b = np.array([OOM_x - cal_c, OOM_y - cal_f])
            col, row = np.linalg.solve(A, b)
            px_x = (float(col) + config.MAP_OFFSET_X) / scale
            px_y = (float(row) + config.MAP_OFFSET_Y) / scale
            end_coord = [px_x, -px_y]
        else:
            end_coord = to_lnglat(end_pt["gy"], end_pt["gx"])

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": end_coord
            },
            "properties": {
                "type": "end",
                "isom": end_pt.get("isom", "End")
            }
        })
        
        # 3. Variants (Lines)
        colors = ["#ff4444", "#4444ff", "#44ff44", "#ffaa00", "#aa00ff"]
        variants_meta = []
        
        for v_idx, variant in enumerate(data.get("variants", [])):
            coords = []
            for point in variant["cesta"]:
                # point is [y, x]
                coords.append(to_lnglat(point[0], point[1]))
                
            color = colors[v_idx % len(colors)]
            
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": coords
                },
                "properties": {
                    "type": "variant",
                    "id": v_idx + 1,
                    "color": color,
                    "vzdal_m": variant["vzdal_m"],
                    "prevyseni_m": variant["prevyseni_m"],
                    "cas_s": variant["cas_s"],
                    "tempo_str": variant.get("tempo_str", "")
                }
            })
            
            variants_meta.append({
                "id": v_idx + 1,
                "color": color,
                "vzdal_m": variant["vzdal_m"],
                "prevyseni_m": variant["prevyseni_m"],
                "cas_s": variant["cas_s"],
                "tempo_str": variant.get("tempo_str", "")
            })
            
        geojson = {
            "type": "FeatureCollection",
            "features": features
        }
        
        out_file = os.path.join(out_dir, geojson_filename)
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(geojson, f, indent=2)
            
        # Add to index
        index_data.append({
            "id": idx + 1,
            "file": geojson_filename,
            "dist_m": data.get("dist_m", 0),
            "variants_count": len(variants_meta),
            "variants": variants_meta
        })
        
    # Write index
    with open(os.path.join(out_dir, "postupy_index.json"), "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2)
        
    print(f"✅ Exported {len(index_data)} procedures to GeoJSON.")

if __name__ == "__main__":
    convert_to_geojson()
