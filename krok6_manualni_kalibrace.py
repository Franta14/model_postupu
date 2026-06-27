import xml.etree.ElementTree as ET
import gpxpy
import math
import matplotlib.pyplot as plt

# --- NASTAVENÍ SOUBORŮ ---
omap_file = 'Homolka_Vojirov_20240917.omap'
gpx_file = '5. 4. 2026 Velikonoce PGP - middle, H18-21_Top Masters, Čtrnáct František.gpx' 

plt.rcParams['keymap.save'] = ''
plt.rcParams['keymap.quit'] = ''

REF_LAT = 49.02982779
REF_LON = 14.9847593

print("1. Načítám mapu...")
tree = ET.parse(omap_file)
root = tree.getroot()
symbol_map = {elem.attrib.get('id'): elem.attrib.get('code') for elem in root.iter() if 'symbol' in elem.tag.lower()}
map_plot = {"Cesty": ([], []), "Voda": ([], []), "Louky": ([], [])}

for obj in root.iter():
    if 'object' in obj.tag.lower():
        sym_id = obj.attrib.get('symbol')
        if not sym_id: continue
        isom = symbol_map.get(sym_id, "")
        for child in obj:
            if 'coords' in child.tag.lower() and child.text:
                xs, ys = [], []
                for p in child.text.strip().split(';'):
                    parts = p.strip().split()
                    if len(parts) >= 2:
                        try:
                            xs.append(float(parts[0])/1000)
                            ys.append(-float(parts[1])/1000)
                        except ValueError: pass
                if xs:
                    if isom.startswith('30'): map_plot["Voda"][0].extend(xs + [None]); map_plot["Voda"][1].extend(ys + [None])
                    elif isom.startswith('50'): map_plot["Cesty"][0].extend(xs + [None]); map_plot["Cesty"][1].extend(ys + [None])
                    elif isom.startswith('40'): map_plot["Louky"][0].extend(xs + [None]); map_plot["Louky"][1].extend(ys + [None])
                break

print("2. Načítám GPX...")
with open(gpx_file, 'r', encoding='utf-8') as f:
    gpx = gpxpy.parse(f)

# Extrakce čistých WGS84 metrů (BEZ těžiště)
raw_gpx_x, raw_gpx_y = [], []
for track in gpx.tracks:
    for segment in track.segments:
        for p in segment.points:
            raw_gpx_x.append((p.longitude - REF_LON) * 111320 * math.cos(math.radians(REF_LAT)))
            raw_gpx_y.append((p.latitude - REF_LAT) * 111320)

# Výchozí nástřel, aby to nebylo mimo obrazovku
offset_x = 0
offset_y = 0
current_rotation = -11.66
scale_factor = 1.0

fig, ax = plt.subplots(figsize=(12, 9))
ax.plot(map_plot["Louky"][0], map_plot["Louky"][1], color='gold', linewidth=1.5, alpha=0.3, label='Louky/Paseky')
ax.plot(map_plot["Voda"][0], map_plot["Voda"][1], color='dodgerblue', linewidth=2, label='Voda/Potoky')
ax.plot(map_plot["Cesty"][0], map_plot["Cesty"][1], color='dimgray', linewidth=1.5, label='Cesty')
line, = ax.plot([], [], color='magenta', linewidth=3, label='Tvoje Trasa')

plt.title("MYŠ = Zoom | ŠIPKY = Posun | [A]/[D] = Rotace | [+]/[-] = Zvětšit | ENTER = Uložit")
plt.legend(loc='upper left')
plt.axis('equal')

def update_plot():
    angle_rad = math.radians(current_rotation)
    cos_a, sin_a = math.cos(angle_rad), math.sin(angle_rad)
    rot_x, rot_y = [], []
    
    # 💡 NOVÁ ROBUSTNÍ MATEMATIKA (Rotace a měřítko kolem absolutní nuly)
    for x, y in zip(raw_gpx_x, raw_gpx_y):
        tx, ty = x * scale_factor, y * scale_factor
        lx = tx * cos_a - ty * sin_a
        ly = tx * sin_a + ty * cos_a
        rot_x.append(lx + offset_x)
        rot_y.append(ly + offset_y)
        
    line.set_xdata(rot_x)
    line.set_ydata(rot_y)
    fig.canvas.draw_idle()

# Funkce pro hrubé přiblížení po startu
update_plot()
valid_x = [x for x in map_plot["Cesty"][0] if x is not None]
valid_y = [y for y in map_plot["Cesty"][1] if y is not None]
if valid_x and valid_y and raw_gpx_x:
    offset_x = (sum(valid_x)/len(valid_x)) - sum(raw_gpx_x)/len(raw_gpx_x)
    offset_y = (sum(valid_y)/len(valid_y)) - sum(raw_gpx_y)/len(raw_gpx_y)
update_plot()

def on_scroll(event):
    if event.inaxes != ax: return
    zoom_factor = 1 / 1.2 if event.button == 'up' else 1.2
    cur_xlim, cur_ylim = ax.get_xlim(), ax.get_ylim()
    xdata, ydata = event.xdata, event.ydata
    new_width, new_height = (cur_xlim[1] - cur_xlim[0]) * zoom_factor, (cur_ylim[1] - cur_ylim[0]) * zoom_factor
    relx, rely = (cur_xlim[1] - xdata) / (cur_xlim[1] - cur_xlim[0]), (cur_ylim[1] - ydata) / (cur_ylim[1] - cur_ylim[0])
    ax.set_xlim([xdata - new_width * (1-relx), xdata + new_width * (relx)])
    ax.set_ylim([ydata - new_height * (1-rely), ydata + new_height * (rely)])
    fig.canvas.draw_idle()

def on_key(event):
    global offset_x, offset_y, current_rotation, scale_factor
    pos_step = 2.0 if event.key.startswith('shift') else 20.0
    rot_step = 0.2 if event.key.startswith('shift') else 2.0
    scale_step = 0.001 if event.key.startswith('shift') else 0.01
    
    k = event.key.replace('shift+', '') 
    if k == 'right': offset_x += pos_step
    elif k == 'left': offset_x -= pos_step
    elif k == 'up': offset_y += pos_step
    elif k == 'down': offset_y -= pos_step
    elif k == 'a': current_rotation -= rot_step
    elif k == 'd': current_rotation += rot_step
    elif k in ['+', '=']: scale_factor += scale_step
    elif k in ['-', '_']: scale_factor -= scale_step
    elif k == 'enter':
        print("\n" + "="*40)
        print("✅ DOKONALÝ ZÁSAH! Tady jsou tvá nová ROBUSTNÍ čísla:")
        print(f"OFFSET_X = {offset_x:.2f}")
        print(f"OFFSET_Y = {offset_y:.2f}")
        print(f"ROTACE   = {current_rotation:.2f}")
        print(f"MERITKO  = {scale_factor:.4f}")
        print("="*40)
        plt.close()
        return
    update_plot()

fig.canvas.mpl_connect('scroll_event', on_scroll)
fig.canvas.mpl_connect('key_press_event', on_key)
plt.show()