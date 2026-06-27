import xml.etree.ElementTree as ET
import gpxpy
import matplotlib.pyplot as plt
from pyproj import Transformer

omap_file = 'Homolka_Vojirov_20240917.omap'
gpx_file = 'PGP_Velikonoce_4_OMRlong.gpx'

REF_X = -718000
REF_Y = -1165000

print("1. Načítám mapu...")
tree = ET.parse(omap_file)
root = tree.getroot()

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

print("2. Načítám GPX...")
transformer = Transformer.from_crs("epsg:4326", "epsg:5514", always_xy=True)
with open(gpx_file, 'r', encoding='utf-8') as f:
    gpx = gpxpy.parse(f)

gpx_xs, gpx_ys = [], []
has_time = 0

for track in gpx.tracks:
    for segment in track.segments:
        for p in segment.points:
            x, y = transformer.transform(p.longitude, p.latitude)
            gpx_xs.append(x - REF_X)
            gpx_ys.append(y - REF_Y)
            if p.time:
                has_time += 1

print(f"\n--- KONTROLA DAT ---")
print(f"GPX má {len(gpx_xs)} bodů.")
print(f"Z toho má uloženo i čas: {has_time} bodů.")

if has_time == 0:
    print("\n🚨 POZOR: V tvém GPX souboru úplně chybí čas (nebo byl smazán při ořezávání)!")
    print("Bez času nemůžeme měřit tempo běžce v terénech.")

print("\nKreslím obrázek... (otevře se v novém okně)")

# Vykreslení
plt.figure(figsize=(10, 8))
# Vykreslíme mapu jako šedé tečky (vezmeme každý 5. bod pro zrychlení)
plt.plot(map_xs[::5], map_ys[::5], '.', color='lightgray', markersize=1, label='Mapa (Geometrie)')
# Vykreslíme GPX jako modrou čáru
plt.plot(gpx_xs, gpx_ys, 'b-', linewidth=2, label='GPX Trasa (S-JTSK)')

plt.title("Vizuální kontrola překryvu Mapy a GPX")
plt.legend()
plt.axis('equal') 
plt.show() # Zobrazí okno!