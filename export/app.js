// ==========================================
// 1. GLOBÁLNÍ DATA A NASTAVENÍ (STATE)
// ==========================================
let postupyData = [];
let geojsonCache = {};
let mapInstances = {}; 
let currentLayers = {}; 
let currentOverlays = {}; 
let currentTileLayers = {}; 
const iofPurple = "#b300ff";
let profileSelectedTerrain = 'Vše';

let userSettings = JSON.parse(localStorage.getItem('user_settings')) || {
    pace: 220, 
    language: 'cs',
    theme: 'system'
};

// ==========================================
// 2. JAZYKOVÝ SLOVNÍK (i18n) A TUTORIAL
// ==========================================
const i18n = {
    cs: {
        settings: "Nastavení", runner: "BĚŽEC", paceOnRoad: "Tempo na cestě",
        application: "APLIKACE", language: "Jazyk", theme: "Vzhled",
        theme_system: "Systémový", theme_light: "Světlý", theme_dark: "Tmavý",
        offlineMaps: "Uložit mapy offline", download: "Stáhnout",
        maps: "MAPY", clearCache: "Vymazat cache",
        saved: "Uložené", all: "Vše", analyzed: "Analyz.", km: "Km", hours: "Hodin",
        noSaved: "Žádné uložené postupy", noSavedDesc: "Klikni ve feedu na ikonku záložky pro uložení.",
        options: "Volby", aerial: "m vzdušně",
        bioDesc: "Zde najdeš všechny své oblíbené volby postupů z tréninků a závodů.",
        confirmClear: "Opravdu chceš vymazat uložené offline mapy?", cacheCleared: "Cache byla vymazána.",
        searchRoutes: "Hledat postupy...",
        tutSwipe: "Potáhni nahoru pro další", tutLike: "Dvojklik pro To se mi líbí",
        tutOptions: "Klikni na Volby pro srovnání", tutBtn: "Rozumím!"
    },
    en: {
        settings: "Settings", runner: "RUNNER", paceOnRoad: "Pace on road",
        application: "APPLICATION", language: "Language", theme: "Appearance",
        theme_system: "System", theme_light: "Light", theme_dark: "Dark",
        offlineMaps: "Save maps offline", download: "Download",
        maps: "MAPS", clearCache: "Clear cache",
        saved: "Saved", all: "All", analyzed: "Analyz.", km: "Km", hours: "Hours",
        noSaved: "No saved routes", noSavedDesc: "Click the bookmark icon in the feed to save.",
        options: "Options", aerial: "m aerial",
        bioDesc: "Here you can find all your favorite route choices from training and races.",
        confirmClear: "Do you really want to clear offline maps?", cacheCleared: "Cache cleared.",
        searchRoutes: "Search routes...",
        tutSwipe: "Swipe up for next route", tutLike: "Double tap to like",
        tutOptions: "Click Options for comparisons", tutBtn: "Got it!"
    }
};

function t(key) { return i18n[userSettings.language][key] || key; }

function getRoutesCountText(count) {
    if (userSettings.language === 'en') return count === 1 ? '1 route' : count + ' routes';
    if (count === 1) return '1 postup';
    if (count >= 2 && count <= 4) return count + ' postupy';
    return count + ' postupů';
}

function formatPace(sec) {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60).toString().padStart(2, '0');
    return `${m}:${s} min/km`;
}

function getAdjustedTime(baseSeconds) {
    const pythonErrorCorrection = 0.965 / 0.750;
    return baseSeconds * pythonErrorCorrection * (userSettings.pace / 220);
}

function updateUITexts() {
    const searchInputs = document.querySelectorAll('input[type="search"], input[type="text"], input[placeholder*="Hledat"], input[placeholder*="Search"]');
    searchInputs.forEach(input => {
        input.placeholder = t('searchRoutes');
    });
}

// ==========================================
// 3. INJEKCE CSS STYLŮ
// ==========================================
const style = document.createElement('style');
style.innerHTML = `
:root {
    --bg-color: #ffffff; --text-color: #000000; --secondary-bg: #f2f2f6; --border-color: #e5e5ea;
    --pill-bg: #e5e5ea; --pill-text: #000; --pill-active-bg: #000; --pill-active-text: #fff;
    --accent: #b300ff; --nav-icon-color: #000000; --search-bg: #f2f2f6;
}
:root[data-theme="dark"] {
    --bg-color: #000000; --text-color: #ffffff; --secondary-bg: #1c1c1e; --border-color: #2c2c2e;
    --pill-bg: #2c2c2e; --pill-text: #fff; --pill-active-bg: #fff; --pill-active-text: #000;
    --nav-icon-color: #ffffff; --search-bg: #2c2c2e;
}
@media (prefers-color-scheme: dark) {
    :root[data-theme="system"] {
        --bg-color: #000000; --text-color: #ffffff; --secondary-bg: #1c1c1e; --border-color: #2c2c2e;
        --pill-bg: #2c2c2e; --pill-text: #fff; --pill-active-bg: #fff; --pill-active-text: #000;
        --nav-icon-color: #ffffff; --search-bg: #2c2c2e;
    }
}

html, body { margin: 0; padding: 0; width: 100%; height: 100%; background-color: var(--bg-color) !important; color: var(--text-color) !important; overflow: hidden; }

/* SCROLLOVÁNÍ NA IPHONECH */
#screen-scroll { position: absolute; top: 0; left: 0; right: 0; bottom: 0; height: 100dvh !important; overflow: hidden; }
#reels-container { position: absolute; top: 0; left: 0; right: 0; bottom: 0; height: 100dvh !important; overflow-y: scroll; scroll-snap-type: y mandatory; -webkit-overflow-scrolling: touch; overscroll-behavior-y: none; }
.reel { height: 100dvh !important; width: 100%; scroll-snap-align: start; scroll-snap-stop: always; position: relative; }

/* DŮLEŽITÉ: Touch akce povoluje scrollování a pinch zoom v mapě */
.leaflet-container { touch-action: pan-y pinch-zoom !important; }
.leaflet-container.zoomed-in { touch-action: none !important; }

/* SPODNÍ LIŠTA A IKONKY */
div.bottom-nav, nav.bottom-nav, .bottom-nav, #bottom-nav { background: var(--bg-color) !important; border-top: 1px solid var(--border-color) !important; }
.nav-btn { color: var(--nav-icon-color) !important; opacity: 0.4 !important; }
.nav-btn.active { color: var(--nav-icon-color) !important; opacity: 1 !important; }
.nav-btn svg { stroke: var(--nav-icon-color); }
.nav-btn.active svg { stroke: var(--nav-icon-color); }

/* STORIES A HLEDÁNÍ */
.story-item, .story-item span, .story-item div { color: var(--text-color) !important; }
.search-bar, .search-container, div:has(> input[type="search"]) { background-color: var(--search-bg) !important; border-radius: 12px !important; border: none !important; }
input[type="search"], input[type="text"] { background-color: transparent !important; color: var(--text-color) !important; border: none !important; outline: none !important; box-shadow: none !important; -webkit-appearance: none !important; padding: 8px !important; border-radius: 0 !important; }
input::placeholder { color: #888 !important; }

/* PILLS A NASTAVENÍ */
.profile-pills-container::-webkit-scrollbar { display: none; }
.profile-pills-container { -ms-overflow-style: none; scrollbar-width: none; }
.ig-pill { padding: 8px 16px; border-radius: 20px; border: 1px solid var(--border-color); background: var(--pill-bg); color: var(--pill-text); font-weight: 600; font-size: 0.85rem; cursor: pointer; white-space: nowrap; }
.ig-pill.active { background: var(--pill-active-bg); color: var(--pill-active-text); border-color: var(--pill-active-bg); }
.settings-section { margin-bottom: 30px; }
.settings-title { font-size: 0.8rem; text-transform: uppercase; color: #888; margin-bottom: 15px; font-weight: 600; letter-spacing: 1px; padding-left: 20px;}
.settings-row { display: flex; justify-content: space-between; align-items: center; padding: 15px 20px; border-bottom: 1px solid var(--border-color); background: var(--bg-color); }
.settings-row select, .settings-btn { background: var(--secondary-bg); color: var(--text-color); border: 1px solid var(--border-color); padding: 8px 12px; border-radius: 8px; font-size: 0.95rem; outline: none; }
input[type=range] { flex-grow: 1; margin: 0 20px; accent-color: var(--text-color); }

/* IG-LIKE SAVED MODE */
body.saved-mode-active #bottom-nav, body.saved-mode-active .bottom-nav, body.saved-mode-active nav { display: none !important; height: 0 !important; opacity: 0 !important; pointer-events: none !important; }
body.saved-mode-active #screen-scroll { padding-bottom: 0 !important; }
#saved-mode-header { position: fixed; top: 0; left: 0; width: 100%; height: 90px; z-index: 9999; display: none; align-items: flex-end; padding: 0 20px 15px 20px; background: linear-gradient(to bottom, rgba(0,0,0,0.9) 0%, rgba(0,0,0,0.6) 60%, transparent 100%); color: #fff; font-size: 1.3rem; font-weight: 600; cursor: pointer; }
body.saved-mode-active #saved-mode-header { display: flex; }

/* TUTORIAL OVERLAY (NOVÝ INTERAKTIVNÍ) */
#interactive-tutorial { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 10000; overflow: hidden; pointer-events: auto; }
#tut-hole { position: absolute; box-shadow: 0 0 0 9999px rgba(0,0,0,0.85); transition: all 0.4s ease-in-out; pointer-events: none; border-radius: 12px; }
#tut-content { position: absolute; left: 5%; width: 90%; color: white; text-align: center; transition: all 0.4s ease-in-out; pointer-events: none; font-size: 1.1rem; font-weight: 600; text-shadow: 0 2px 6px rgba(0,0,0,0.8); }
.tut-hint { margin-top: 20px; font-size: 0.85rem; font-weight: normal; opacity: 0.6; }
`;

