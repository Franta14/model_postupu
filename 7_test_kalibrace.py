import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
import os

print("🔍 Spouštím Nástroj pro jemné doladění kalibrace...")

# 1. NAČTENÍ DAT A DOSAVADNÍ KALIBRACE
try:
    cost_grid = np.load("cenova_mapa.npy")
    height, width = cost_grid.shape
    kalibrace_data = np.load("kalibrace.npy")
except FileNotFoundError:
    print("❌ Chybí data nebo kalibrace.npy! Nejdřív naklikej kalibraci ve stavitelovi.")
    exit()

import config
img = Image.open(config.PNG_FILE)

# Držíme stav kalibrace v paměti
state = {
    'scale_x': kalibrace_data[0],
    'scale_y': kalibrace_data[1],
    'off_x': kalibrace_data[2],
    'off_y': kalibrace_data[3],
    'krok_px': 1.0  # O kolik pixelů obrázku se to posune na jedno zmáčknutí
}

# 2. PŘÍPRAVA POLOPRŮHLEDNÉ ČERVENÉ FÓLIE (Kreslíme jen rychlé cesty a louky)
print("🎨 Připravuji grafiku (tohle může trvat 2-3 vteřiny)...")
overlay_rgba = np.zeros((height, width, 4))
overlay_rgba[..., 0] = 1.0  # Červená barva
overlay_rgba[..., 3] = np.where(cost_grid < 1.15, 0.6, 0.0)  # Průhlednost (Vidět jsou jen cesty/louky)

fig, ax = plt.subplots(figsize=(14, 10))
fig.canvas.manager.set_window_title("Mikro-Kalibrátor (Zarovnání os)")

ax.imshow(img)

def get_extent():
    # Přepočet z matematické mřížky na obrazovku
    u_min = -state['off_x'] / state['scale_x']
    u_max = (width - state['off_x']) / state['scale_x']
    v_min = -state['off_y'] / state['scale_y']
    v_max = (height - state['off_y']) / state['scale_y']
    return [u_min, u_max, v_max, v_min]

# Vykreslení fólie
overlay = ax.imshow(overlay_rgba, extent=get_extent(), origin='upper')

titulek = "⌨️ ŠIPKY = Posun mřížky | +/- = Změna velikosti | E = Zrychlit krok | ENTER = ULOŽIT"
ax.set_title(titulek, fontweight='bold')
plt.tight_layout()

# 3. INTERAKTIVNÍ OVLÁDÁNÍ KLÁVESNICÍ
def update_view():
    overlay.set_extent(get_extent())
    fig.canvas.draw_idle()

def on_key(event):
    if event.key == 'right':
        state['off_x'] -= state['krok_px'] * state['scale_x']
    elif event.key == 'left':
        state['off_x'] += state['krok_px'] * state['scale_x']
    elif event.key == 'down':
        # Dolů znamená větší Y na obrázku
        state['off_y'] -= state['krok_px'] * state['scale_y']
    elif event.key == 'up':
        state['off_y'] += state['krok_px'] * state['scale_y']
    elif event.key == '+':
        # Zvětšení
        state['scale_x'] /= 1.002
        state['scale_y'] /= 1.002
    elif event.key == '-':
        # Zmenšení
        state['scale_x'] *= 1.002
        state['scale_y'] *= 1.002
    elif event.key == 'e':
        # Přepínač rychlosti posunu (1 px vs 5 px)
        state['krok_px'] = 5.0 if state['krok_px'] == 1.0 else 1.0
        print(f"⚡ Rychlost kroku změněna na: {state['krok_px']} pixelů")
    elif event.key == 'enter':
        # ULOŽENÍ!
        nove_hodnoty = np.array([state['scale_x'], state['scale_y'], state['off_x'], state['off_y']])
        np.save("kalibrace.npy", nove_hodnoty)
        print("\n✅ DOKONALÁ KALIBRACE ULOŽENA! Můžeš zavřít toto okno a zapnout Stavitele.")
        plt.close(fig)
        return
        
    update_view()

fig.canvas.mpl_connect('key_press_event', on_key)

print("\nNÁVOD:")
print("1. Kolečkem nebo ikonou lupy si přibliž nějakou křižovatku.")
print("2. POUŽIJ ŠIPKY na klávesnici a posuň červenou síť tak, aby přesně lícovala na šedé/černé cesty.")
print("3. Až to zacvakne, zmáčkni ENTER.")
plt.show()