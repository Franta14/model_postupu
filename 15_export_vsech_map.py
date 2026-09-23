import os
import subprocess
import sys

maps_to_export = [
    {
        "map_id": "homolka",
        "map_name": "Homolka",
        "terrain": "cesko",
        "cache_dir": "cache/Homolka_Vojirov_20240917",
        "png_file": "mapa.png",
        "circle_scale": 1.0
    },
    {
        "map_id": "holna",
        "map_name": "Holná",
        "terrain": "cesko",
        "cache_dir": "cache/Holna_20240916",
        "png_file": "Holna.png",
        "offset_x": 1,
        "offset_y": 9,
        "circle_scale": 2.5
    },
    {
        "map_id": "bilaskala",
        "map_name": "Bílá skála",
        "terrain": "cesko",
        "cache_dir": "cache/bilaskala",
        "png_file": "bilaskala.png",
        "circle_scale": 2.5
    }
]

def run_export():
    for m in maps_to_export:
        print(f"============================================================")
        print(f"Exporting map: {m['map_name']}")
        print(f"============================================================")
        
        # 1. Export geojson
        cmd1 = [
            sys.executable, "12_export_geojson.py",
            "--cache-dir", m["cache_dir"],
            "--map-id", m["map_id"],
            "--map-name", m["map_name"],
            "--terrain", m["terrain"],
            "--png-file", m["png_file"],
            "--offset-x", str(m.get("offset_x", 0)),
            "--offset-y", str(m.get("offset_y", 0))
        ]
        print(f"Running: {' '.join(cmd1)}")
        try:
            subprocess.run(cmd1, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error exporting {m['map_name']}")
            continue
        
        # 2. Export thumbnails
        cmd2 = [
            sys.executable, "14_export_thumbnails.py",
            "--map-id", m["map_id"],
            "--png-file", m["png_file"],
            "--circle-scale", str(m.get("circle_scale", 1.0))
        ]
        print(f"Running: {' '.join(cmd2)}")
        try:
            subprocess.run(cmd2, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error exporting thumbnails for {m['map_name']}")
            continue
        # 3. Export map tiles
        cmd3 = [
            sys.executable, "11_export_tiler.py",
            "--map-id", m["map_id"],
            "--png-file", m["png_file"]
        ]
        print(f"Running: {' '.join(cmd3)}")
        try:
            subprocess.run(cmd3, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error exporting tiles for {m['map_name']}")
            continue
        print("\n")

if __name__ == "__main__":
    run_export()