document.head.appendChild(style);

function applyTheme() { document.documentElement.setAttribute('data-theme', userSettings.theme); }
applyTheme();

// ==========================================
// 4. MĚŘENÍ ČASU V APLIKACI A TUTORIAL
// ==========================================
setInterval(() => {
    let accMs = parseInt(localStorage.getItem('app_time_ms') || '0');
    accMs += 5000;
    localStorage.setItem('app_time_ms', accMs.toString());
    const hrsEl = document.getElementById('stat-hours');
    if (hrsEl) hrsEl.innerText = (accMs / 3600000).toFixed(1);
}, 5000);

function showTutorial() {
    // Prozatím zakomentováno, aby se tutoriál ukázal pokaždé při zapnutí (pro účely ladění)
    // if (localStorage.getItem('tutorial_seen')) return;

    const overlay = document.createElement('div');
    overlay.id = 'interactive-tutorial';
    
    const hole = document.createElement('div');
    hole.id = 'tut-hole';
    
    const content = document.createElement('div');
    content.id = 'tut-content';
    
    overlay.appendChild(hole);
    overlay.appendChild(content);
    document.body.appendChild(overlay);

    const arrowDown = `<svg style="display:block; margin: 15px auto 0 auto;" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round"><path d="M12 4v16M19 13l-7 7-7-7"/></svg>`;
    const arrowUp = `<svg style="display:block; margin: 0 auto 15px auto;" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round"><path d="M12 20V4M5 11l7-7 7 7"/></svg>`;

    let currentStep = 0;
    
    // Získání tlačítek spodní navigace (předpoklad: 0 = Objevuj, 1 = Feed, 2 = Profil, 3 = Nastavení)
    const navBtns = document.querySelectorAll('.nav-btn');
    
    const steps = [
        // 1. ZÁLOŽKA: OBJEVUJ
        {
            pre: () => { if (navBtns[0]) navBtns[0].click(); },
            selector: ".story-item", 
            msg: "Záložka Objevuj. Kliknutím na tato kolečka filtruješ mapy podle terénu. Dole se následně zobrazí dostupné postupy.",
            delay: 400
        },
        {
            selector: ".nav-btn:nth-child(2)",
            msg: "Zde se přidávají čísla podle toho, kolik typů terénu máš právě vybráno.",
            delay: 100
        },
        // 2. ZÁLOŽKA: FEED (TROJÚHELNÍK)
        {
            pre: () => { if (navBtns[1]) navBtns[1].click(); },
            selector: null,
            msg: "Tohle je hlavní feed. Tahem nahoru a dolů listuješ mezi jednotlivými postupy.",
            delay: 500
        },
        {
            selector: null,
            msg: "Pohybem dvou prstů mapu přiblížíš. Poté s ní můžeš volně posouvat. Během přiblížení nejde scrollovat na další postup.",
            delay: 100
        },
        {
            selector: ".reel:not([style*='display: none']) .reel-actions",
            msg: "Dvojklikem mapu opět oddálíš. Pokud je už oddálená, přidáš dvojklikem 'To se mi líbí'. Postup zde můžeš také uložit (ikonka záložky) nebo sdílet.",
            delay: 100
        },
        {
            selector: ".reel:not([style*='display: none']) .btn-primary",
            msg: "Tlačítko 'Volby' ti zobrazí detaily dostupných variant postupu a jejich porovnání.",
            delay: 100
        },
        // 3. ZÁLOŽKA: PROFIL
        {
            pre: () => { if (navBtns[2]) navBtns[2].click(); },
            selector: "#profile-content-wrapper",
            msg: "Na svém profilu vidíš statistiky a všechny uložené postupy, ke kterým se chceš vrátit.",
            delay: 500
        },
        // 4. ZÁLOŽKA: NASTAVENÍ
        {
            pre: () => { if (navBtns[3]) navBtns[3].click(); },
            selector: ".settings-section", 
            msg: "V nastavení si uprav 'Tempo na cestě'. Aplikace podle toho výrazně zpřesní odhady časů variant přímo pro tebe.",
            delay: 500
        },
        // KONEC
        {
            selector: null,
            msg: "To je vše! Tutoriál je u konce.",
            delay: 100
        }
    ];

    function renderStep() {
        if (currentStep >= steps.length) {
            overlay.remove();
            localStorage.setItem('tutorial_seen', 'true');
            // Po dokončení vrátíme uživatele na první záložku (Objevuj)
            if (navBtns[0]) navBtns[0].click();
            return;
        }

        let step = steps[currentStep];
        
        // Akce před vykreslením (např. přepnutí obrazovky)
        if (step.pre) step.pre();

        setTimeout(() => {
            let el = step.selector ? document.querySelector(step.selector) : null;
            let finalMsg = step.msg;

            if (el && el.getBoundingClientRect().width > 0) {
                let rect = el.getBoundingClientRect();
                let pad = 12;
                
                hole.style.opacity = '1';
                hole.style.width = (rect.width + pad * 2) + 'px';
                hole.style.height = (rect.height + pad * 2) + 'px';
                hole.style.left = (rect.left - pad) + 'px';
                hole.style.top = (rect.top - pad) + 'px';
                hole.style.borderRadius = '16px';

                // Dynamické umístění textu podle toho, kde se nachází zvýrazněný prvek
                if (rect.top > window.innerHeight / 2) {
                    // Prvek je dole, text dáme nad něj
                    content.style.bottom = (window.innerHeight - rect.top + pad + 10) + 'px';
                    content.style.top = 'auto';
                    finalMsg = step.msg + arrowDown;
                } else {
                    // Prvek je nahoře, text dáme pod něj
                    content.style.top = (rect.bottom + pad + 10) + 'px';
                    content.style.bottom = 'auto';
                    finalMsg = arrowUp + step.msg;
                }
            } else {
                // Bez konkrétního prvku vycentrujeme text a skryjeme díru
                hole.style.opacity = '0';
                hole.style.width = '0px'; 
                hole.style.height = '0px';
                hole.style.left = '50%'; 
                hole.style.top = '50%';
                
                content.style.top = '40%';
                content.style.bottom = 'auto';
            }
            
            content.innerHTML = finalMsg + '<div class="tut-hint">Klikni kamkoliv pro pokračování</div>';
            
        }, step.delay || 100);
    }

    // Prokliknutí na další krok
    overlay.addEventListener('click', () => {
        currentStep++;
        renderStep();
    });

    renderStep(); // Spuštění prvního kroku
}

