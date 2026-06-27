import xml.etree.ElementTree as ET
import gpxpy
import math
import matplotlib.pyplot as plt

# --- NASTAVENÍ SOUBORŮ ---
omap_file = 'Homolka_Vojirov_20240917.omap'
gpx_file = 'activity_22413815024.gpx' # <-- Vlož název originálu s časem!

# Referenční bod z hlavičky mapy
REF_LAT = 49.02982779
REF_LON = 14.9847593
GRIVACE = 11.66

def wgs84_to_local(lat, lon):
    # Přepočet na metry vůči referenčnímu bodu
    dx = (lon - REF_LON) * 111320 * math.cos(math.radians(REF_LAT))
    dy = (lat - REF_LAT) * 111320
    
    # Rotace (Grivace)
    angle_rad = math.radians(-GRIVACE)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    
    local_x = dx * cos_a - dy * sin_a
    local_y = dx * sin_a + dy * cos_a
    
    return local_x, local_y

print("1. Načítám mapu pro vizualizaci...")
tree = ET.parse(omap_file)
root = tree.getroot()

symbol_map = {}
for elem in root.iter():
    if 'symbol' in elem.tag.lower():
        s_id = elem.attrib.get('id')
        s_code = elem.attrib.get('code')
        if s_id and s_code:
            symbol_map[s_id] = s_code

map_plot = {"Cesty": ([], []), "Paseky": ([], []), "Hustnik": ([], [])}

for obj in root.iter():
    if 'object' in obj.tag.lower():
        sym_id = obj.attrib.get('symbol')
        if not sym_id: continue
        isom = symbol_map.get(sym_id, "")
        
        for child in obj:
            if 'coords' in child.tag.lower() and child.text:
                pairs = child.text.strip().split(';')
                xs, ys = [], []
                for p in pairs:
                    parts = p.strip().split()
                    if len(parts) >= 2:
                        try:
                            xs.append(float(parts[0])/1000)
                            ys.append(float(parts[1])/1000)
                        except ValueError:
                            pass
                if not xs: continue
                
                # Uložíme body oddělené "None", aby se nevykreslily čáry napříč celou mapou
                if isom in ['506.0', '508.0']:
                    map_plot["Cesty"][0].extend(xs + [None])
                    map_plot["Cesty"][1].extend(ys + [None])
                elif isom in ['403.0', '404.0']:
                    map_plot["Paseky"][0].extend(xs + [None])
                    map_plot["Paseky"][1].extend(ys + [None])
                elif isom in ['406.0', '408.0', '410.0']:
                    map_plot["Hustnik"][0].extend(xs + [None])
                    map_plot["Hustnik"][1].extend(ys + [None])
                break

print("2. Načítám GPX...")
with open(gpx_file, 'r', encoding='utf-8') as f:
    gpx = gpxpy.parse(f)

gpx_x, gpx_y = [], []
for track in gpx.tracks:
    for segment in track.segments:
        for p in segment.points:
            x, y = wgs84_to_local(p.latitude, p.longitude)
            gpx_x.append(x)
            gpx_y.append(y)

print("3. Vykresluji... Zkontroluj okno s grafem!")
plt.figure(figsize=(10, 8))

# Vykreslení obrysů terénů
plt.plot(map_plot["Hustnik"][0], map_plot["Hustnik"][1], color='green', linewidth=1, label='Hustníky', alpha=0.5)
plt.plot(map_plot["Paseky"][0], map_plot["Paseky"][1], color='orange', linewidth=1, label='Paseky', alpha=0.5)
plt.plot(map_plot["Cesty"][0], map_plot["Cesty"][1], color='gray', linewidth=2, label='Cesty', alpha=0.7)

# Vykreslení GPX a středu
plt.plot(gpx_x, gpx_y, color='blue', linewidth=2, label='GPX Trasa')
plt.plot(0, 0, marker='X', color='red', markersize=15, label='Střed (Referenční bod)')

plt.title("Ověření polohy GPX vůči mapě")
plt.legend()
plt.axis('equal') 
plt.grid(True)
plt.show()