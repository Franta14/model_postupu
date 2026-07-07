import os
import json
import numpy as np
import xml.etree.ElementTree as ET
from shapely.geometry import Polygon, LineString, Point
import shapely.ops

# Nacteni konfigurace
CACHE_DIR = "cache/Homolka_Vojirov_20240917"
GROUPS_FILE = os.path.join(CACHE_DIR, "vrstevnice_groups.json")
META_FILE = os.path.join(CACHE_DIR, "cenova_mapa_meta.npy")

def load_data():
    with open(GROUPS_FILE, 'r') as f:
        groups_data = json.load(f)
    meta = np.load(META_FILE)
    return groups_data['groups'], meta

def main():
    groups, meta = load_data()
    min_x, min_y, max_x, max_y = meta[0], meta[1], meta[2], meta[3]
    
    print(f"Nacteno {len(groups)} skupin.")
    # Zde otestujeme logiku shapely pro uzavirani polygonu.
    
if __name__ == "__main__":
    main()
