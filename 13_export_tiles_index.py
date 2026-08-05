import os
import json
import glob

print("Vytvarim index dlazdic pro offline stahovani...")

EXPORT_DIR = "export"
TILES_DIR = os.path.join(EXPORT_DIR, "tiles")
INDEX_FILE = os.path.join(EXPORT_DIR, "tiles_index.json")

if not os.path.exists(TILES_DIR):
    print("❌ Složka s dlaždicemi nebyla nalezena. Spusťte nejdříve 11_export_tiler.py")
    exit(1)

tile_paths = []
# Walk through tiles directory recursively
for root, _, files in os.walk(TILES_DIR):
    for file in files:
        if file.endswith('.png'):
            # Vytvořit relativní cestu ve tvaru 'tiles/z/x/y.png'
            full_path = os.path.join(root, file)
            # Relativní k export složce
            rel_path = os.path.relpath(full_path, EXPORT_DIR)
            # Převést na lomítka pro web
            web_path = rel_path.replace(os.sep, '/')
            tile_paths.append(web_path)

print(f"Nalezeno {len(tile_paths)} dlazdic.")

with open(INDEX_FILE, "w", encoding="utf-8") as f:
    json.dump(tile_paths, f)

print(f"Index ulozen do {INDEX_FILE}")