// ==========================================
// 5. INICIALIZACE APLIKACE
// ==========================================
document.addEventListener("DOMContentLoaded", () => {
    try {
        let originalUpdatePosition = L.Draggable.prototype._updatePosition;
        L.Draggable.prototype._updatePosition = function () {
            if (this._element && this._element.classList && this._element.classList.contains('leaflet-map-pane')) {
                let mapDiv = this._element.closest('.map-container');
                if (mapDiv && mapDiv.style.transform) {
                    let match = mapDiv.style.transform.match(/rotate\(([\-\d\.]+)deg\)/);
                    if (match) {
                        let theta = parseFloat(match[1]) * Math.PI / 180;
                        let cos = Math.cos(-theta);
                        let sin = Math.sin(-theta);
                        let dx_screen = this._newPos.x - this._startPos.x;
                        let dy_screen = this._newPos.y - this._startPos.y;
                        let dx_local = dx_screen * cos - dy_screen * sin;
                        let dy_local = dx_screen * sin + dy_screen * cos;
                        this._newPos = new L.Point(this._startPos.x + dx_local, this._startPos.y + dy_local);
                    }
                }
            }
            originalUpdatePosition.call(this);
        };
    } catch (e) {}

    loadData();

    const navButtons = document.querySelectorAll('.nav-btn');
    const screens = document.querySelectorAll('.app-screen');

    navButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const targetId = btn.getAttribute('data-target');
            
            if (targetId === 'screen-scroll' && !document.body.classList.contains('saved-mode-active')) {
                updateExploreBadge(document.getElementById('nav-badge'));
            }

            navButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            screens.forEach(screen => {
                if (screen.id === targetId) {
                    screen.classList.add('active');
                    if (targetId === 'screen-profile') renderProfileSaved();
                    if (targetId === 'screen-settings') renderSettings();
                    
                    // LÉK NA BÍLOU OBRAZOVKU PŘI PŘEPNUTÍ DO FEEDU Z PROFILU
                    if (targetId === 'screen-scroll') {
                        setTimeout(() => {
                            Object.values(mapInstances).forEach(m => {
                                m.invalidateSize();
                                if (m.originalMidX !== undefined) {
                                    m.setView([m.originalMidY, m.originalMidX], m.originalZoom, { animate: false });
                                }
                            });
                            if (activeIndex !== -1) activateReel(activeIndex);
                        }, 50);
                    }
                } else {
                    screen.classList.remove('active');
                }
            });
        });
    });

    let smh = document.createElement('div');
    smh.id = 'saved-mode-header';
    smh.innerHTML = `<svg style="width:28px; height:28px; margin-right:10px; margin-bottom:-2px;" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/></svg> <span id="saved-mode-title">${t('saved')}</span>`;
    smh.onclick = closeSavedFeed;
    document.body.appendChild(smh);

    let startX = 0;
    document.body.addEventListener('touchstart', e => { if (document.body.classList.contains('saved-mode-active')) startX = e.touches[0].clientX; }, {passive: true});
    document.body.addEventListener('touchend', e => { if (document.body.classList.contains('saved-mode-active')) { if (e.changedTouches[0].clientX - startX > 100) closeSavedFeed(); } }, {passive: true});
    setTimeout(updateUITexts, 200);
});

let selectedTerrains = new Set();

function loadData() {
    fetch('postupy/postupy_index.json?v=' + Date.now())
        .then(res => res.json())
        .then(data => {
            postupyData = data;
            postupyData.forEach((map, index) => {
                map.terrain = 'cesky-les';
                map.map_id = 'homolka';    
                map.map_name = 'Homolka';  
                if (!map.id) map.id = index + 1;
            });
            
            buildReels();
            setupObserver();
            renderExploreGrid();
            setupExploreStories();
            renderProfileSaved();
            updateUITexts(); 
            
            setTimeout(() => {
                const loader = document.getElementById('loader');
                if (loader) { loader.style.opacity = 0; setTimeout(() => loader.remove(), 500); }
                showTutorial();
            }, 500);
        })
        .catch(err => console.error("Chyba při načítání dat: ", err));
}

// ==========================================
// 6. NASTAVENÍ (SETTINGS SCREEN)
// ==========================================
function updateSettings(key, value) {
    userSettings[key] = value;
    localStorage.setItem('user_settings', JSON.stringify(userSettings));
    
    if (key === 'theme') applyTheme();
    if (key === 'language' || key === 'pace') {
        let smhTitle = document.getElementById('saved-mode-title');
        if (smhTitle && smhTitle.innerText === i18n[userSettings.language === 'cs' ? 'en' : 'cs'].saved) { smhTitle.innerText = t('saved'); }
        
        renderSettings();
        updateUITexts();
        
        Object.values(mapInstances).forEach(m => m.remove());
        mapInstances = {}; currentLayers = {}; currentOverlays = {}; currentTileLayers = {};
        
        buildReels();
        setupObserver(); 
        renderProfileSaved();
        renderExploreGrid();
    }
}

function renderSettings() {
    let screen = document.getElementById('screen-settings');
    if (!screen) {
        screen = document.createElement('div');
        screen.id = 'screen-settings';
        screen.className = 'app-screen';
        document.body.appendChild(screen);
    }
    
    screen.innerHTML = `
        <div style="padding: 20px 0; padding-bottom: 100px;">
            <h1 style="font-size: 1.5rem; margin: 10px 20px 30px 20px; font-weight: 700;">${t('settings')}</h1>
            
            <div class="settings-section">
                <div class="settings-title">${t('runner')}</div>
                <div class="settings-row">
                    <span style="white-space:nowrap;">${t('paceOnRoad')}</span>
                    <input type="range" id="pace-slider" min="180" max="480" step="5" value="${userSettings.pace}">
                    <span id="pace-value" style="white-space:nowrap; font-weight: 600;">${formatPace(userSettings.pace)}</span>
                </div>
            </div>

            <div class="settings-section">
                <div class="settings-title">${t('application')}</div>
                <div class="settings-row">
                    <span>${t('language')}</span>
                    <select id="lang-select" onchange="updateSettings('language', this.value)">
                        <option value="cs" ${userSettings.language === 'cs' ? 'selected' : ''}>Čeština</option>
                        <option value="en" ${userSettings.language === 'en' ? 'selected' : ''}>English</option>
                    </select>
                </div>
                <div class="settings-row">
                    <span>${t('theme')}</span>
                    <select id="theme-select" onchange="updateSettings('theme', this.value)">
                        <option value="system" ${userSettings.theme === 'system' ? 'selected' : ''}>${t('theme_system')}</option>
                        <option value="light" ${userSettings.theme === 'light' ? 'selected' : ''}>${t('theme_light')}</option>
                        <option value="dark" ${userSettings.theme === 'dark' ? 'selected' : ''}>${t('theme_dark')}</option>
                    </select>
                </div>
                <div class="settings-row">
                    <span>${t('offlineMaps')}</span>
                    <button class="settings-btn" id="offline-sync-btn" onclick="startOfflineSync()">${t('download')}</button>
                </div>
            </div>

            <div class="settings-section">
                <div class="settings-title">${t('maps')}</div>
                <div class="settings-row" style="border:none;">
                    <button class="settings-btn" style="width: 100%; text-align: left;" onclick="clearAppCache()">${t('clearCache')} (<span id="cache-size">0.0 MB</span>)</button>
                </div>
            </div>
        </div>
    `;

    const paceSlider = document.getElementById('pace-slider');
    const paceValue = document.getElementById('pace-value');
    paceSlider.addEventListener('input', (e) => { paceValue.innerText = formatPace(e.target.value); });
    paceSlider.addEventListener('change', (e) => { updateSettings('pace', parseInt(e.target.value)); });
    updateCacheSize();
}

