# ============================================================
# CONFIG.PY - JEDINE MISTO KDE MENIS NASTAVENI MAPY
# ============================================================

# --- AKTIVNI MAPA (zmenit pri prepnuti mapy) ---
OMAP_FILE = "Homolka_Vojirov_20240917.omap"
PNG_FILE  = "mapa.png"
PGW_FILE  = "mapa.pgw"
XML_FILE  = "vel1.xml"

# --- EKVIDISTANCE vrstevnic tve mapy (bezne 5m) ---
EKVIDISTANCE_M = 5.0

# ============================================================
# NASTAVENI BEZCE (nemenis per mapa, jen per zavodnich)
# ============================================================
ZAKLADNI_TEMPO_MIN = 3    # minuty
ZAKLADNI_TEMPO_SEC = 40   # vteriny  (= 3:40 min/km na lesni ceste)
POCET_VARIANT      = 3

# ============================================================
# PARAMETRY ALGORITMU (normalne nemen)
# ============================================================
ZAPNOUT_VYHLAZENI       = True
VYHLAZENI_BUNEK         = 3
NASOBIC_MERITKA         = 10.0
CENA_LESNI_CESTY        = 0.965

# --- PARAMETRY DIJKSTRA HEATMAP ---
ELIPSA_KOLMA_POLOOSA    = 0.45   # Sirka elipsy jako podil vzdalenosti Start-Cil

PENALIZACE_SIRKA_PX     = 30     # Sirka penalizacni zony kolem nalezene trasy (v pixelech gridu)
MAX_CAS_ODCHYLKA        = 0.30   # Maximalni casova odchylka alternativy od optima (30%)
PODOBNOST_RADIUS        = 10     # 10 bunek = 50m: co se povazuje za "stejnou stopu"
MAX_SHODA               = 0.65   # Max 65% prostorova shoda s prijatymi trasami

# ============================================================
# PARAMETRY GENERATORU POSTUPU
# ============================================================
DELKOVE_ROZSAHY         = [(400, 700), (700, 1200), (1200, 2000), (2000, 3500)]
MAX_KANDIDATU           = 500    # Max pocet paru vyhodnocenych Dijkstrou
DEDUP_CTRL_RADIUS       = 200    # metry - dva postupy jsou "podobne" pokud starty/cile blize nez toto
DEDUP_LEN_RATIO         = 0.30   # ...a delky se lisi mene nez 30%
MIN_ZAJIMAVOST          = 0.15   # minimalni skore pro ulozeni

# ============================================================
# KALIBRACE MAPY
# ============================================================
# Kalibrační posun mapy (v pixelech). Tyto hodnoty lze zjistit přes "K" režim ve webové aplikaci.
MAP_OFFSET_X = 1
MAP_OFFSET_Y = 9

# ============================================================
# CACHE (nemenit)
# ============================================================
CACHE_DIR = "cache"
