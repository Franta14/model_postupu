# ============================================================
# CONFIG.PY - JEDINE MISTO KDE MENIS NASTAVENI MAPY
# ============================================================

# --- AKTIVNI MAPA (zmenit pri prepnuti mapy) ---
OMAP_FILE = "Holna_20240916.omap"
PNG_FILE  = "Holna.png"
PGW_FILE  = "Holna.pgw"
XML_FILE  = "Holna.xml"

# --- EKVIDISTANCE vrstevnic tve mapy (bezne 5m) ---
EKVIDISTANCE_M = 5.0

# ============================================================
# NASTAVENI BEZCE (nemenis per mapa, jen per zavodnich)
# ============================================================
ZAKLADNI_TEMPO_MIN = 3    # minuty
ZAKLADNI_TEMPO_SEC = 50   # vteriny  (= 3:50 min/km na zpevnene ceste)
POCET_VARIANT      = 3

# ============================================================
# PARAMETRY ALGORITMU (normalne nemen)
# ============================================================
ZAPNOUT_VYHLAZENI       = True
VYHLAZENI_BUNEK         = 3
NASOBIC_MERITKA         = 10.0
CENA_LESNI_CESTY        = 0.965

# --- PARAMETRY DIJKSTRA HEATMAP ---
ELIPSA_KOLMA_POLOOSA    = 0.50   # Mírně rozšířeno pro velkorysejší obíhačky (bylo 0.45)

PENALIZACE_SIRKA_PX     = 30     # Sirka penalizacni zony kolem nalezene trasy (v pixelech gridu)
MAX_CAS_ODCHYLKA        = 0.40   # Zahrne varianty až o 40% pomalejší (bezpečné obíhačky) (bylo 0.30)
PODOBNOST_RADIUS        = 10     # 10 bunek = 50m: co se povazuje za "stejnou stopu"
MAX_SHODA               = 0.65   # Max 65% prostorova shoda s prijatymi trasami

# ============================================================
# PARAMETRY GENERATORU POSTUPU
# ============================================================
DELKOVE_ROZSAHY         = [(400, 700), (700, 1200), (1200, 2200)]
HUSTOTA_KANDIDATU_KM2   = 40     # Zvýšeno pro vygenerování větší masy postupů (60-70 ve finále)
DEDUP_CTRL_RADIUS       = 80     # metry - zmenseno ze 100m pro vyssi hustotu unikatnich postupu
DEDUP_LEN_RATIO         = 0.30   # ...a delky se lisi mene nez 30%
MIN_ZAJIMAVOST          = 0.08   # Změkčeno pro vpuštění více přijatelných postupů

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