async function updateCacheSize() {
    const span = document.getElementById('cache-size');
    if (!span) return;
    let total = 0;
    if ('caches' in window) {
        try {
            const cacheNames = await caches.keys();
            for (let name of cacheNames) {
                const cache = await caches.open(name);
                const keys = await cache.keys();
                for (let req of keys) {
                    const res = await cache.match(req);
                    if (res) { const blob = await res.blob(); total += blob.size; }
                }
            }
        } catch(e) { console.warn(e); }
    }
    span.innerText = (total / (1024 * 1024)).toFixed(1) + ' MB';
}

async function clearAppCache() {
    if (confirm(t('confirmClear'))) {
        if ('caches' in window) {
            const cacheNames = await caches.keys();
            for (let name of cacheNames) { await caches.delete(name); }
        }
        updateCacheSize();
        alert(t('cacheCleared'));
    }
}

// ==========================================
// 7. VYKRESLENÍ FEEDU A MAPY
// ==========================================
function buildReels() {
    const container = document.getElementById('reels-container');
    if (!container) return;
    container.innerHTML = '';
    
    let saved = JSON.parse(localStorage.getItem('saved_postupy') || '[]');
    let savedIds = saved.map(String);
    
    postupyData.forEach((postup, index) => {
        const reel = document.createElement('div');
        reel.className = 'reel';
        reel.dataset.index = index;
        reel.dataset.terrain = postup.terrain; 

        const isSaved = savedIds.includes(String(postup.id));
        const bookmarkClass = isSaved ? 'action-btn bookmark-btn bookmarked' : 'action-btn bookmark-btn';
        const bookmarkSvg = isSaved 
            ? '<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 012-2h10a2 2 0 012 2z"/></svg>'
            : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 012-2h10a2 2 0 012 2z"/></svg>';

        reel.innerHTML = `
            <div class="map-clip" id="clip-${index}">
                <div class="map-container" id="map-${index}"></div>
                <div class="like-animation-container" id="like-anim-${index}">
                    <svg viewBox="0 0 24 24" fill="currentColor"><path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z"/></svg>
                </div>
            </div>
            <div class="reel-actions">
                <button class="action-btn like-btn" onclick="toggleLike(${index}, this)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z"/></svg></button>
                <button class="${bookmarkClass}" onclick="toggleBookmark(${index}, this)">${bookmarkSvg}</button>
                <button class="action-btn share-btn" onclick="sharePostup(${index})"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg></button>
            </div>
            <div class="reel-ui">
                <div class="reel-header">
                    <div class="reel-subtitle">${postup.dist_m ? postup.dist_m.toFixed(0) : ''} ${t('aerial')}</div>
                    <button class="btn-primary" onclick="toggleVariants(${index})"><svg class="btn-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M4 6h16M4 12h16M4 18h16" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" fill="none"/></svg>${t('options')}</button>
                </div>
            </div>
        `;
        container.appendChild(reel);
    });
}

let reelObserver = null;
let activationTimeout = null;

function setupObserver() {
    if (reelObserver) reelObserver.disconnect();
    const rc = document.getElementById('reels-container');
    if (!rc) return;
    
    // Observer už nespouští zpožděné centrování do zdi.
    let options = { root: rc, rootMargin: '0px', threshold: 0.51 };
    reelObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting && entry.target.style.display !== 'none') {
                const index = parseInt(entry.target.dataset.index);
                if (activationTimeout) clearTimeout(activationTimeout);
                activationTimeout = setTimeout(() => { activateReel(index); }, 150);
            }
        });
    }, options);
    
    document.querySelectorAll('.reel').forEach(reel => reelObserver.observe(reel));
}

let showVariantsForIndex = {};
let isPanelOpen = false;
let activeIndex = -1;

function toggleVariants(index) {
    const panel = document.getElementById('global-variants-panel');
    const content = document.getElementById('global-variants-content');
    if (!panel || !content) return;
    
    if (isPanelOpen) {
        panel.classList.remove('active');
        panel.classList.remove('collapsed');
        isPanelOpen = false;
        showVariantsForIndex[index] = false;
    } else {
        const postup = postupyData[index];
        content.innerHTML = postup.variants.map(v => {
            let adjCasS = getAdjustedTime(v.cas_s);
            let adjTempoS = (adjCasS / v.vzdal_m) * 1000;
            let timeStr = `${Math.floor(adjCasS/60)}:${Math.floor(adjCasS%60).toString().padStart(2,'0')}`;
            let paceStr = `${Math.floor(adjTempoS/60)}:${Math.floor(adjTempoS%60).toString().padStart(2,'0')} min/km`;

            return `
            <div class="variant-item">
                <div class="variant-color" style="background-color: ${v.color}; color: ${v.color}"></div>
                <div class="variant-stats">
                    <div class="variant-main">V${v.id} • ${timeStr}</div>
                    <div class="variant-sub">${v.vzdal_m.toFixed(0)}m • ${v.prevyseni_m.toFixed(0)}m↑<br>${paceStr}</div>
                </div>
            </div>`;
        }).join('');
        
        let panelClass = 'pos-top-right';
        if (geojsonCache[postup.file]) {
            let startC = null, endC = null;
            geojsonCache[postup.file].features.forEach(f => {
                if (f.properties && f.properties.type === 'start') startC = f.geometry.coordinates;
                if (f.properties && f.properties.type === 'end') endC = f.geometry.coordinates;
            });
            if (startC && endC) {
                let dx = endC[0] - startC[0]; let dy = endC[1] - startC[1];
                let dist = Math.sqrt(dx*dx + dy*dy);
                if (dist > 0) {
                    let ux = dx/dist, uy = dy/dist, vx = -uy, vy = ux;
                    let maxLeftTop = 0, maxRightTop = 0, maxLeftBot = 0, maxRightBot = 0;
                    geojsonCache[postup.file].features.forEach(f => {
                        if (f.properties && f.properties.type === 'variant' && f.geometry.type === 'LineString') {
                            f.geometry.coordinates.forEach(c => {
                                let px = c[0] - startC[0], py = c[1] - startC[1];
                                let localY = px * ux + py * uy; 
                                let localX = px * vx + py * vy; 
                                if (localY > dist * 0.6) { 
                                    if (localX > maxLeftTop) maxLeftTop = localX;
                                    if (-localX > maxRightTop) maxRightTop = -localX;
                                } else if (localY < dist * 0.4) { 
                                    if (localX > maxLeftBot) maxLeftBot = localX;
                                    if (-localX > maxRightBot) maxRightBot = -localX;
                                }
                            });
                        }
                    });
                    let bulges = [ { corner: 'pos-top-left', val: maxLeftTop }, { corner: 'pos-top-right', val: maxRightTop }, { corner: 'pos-bottom-left', val: maxLeftBot } ];
                    bulges.sort((a, b) => a.val - b.val);
                    panelClass = bulges[0].corner;
                }
            }
        }
        
        panel.className = 'variants-panel ' + panelClass;
        void panel.offsetWidth; 
        
        const toggleBtn = document.getElementById('global-toggle-btn');
        if (toggleBtn) {
            toggleBtn.innerHTML = '<svg class="toggle-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>';
            toggleBtn.onclick = () => panel.classList.toggle('collapsed');
        }
        
        panel.classList.remove('collapsed'); 
        panel.classList.add('active');
        isPanelOpen = true;
        showVariantsForIndex[index] = true;
    }
    const postup = postupyData[index];
    if (geojsonCache[postup.file]) renderMapData(index, geojsonCache[postup.file]);
}

