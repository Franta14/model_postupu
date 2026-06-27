import xml.etree.ElementTree as ET
import gpxpy
from pyproj import Transformer

omap_file = 'Homolka_Vojirov_20240917.omap'
gpx_file = 'PGP_Velikonoce_4_OMRlong.gpx'

print("--- DIAGNOSTIKA SOUŘADNIC ---")
tree = ET.parse(omap_file)
root = tree.getroot()

# Opravené hledání souřadnic, které ignoruje XML namespaces
map_xs, map_ys = [], []
for elem in root.iter():
    if 'coords' in elem.tag.lower() and elem.text:
        pairs = elem.text.strip().split(';')
        for p in pairs:
            parts = p.strip().split()
            if len(parts) >= 2:
                try:
                    map_xs.append(float(parts[0])/1000)
                    map_ys.append(float(parts[1])/1000)
                except ValueError:
                    pass

print("1. MAPA (papírové metry):")
if map_xs:
    print(f"Osa X: od {min(map_xs):.2f} do {max(map_xs):.2f}")
    print(f"Osa Y: od {min(map_ys):.2f} do {max(map_ys):.2f}")
else:
    print("Chyba: Nenašly se žádné souřadnice v mapě!")

transformer = Transformer.from_crs("epsg:4326", "epsg:5514", always_xy=True)
with open(gpx_file, 'r', encoding='utf-8') as f:
    gpx = gpxpy.parse(f)

gpx_xs, gpx_ys = [], []
for track in gpx.tracks:
    for segment in track.segments:
        for p in segment.points:
            x, y = transformer.transform(p.longitude, p.latitude)
            gpx_xs.append(x)
            gpx_ys.append(y)

print("\n2. GPX STOPA (S-JTSK metry v realitě):")
if gpx_xs:
    print(f"Osa X: od {min(gpx_xs):.0f} do {max(gpx_xs):.0f}")
    print(f"Osa Y: od {min(gpx_ys):.0f} do {max(gpx_ys):.0f}")
else:
    print("Chyba: Prázdné GPX.")