function activateReel(index) {
    const postup = postupyData[index];
    if (postup) {
        let viewed = JSON.parse(localStorage.getItem('viewed_postupy') || '[]');
        if (!viewed.includes(postup.id)) {
            viewed.push(postup.id);
            localStorage.setItem('viewed_postupy', JSON.stringify(viewed));
        }
    }

    if (activeIndex !== index) {
        // Resetovat zoom předešlé mapy, aby nezůstal viset overflowY='hidden' na kontejneru
        if (activeIndex !== -1 && mapInstances[activeIndex]) {
            let oldMap = mapInstances[activeIndex];
            if (oldMap.getZoom() > oldMap.getMinZoom() + 0.05) {
                if (oldMap.originalMidX !== undefined) {
                    oldMap.setView([oldMap.originalMidY, oldMap.originalMidX], oldMap.originalZoom, { animate: false });
                } else {
                    oldMap.setZoom(oldMap.getMinZoom(), { animate: false });
                }
            }
        }

        if (isPanelOpen) {
            const panel = document.getElementById('global-variants-panel');
            if (panel) { panel.classList.remove('active'); panel.classList.remove('collapsed'); }
            isPanelOpen = false;
            if (activeIndex !== -1) {
                showVariantsForIndex[activeIndex] = false;
                const prevPostup = postupyData[activeIndex];
                if (prevPostup && geojsonCache[prevPostup.file]) {
                    renderMapData(activeIndex, geojsonCache[prevPostup.file]);
                }
            }
        }
        activeIndex = index;
    }
    preloadReel(index);
}

function preloadReel(i) {
    if (i < 0 || i >= postupyData.length) return;
    if (!mapInstances[i]) initMapForReel(i);
    const postup = postupyData[i];
    if (geojsonCache[postup.file]) {
        if (!currentLayers[i]) renderMapData(i, geojsonCache[postup.file]);
    } else {
        fetch('postupy/' + postup.file + '?v=' + Date.now())
            .then(res => res.json())
            .then(geojson => {
                geojsonCache[postup.file] = geojson;
                if (!currentLayers[i]) renderMapData(i, geojson);
            })
            .catch(err => console.warn("GeoJSON load error:", err));
    }
}

const originalSetView = L.GridLayer.prototype._setView;
L.GridLayer.prototype._setView = function (center, zoom, noPrune, noUpdate) {
    let oldRound = Math.round;
    Math.round = function(val) { return (val === zoom) ? Math.ceil(val) : oldRound(val); };
    try { originalSetView.call(this, center, zoom, noPrune, noUpdate); } 
    finally { Math.round = oldRound; }
};

function initMapForReel(index) {
    const mapContainer = document.getElementById(`map-${index}`);
    if (!mapContainer) return;
    const map = L.map(`map-${index}`, {
        crs: L.CRS.Simple, minZoom: 0, maxZoom: 8, zoomSnap: 0,
        zoomControl: false, gestureHandling: false, inertia: false,
        tap: false,
        maxBoundsViscosity: 1.0,
        dragging: false, // Výchozí stav: posouvání zakázáno
        bounceAtZoomLimits: false // Zakáže "gumové" oddalování pod povolený minZoom
    });
    map.createPane('maskPane');
    map.getPane('maskPane').style.zIndex = 250; 
    map.doubleClickZoom.disable();
    
    let mc = map.getContainer();
    
    let lastClickTime = 0;
    map.on('click', function(e) {
        let currentTime = Date.now();
        if (currentTime - lastClickTime < 400) {
            let currentZoom = map.getZoom();
            let minZoom = map.getMinZoom();
            if (currentZoom > minZoom + 0.05) {
                if (map.originalMidX !== undefined && map.originalMidY !== undefined) map.setView([map.originalMidY, map.originalMidX], map.originalZoom || minZoom);
                else map.setZoom(minZoom);
            } else {
                let btn = document.querySelector(`.reel[data-index="${index}"] .like-btn`);
                if (btn && !btn.classList.contains('liked')) toggleLike(index, btn);
                else triggerLikeAnimation(index);
            }
            lastClickTime = 0; 
        } else {
            lastClickTime = currentTime;
        }
    });

    L.control.zoom({ position: 'topleft' }).addTo(map);

    map.on('zoomend', function() {
        updateCalibrationShift();

        const reelsContainer = document.getElementById('reels-container');
        const minZoom = map.getMinZoom();
        
        if (map.getZoom() > minZoom + 0.05) {
            // Přiblíženo - zablokovat scrollování reels a povolit panování
            if (reelsContainer) reelsContainer.style.overflowY = 'hidden';
            mc.classList.add('zoomed-in');
            map.dragging.enable();
        } else {
            // Oddáleno - povolit scrollování reels a zakázat panování
            if (reelsContainer) reelsContainer.style.overflowY = 'scroll';
            mc.classList.remove('zoomed-in');
            map.dragging.disable();
            
            // Pro jistotu vycentrovat, pokud uživatel mapu při oddálení zanechal posunutou
            if (map.originalMidX !== undefined) {
                map.panTo([map.originalMidY, map.originalMidX], { animate: false });
            }
        }
    });

    mapInstances[index] = map;
}


function renderMapData(index, geojsonOriginal) {
    try {
        const map = mapInstances[index];
        if (!map) return;
        
        let isInitialRender = !currentLayers[index];
        
        if (currentLayers[index]) map.removeLayer(currentLayers[index]);
        if (currentOverlays[index]) map.removeLayer(currentOverlays[index]);
        
        let geojson = JSON.parse(JSON.stringify(geojsonOriginal));
        let overlays = L.featureGroup().addTo(map);
        currentOverlays[index] = overlays;
        
        let startCoords = null, endCoords = null;
        let allLngs = [], allLats = [];
        geojson.features.forEach(f => {
            if (f.properties && f.properties.type === 'start') startCoords = f.geometry.coordinates;
            if (f.properties && f.properties.type === 'end') endCoords = f.geometry.coordinates;
            if (f.geometry.type === 'Point') {
                allLngs.push(f.geometry.coordinates[0]); allLats.push(f.geometry.coordinates[1]);
            } else if (f.geometry.type === 'LineString') {
                f.geometry.coordinates.forEach(c => { allLngs.push(c[0]); allLats.push(c[1]); });
            }
        });
        
        if (!currentTileLayers[index] && allLngs.length > 0) {
            let minLng = Math.min(...allLngs), maxLng = Math.max(...allLngs);
            let minLat = Math.min(...allLats), maxLat = Math.max(...allLats);
            
            let spanLng = maxLng - minLng;
            let spanLat = maxLat - minLat;
            let maxSpan = Math.max(spanLng, spanLat, 200); 
            
            // Zvětšená rezerva (45 %), aby rohy zrotované mapy nenarazily do maxBounds limitu
            let marginLng = maxSpan * 0.45;
            let marginLat = maxSpan * 0.45;
            let tileBounds = [[minLat - marginLat, minLng - marginLng], [maxLat + marginLat, maxLng + marginLng]];
            
            map.setMaxBounds(tileBounds);
            let tl = L.tileLayer('tiles/{z}/{x}/{y}.png', {
                tileSize: 512, minZoom: 0, maxZoom: 8, maxNativeZoom: 5,
                noWrap: true, tms: false, keepBuffer: 4, updateWhenIdle: false, updateWhenZooming: true, detectRetina: true
            }).addTo(map);
            currentTileLayers[index] = tl;
        }
        
        let showVariants = showVariantsForIndex[index] || false;
        let layer = L.geoJSON(geojson, {
            filter: function(f) {
                if (f.properties && f.properties.type === 'variant' && !showVariants) return false;
                if (f.properties && ['start', 'end', 'spojnice'].includes(f.properties.type)) return false;
                return true;
            },
            style: function (f) {
                if (f.properties && f.properties.type === 'variant') return { color: f.properties.color, weight: 6, opacity: 0.8, lineCap: 'round', lineJoin: 'round' };
                if (f.properties && f.properties.type === 'spojnice') return { color: iofPurple, weight: 3, opacity: 0.8, lineCap: 'round', lineJoin: 'round' };
            },
        });
        
        if (startCoords && endCoords) {
            let dx = endCoords[0] - startCoords[0], dy = endCoords[1] - startCoords[1];
            let dist = Math.sqrt(dx*dx + dy*dy);
            if (dist > 0) {
                let distM = postupyData[index].dist_m || 0;
                let R = 1.10 + Math.max(0, Math.min(1, (distM - 1600) / 800)) * 0.40; 
                let gap = 0.10;
                let ux = dx / dist, uy = dy / dist;
                let targetBearing = (Math.atan2(dy, dx) * 180 / Math.PI) - 90;
                
                const mContainer = document.getElementById(`map-${index}`);
                if (mContainer) mContainer.style.transform = `rotate(${targetBearing}deg)`;
                
                let lineWeight = Math.max(2, Math.min(3, 2 + dist / 150));
                let lineStart = [startCoords[0] + ux * (R + gap), startCoords[1] + uy * (R + gap)];
                let lineEnd = [endCoords[0] - ux * (R + gap), endCoords[1] - uy * (R + gap)];
                if (dist > R*2 + gap*2) {
                    let polyline = L.polyline([[lineStart[1], lineStart[0]], [lineEnd[1], lineEnd[0]]], 
                        {color: iofPurple, weight: lineWeight, pane: 'markerPane', interactive: false});
                    layer.addLayer(polyline);
                }
                [startCoords, endCoords].forEach((coords, idx) => {
                    let num = idx === 0 ? "1" : "2";
                    layer.addLayer(L.circle([coords[1], coords[0]], { radius: R, color: iofPurple, weight: lineWeight, fill: false, pane: 'markerPane', interactive: false }));
                    
                    let nx = -uy, ny = ux;
                    let textDist = R + 0.90;
                    let cx = coords[0] + nx * textDist, cy = coords[1] + ny * textDist;
                    
                    let svgText = document.createElementNS("http://www.w3.org/2000/svg", "svg");
                    svgText.setAttribute('xmlns', "http://www.w3.org/2000/svg");
                    svgText.setAttribute('viewBox', "0 0 100 100");
                    svgText.setAttribute('preserveAspectRatio', 'none');
                    svgText.innerHTML = `<text x="50" y="80" transform="rotate(${-targetBearing}, 50, 50)" font-family="Arial, sans-serif" font-size="75" font-weight="bold" fill="${iofPurple}" text-anchor="middle">${num}</text>`;
                    let halfSizeText = 1.0;
                    let boundsText = [[cy - halfSizeText, cx - halfSizeText], [cy + halfSizeText, cx + halfSizeText]];
                    overlays.addLayer(L.svgOverlay(svgText, boundsText, {interactive: false, pane: 'markerPane'}));
                });
            }
        }
        
        layer.addTo(map);
        currentLayers[index] = layer;
        
        if (startCoords && endCoords) {
            let w = window.innerWidth, h = window.innerHeight; 
            let dx = endCoords[0] - startCoords[0], dy = endCoords[1] - startCoords[1];
            let dist = Math.sqrt(dx*dx + dy*dy);
            
            let targetPixelsY = h * 0.82; 
            let idealZoom = 0;
            if (dist > 0) idealZoom = Math.log2(targetPixelsY / dist);
            
            let maxZoom = map.getMaxZoom() || 8;
            idealZoom = Math.max(0, Math.min(maxZoom, idealZoom));
            
            let midX = (startCoords[0] + endCoords[0]) / 2, midY = (startCoords[1] + endCoords[1]) / 2;
            map.setMinZoom(idealZoom);
            
            let ux = dx / dist, uy = dy / dist, vx = -uy, vy = ux;
            let maxAbsX = 0;
            
            allLngs.forEach((lng, idx) => {
                let px = lng - midX, py = allLats[idx] - midY;
                let localX = px * vx + py * vy;
                if (Math.abs(localX) > maxAbsX) maxAbsX = Math.abs(localX);
            });
            
            let pixelScale = Math.pow(2, idealZoom); 
            let screenHalfW = (w / 2) / pixelScale, screenHalfH = (h / 2) / pixelScale;
            let routeHalfW = maxAbsX + (50 / pixelScale), routeHalfH = (dist / 2) + (50 / pixelScale);
            
            // Přidání 15% rezervy, aby se maska nedostala do vizuálního pole obrazovky
            let holeHalfW = Math.max(screenHalfW * 1.15, routeHalfW);
            let holeHalfH = Math.max(screenHalfH * 1.15, routeHalfH);
            
            let innerRing = [
                [midY + uy * holeHalfH + vy * holeHalfW, midX + ux * holeHalfH + vx * holeHalfW],
                [midY + uy * holeHalfH - vy * holeHalfW, midX + ux * holeHalfH - vx * holeHalfW],
                [midY - uy * holeHalfH - vy * holeHalfW, midX - ux * holeHalfH - vx * holeHalfW],
                [midY - uy * holeHalfH + vy * holeHalfW, midX - ux * holeHalfH + vx * holeHalfW]
            ];
            let outerRing = [[-50000, -50000], [-50000, 50000], [50000, 50000], [50000, -50000]];
            
            let mask = L.polygon([outerRing, innerRing], { color: 'transparent', fillColor: '#ffffff', fillOpacity: 1.0, interactive: false, pane: 'maskPane' });
            overlays.addLayer(mask);
            
            if (isInitialRender) {
                map.originalMidX = midX; map.originalMidY = midY; map.originalZoom = idealZoom;
                map.setView([midY, midX], idealZoom, { animate: false });
            }
        }
    } catch (e) { console.warn("Silent ignore map render error", e); }
}

let calibMode = false;
let calibX = 400;
let calibY = -300;

document.addEventListener('keydown', (e) => {
    if (e.key.toLowerCase() === 'k') {
        calibMode = !calibMode;
        let ui = document.getElementById('calibration-ui');
        if(ui) ui.style.display = calibMode ? 'block' : 'none';
        if (calibMode) updateCalibrationShift();
        return;
    }
    if (!calibMode) return;
    if (e.key === 'ArrowLeft') calibX -= 1;
    else if (e.key === 'ArrowRight') calibX += 1;
    else if (e.key === 'ArrowUp') calibY -= 1;
    else if (e.key === 'ArrowDown') calibY += 1;
    else return;
    e.preventDefault();
    let xspan = document.getElementById('calib-x');
    let yspan = document.getElementById('calib-y');
    if (xspan) xspan.innerText = calibX;
    if (yspan) yspan.innerText = calibY;
    updateCalibrationShift();
});

function updateCalibrationShift() {
    if (typeof activeIndex === 'undefined') return;
    let map = mapInstances[activeIndex];
    if (!map) return;
    let pane = map.getPane('markerPane');
    if (!pane) return;
    let shiftXConfig = calibX - 400;
    let shiftYConfig = calibY - (-300);
    let scale = Math.pow(2, map.getZoom()) / 64;
    pane.style.marginLeft = (shiftXConfig * scale) + 'px';
    pane.style.marginTop = (shiftYConfig * scale) + 'px';
}

async function startOfflineSync() {
    let btn = document.getElementById('offline-sync-btn');
    if (btn) btn.disabled = true;
    let progressOverlay = document.getElementById('sync-progress');
    let bar = document.getElementById('sync-bar');
    let text = document.getElementById('sync-text');
    if (progressOverlay) progressOverlay.style.display = 'flex';
    
    try {
        let urlsToFetch = ['postupy/postupy_index.json'];
        postupyData.forEach(p => urlsToFetch.push('postupy/' + p.file));
        text.innerText = "Získávám index dlaždic...";
        let tilesResponse = await fetch('tiles_index.json?v=' + Date.now());
        if (tilesResponse.ok) {
            let tiles = await tilesResponse.json();
            urlsToFetch = urlsToFetch.concat(tiles);
        }
        
        let total = urlsToFetch.length;
        let done = 0;
        const chunkSize = 20;
        for (let i = 0; i < total; i += chunkSize) {
            let chunk = urlsToFetch.slice(i, i + chunkSize);
            await Promise.all(chunk.map(async (url) => {
                try { await fetch(url, { cache: 'no-store' }); } catch(e) {}
                done++;
            }));
            if (bar) bar.style.width = Math.floor((done / total) * 100) + '%';
            if (text) text.innerText = `${done} / ${total}`;
        }
        
        setTimeout(() => {
            if (progressOverlay) progressOverlay.style.display = 'none';
            if (btn) {
                btn.innerHTML = t('download');
                btn.disabled = false;
            }
            updateCacheSize();
        }, 500);
    } catch (err) {
        alert("Chyba při stahování: " + err.message);
        if (progressOverlay) progressOverlay.style.display = 'none';
    }
}

function triggerLikeAnimation(index) {
    let anim = document.getElementById(`like-anim-${index}`);
    if (anim) {
        anim.classList.remove('active');
        void anim.offsetWidth; 
        anim.classList.add('active');
    }
}

function toggleLike(index, btn) {
    btn.classList.toggle('liked');
    if (btn.classList.contains('liked')) {
        btn.innerHTML = '<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1.5"><path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z" stroke-linecap="round" stroke-linejoin="round"/></svg>';
        triggerLikeAnimation(index);
    } else {
        btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z"/></svg>';
    }
}

function toggleBookmark(index, btn) {
    btn.classList.toggle('bookmarked');
    const postup = postupyData[index];
    if (!postup) return;
    const mapId = String(postup.id || (index + 1));
    let saved = JSON.parse(localStorage.getItem('saved_postupy') || '[]');
    let savedStrings = saved.map(String);
    
    if (btn.classList.contains('bookmarked')) {
        btn.innerHTML = '<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 012-2h10a2 2 0 012 2z"/></svg>';
        if (!savedStrings.includes(mapId)) saved.push(postup.id || (index + 1));
    } else {
        btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 012-2h10a2 2 0 012 2z"/></svg>';
        saved = saved.filter(id => String(id) !== mapId);
    }
    localStorage.setItem('saved_postupy', JSON.stringify(saved));
    
    if (document.body.classList.contains('saved-mode-active') && !btn.classList.contains('bookmarked')) {
        const reel = document.querySelector(`.reel[data-index="${index}"]`);
        if (reel) reel.style.display = 'none';
    }
    
    renderProfileSaved();
}

function sharePostup(index) {
    if (navigator.share) navigator.share({ title: 'Zajímavý postup!', url: window.location.href }).catch(err => console.log(err));
    else alert("Odkaz zkopírován do schránky.");
}

function groupRoutesByMap(routesArray) {
    const mapGroups = new Map();
    routesArray.forEach(route => {
        if (!mapGroups.has(route.map_id)) {
            mapGroups.set(route.map_id, {
                map_id: route.map_id, map_name: route.map_name, terrain: route.terrain, routes: [], thumbRoute: route
            });
        }
        mapGroups.get(route.map_id).routes.push(route);
    });
    return Array.from(mapGroups.values());
}

function renderProfileSaved() {
    const profileScreen = document.getElementById('screen-profile');
    if (!profileScreen) return;
    
    profileScreen.innerHTML = '';
    
    let profileContent = document.createElement('div');
    profileContent.id = 'profile-content-wrapper';
    profileContent.style.paddingBottom = '80px'; 
    profileScreen.appendChild(profileContent);
    
    let saved = JSON.parse(localStorage.getItem('saved_postupy') || '[]');
    let viewed = JSON.parse(localStorage.getItem('viewed_postupy') || '[]');
    let accMs = parseInt(localStorage.getItem('app_time_ms') || '0');
    
    let ulozenaCislo = saved.length;
    let videnoCislo = viewed.length;
    let hodinCislo = (accMs / 3600000).toFixed(1);

    let savedPic = localStorage.getItem('profile_picture');
    let avatarContent = savedPic 
        ? `<img src="${savedPic}" style="width:100%; height:100%; object-fit:cover;">`
        : `<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#888" stroke-width="1.5"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>`;

    let oldUpload = document.getElementById('profile-pic-upload');
    if (oldUpload) oldUpload.remove();
    let fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.id = 'profile-pic-upload';
    fileInput.accept = 'image/*';
    fileInput.style.display = 'none';
    fileInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = function(event) {
                localStorage.setItem('profile_picture', event.target.result);
                renderProfileSaved();
            };
            reader.readAsDataURL(file);
        }
    });
    document.body.appendChild(fileInput);

    profileContent.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; padding: 15px 20px 5px 20px; color: inherit;">
            <div style="font-size: 1.4rem; font-weight: 700; display:flex; align-items:center; gap: 5px;">
                <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2" fill="none"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0110 0v4"></path></svg>
                franta14_
            </div>
        </div>

        <div style="display:flex; padding: 15px 20px; align-items:center;">
            <div onclick="document.getElementById('profile-pic-upload').click()" style="width: 80px; height: 80px; border-radius: 50%; background: var(--secondary-bg); overflow:hidden; flex-shrink: 0; border: 1px solid var(--border-color); display:flex; align-items:center; justify-content:center; cursor: pointer;">
                ${avatarContent}
            </div>
            <div style="display:flex; flex-grow: 1; justify-content: space-evenly; text-align:center;">
                <div>
                    <div style="font-weight:700; font-size:1.1rem; color: inherit;">${videnoCislo}</div>
                    <div style="font-size:0.8rem; opacity: 0.7;">${t('analyzed')}</div>
                </div>
                <div>
                    <div style="font-weight:700; font-size:1.1rem; color: inherit;">${ulozenaCislo}</div>
                    <div style="font-size:0.8rem; opacity: 0.7;">${t('saved')}</div>
                </div>
                <div>
                    <div id="stat-hours" style="font-weight:700; font-size:1.1rem; color: inherit;">${hodinCislo}</div>
                    <div style="font-size:0.8rem; opacity: 0.7;">${t('hours')}</div>
                </div>
            </div>
        </div>
        
        <div style="padding: 0 20px 15px 20px; font-size: 0.95rem; color: inherit;">
            <div style="font-weight: 700; margin-bottom:3px;">František Čtrnáct</div>
            <div style="opacity: 0.8;">${t('bioDesc')}</div>
        </div>
        <div id="profile-dynamic-content"></div>
    `;
    
    let dynamicContent = document.getElementById('profile-dynamic-content');
    let savedIds = saved.map(String);
    if (savedIds.length === 0) {
        dynamicContent.innerHTML = `
            <div style="text-align:center; padding: 4rem 1.5rem; color: #888; font-size: 0.95rem;">
                <svg style="width: 42px; height: 42px; margin-bottom: 10px; stroke: #666;" viewBox="0 0 24 24" fill="none" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 012-2h10a2 2 0 012 2z"/></svg>
                <div style="font-weight: 600; opacity: 0.7; margin-bottom: 4px;">${t('noSaved')}</div>
                <div style="font-size: 0.8rem;">${t('noSavedDesc')}</div>
            </div>`;
        return;
    }
    
    const savedData = postupyData.filter(map => savedIds.includes(String(map.id)));
    const uniqueTerrains = [...new Set(savedData.map(map => map.terrain))];
    if (profileSelectedTerrain !== 'Vše' && !uniqueTerrains.includes(profileSelectedTerrain)) profileSelectedTerrain = 'Vše';
    
    const pillsContainer = document.createElement('div');
    pillsContainer.className = 'profile-pills-container';
    pillsContainer.style.display = 'flex';
    pillsContainer.style.overflowX = 'auto';
    pillsContainer.style.gap = '8px';
    pillsContainer.style.padding = '5px 15px 15px 15px';
    
    const createPill = (terrainName, label) => {
        const pill = document.createElement('button');
        pill.className = 'ig-pill' + (profileSelectedTerrain === terrainName ? ' active' : '');
        pill.innerText = label;
        pill.onclick = () => { profileSelectedTerrain = terrainName; renderProfileSaved(); };
        return pill;
    };

    pillsContainer.appendChild(createPill('Vše', t('all')));
    uniqueTerrains.forEach(t => {
        const niceName = t.charAt(0).toUpperCase() + t.slice(1).replace('-', ' ');
        pillsContainer.appendChild(createPill(t, niceName));
    });
    dynamicContent.appendChild(pillsContainer);
    
    const gridContainer = document.createElement('div');
    gridContainer.style.display = 'grid';
    gridContainer.style.gridTemplateColumns = 'repeat(3, 1fr)';
    gridContainer.style.gap = '2px';
    gridContainer.style.width = '100%';
    
    const displayData = profileSelectedTerrain === 'Vše' ? savedData : savedData.filter(map => map.terrain === profileSelectedTerrain);
    const groups = groupRoutesByMap(displayData);
    
    groups.forEach((group) => {
        let fileName = group.thumbRoute.file.replace('.json', '.png').replace('.geojson', '.png');
        const thumbUrl = 'postupy/' + fileName;
        
        const el = document.createElement('div');
        el.className = 'explore-grid-item';
        el.style.position = 'relative';
        el.style.aspectRatio = '1 / 1';
        el.style.background = 'var(--secondary-bg)';
        el.style.overflow = 'hidden';
        el.style.cursor = 'pointer';
        
        const countText = getRoutesCountText(group.routes.length);
        
        el.innerHTML = `
            <div style="width:100%; height:100%; background-image: url('${thumbUrl}'); background-size: cover; background-position: center;"></div>
            <div style="position:absolute; bottom:0; left:0; width:100%; background:linear-gradient(to top, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.3) 70%, transparent 100%); color:#fff; font-size:13px; padding:12px 8px 8px 8px; box-sizing:border-box;">
                <div style="font-weight:700; text-shadow: 1px 1px 2px rgba(0,0,0,0.8);">${group.map_name}</div>
                <div style="font-size:10px; font-weight:600; color:#ddd; margin-top:2px;">${countText}</div>
            </div>
        `;
        el.addEventListener('click', () => openFeed(group.map_id, true));
        gridContainer.appendChild(el);
    });
    dynamicContent.appendChild(gridContainer);
}

function openFeed(map_id, isSavedMode) {
    let saved = JSON.parse(localStorage.getItem('saved_postupy') || '[]');
    let savedStrings = saved.map(String);
    
    let firstVisibleIndex = -1;
    let groupName = postupyData.find(m => m.map_id === map_id)?.map_name || t('saved');

    if (isSavedMode) {
        document.body.classList.add('saved-mode-active');
        const header = document.getElementById('saved-mode-header');
        if (header) {
            header.innerHTML = `<svg style="width:28px; height:28px; margin-right:10px; margin-bottom:-2px;" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/></svg> <span id="saved-mode-title">${groupName}</span>`;
        }
    } else {
        document.body.classList.remove('saved-mode-active');
    }

    document.querySelectorAll('.reel').forEach(reel => {
        let mIndex = reel.dataset.index;
        let postup = postupyData[mIndex];
        
        let isMatch = (postup.map_id === map_id);
        if (isSavedMode) {
            isMatch = isMatch && savedStrings.includes(String(postup.id));
        }

        if (isMatch) {
            reel.style.display = 'block';
            if (firstVisibleIndex === -1) firstVisibleIndex = mIndex;
        } else {
            reel.style.display = 'none';
        }
    });

    if (firstVisibleIndex === -1) return;

    document.querySelectorAll('.app-screen').forEach(s => s.classList.remove('active'));
    const scrollNavBtn = document.querySelector('.nav-btn[data-target="screen-scroll"]');
    if (scrollNavBtn) {
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        scrollNavBtn.classList.add('active');
    }
    document.getElementById('screen-scroll').classList.add('active');

    const reelsContainer = document.getElementById('reels-container');
    const targetReel = document.querySelector(`.reel[data-index="${firstVisibleIndex}"]`);
    if (targetReel && reelsContainer) {
        setTimeout(() => {
            reelsContainer.scrollTo({ top: targetReel.offsetTop, behavior: 'instant' });
            
            // Masivní re-kalkulace všech map po otevření Feed zóny z Profilu
            Object.values(mapInstances).forEach(m => {
                m.invalidateSize();
                if (m.originalMidX !== undefined) {
                    m.setView([m.originalMidY, m.originalMidX], m.originalZoom, { animate: false });
                }
            });
            activateReel(firstVisibleIndex);
        }, 50); 
    }
}

function closeSavedFeed() {
    document.body.classList.remove('saved-mode-active');
    updateExploreBadge(document.getElementById('nav-badge'));

    document.querySelectorAll('.app-screen').forEach(s => s.classList.remove('active'));
    document.getElementById('screen-profile').classList.add('active');
}

let appState = { selectedTerrains: ['*'] };

function setupExploreStories() {
    const stories = document.querySelectorAll('.story-item');
    const navBadge = document.getElementById('nav-badge');
    stories.forEach(story => {
        story.addEventListener('click', () => {
            const terrain = story.getAttribute('data-terrain');
            const ring = story.querySelector('.story-ring');
            if (selectedTerrains.has(terrain)) {
                selectedTerrains.delete(terrain);
                if (ring) ring.classList.remove('active-story');
            } else {
                selectedTerrains.add(terrain);
                if (ring) ring.classList.add('active-story');
            }
            updateExploreBadge(navBadge);
            renderExploreGrid(); 
        });
    });
}

function updateExploreBadge(badgeEl) {
    if (selectedTerrains.size > 0) {
        if (badgeEl) { badgeEl.innerText = selectedTerrains.size; badgeEl.style.display = 'flex'; }
        appState.selectedTerrains = Array.from(selectedTerrains);
    } else {
        if (badgeEl) badgeEl.style.display = 'none';
        appState.selectedTerrains = ['*'];
    }
    
    document.querySelectorAll('.reel').forEach(reel => {
        if (selectedTerrains.size === 0) {
            reel.style.display = 'block'; 
        } else {
            const t = reel.getAttribute('data-terrain');
            reel.style.display = selectedTerrains.has(t) ? 'block' : 'none';
        }
    });
}

function renderExploreGrid() {
    const container = document.getElementById('explore-grid-container');
    if (!container) return;
    container.innerHTML = '';
    
    let displayData = postupyData;
    if (selectedTerrains.size > 0) displayData = postupyData.filter(map => selectedTerrains.has(map.terrain));
    
    const groups = groupRoutesByMap(displayData);
    const localMapThumbs = ["tiles/3/1/2.png", "tiles/3/2/2.png", "tiles/3/1/3.png", "tiles/3/2/3.png"];
    
    groups.forEach((group) => {
        let hash = 0;
        for(let i=0; i<group.map_id.length; i++) hash += group.map_id.charCodeAt(i);
        const thumbUrl = localMapThumbs[hash % localMapThumbs.length];
        
        const el = document.createElement('div');
        el.className = 'explore-grid-item'; 
        el.style.aspectRatio = '1 / 1';
        el.style.overflow = 'hidden';
        el.style.cursor = 'pointer';
        el.style.position = 'relative';
        
        const countText = getRoutesCountText(group.routes.length);
        
        el.innerHTML = `
            <div class="grid-img" style="background-image: url('${thumbUrl}'); background-size: cover; background-position: center; width: 100%; height: 100%;"></div>
            <div style="position:absolute; bottom:0; left:0; width:100%; background:linear-gradient(to top, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.3) 70%, transparent 100%); color:#fff; font-size:13px; padding:12px 8px 8px 8px; box-sizing:border-box;">
                <div style="font-weight:700; text-shadow: 1px 1px 2px rgba(0,0,0,0.8);">${group.map_name}</div>
                <div style="font-size:10px; font-weight:600; color:#ddd; margin-top:2px;">${countText}</div>
            </div>
        `;
        el.addEventListener('click', () => openFeed(group.map_id, false));
        container.appendChild(el);
    });
}
