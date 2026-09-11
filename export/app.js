// ==========================================
// KONFIGURACE ANIMACÍ (Upravte si libovolně!)
// ==========================================
window.ANIMATION_CONFIG = {
    // POSUV KAMERY U POSTUPŮ (v procentech, např. 5, 10, -5).
    // Posouvá kameru podélně ve směru osy. Kladné číslo (např. 15) u osy Y znamená,
    // že kamera ukrojí zbytečné místo ZA kolečkem a obrazovka začne "více vepředu"
    // ve směru běhu postupu. Aplikuje se na všechny postupy chytře podle jejich směru.
    routeOffsetX: 0,
    routeOffsetY: 15,

    // VOLITELNÝ MANUÁLNÍ POSUV KAMERY NA ÚVODNÍ STRÁNCE (Explore grid)
    // Pokud zde mapa není uvedena, použije se automatický inteligentní výpočet z metadat (vyhýbá se bílým okrajům)
    exploreMaps: {
        // 'homolka': { startX: -60, startY: -34, midX: -65, midY: -35.6, endX: -68, endY: -38.8 }
    }
};

// ==========================================
// 0. FIREBASE INICIALIZACE A PŘIHLÁŠENÍ
// ==========================================
const firebaseConfig = {
    apiKey: "AIzaSyBDlLvcLPqZ3iyy8ugDqHH-KJZa_t0tvgM",
    authDomain: "scrollienteering.firebaseapp.com",
    projectId: "scrollienteering",
    storageBucket: "scrollienteering.firebasestorage.app",
    messagingSenderId: "1062555766603",
    appId: "1:1062555766603:web:be09e089f80bfef04fa2ce",
    measurementId: "G-YE6PPNFZ54"
};

// Inicializace Firebase
firebase.initializeApp(firebaseConfig);
const auth = firebase.auth();
const db = firebase.firestore();

let currentUser = null;

// Dynamické vytvoření přihlašovací obrazovky (Unified White Splash & Login Overlay)
const loginOverlay = document.createElement('div');
loginOverlay.id = 'login-overlay';
loginOverlay.innerHTML = `
    <div class="splash-logo-container" style="margin-bottom: 5vh; transition: margin 0.5s ease;">
        <svg viewBox="0 0 350 150" class="splash-svg" xmlns="http://www.w3.org/2000/svg" style="width: 100%; max-width: 320px; overflow: visible;">
            <defs>
                <linearGradient id="diagonal-split" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="50%" stop-color="#ffffff" />
                    <stop offset="50%" stop-color="#f7931e" />
                </linearGradient>
                <clipPath id="reveal-clip">
                    <rect id="clip-rect" x="40" y="0" width="0" height="150" />
                </clipPath>
            </defs>
            <text x="40" y="110" font-family="'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-weight="500" font-size="95" fill="#000" letter-spacing="-2" clip-path="url(#reveal-clip)">REEL</text>
            <circle class="circle-o" cx="295" cy="72.5" r="30" fill="url(#diagonal-split)" stroke="#000000" stroke-width="9" />
        </svg>
    </div>
    <div id="splash-login-container" style="text-align: center; padding: 20px; opacity: 0; pointer-events: none; transition: opacity 0.5s ease-in-out;">
        <p style="color: #737373; margin-bottom: 30px; font-size: 1.1rem; font-weight: 500;">Prohlížej, analyzuj a sdílej postupy.</p>
        <button id="google-login-btn" class="tut-allow-interaction" style="background: #ffffff; color: #000000; border: 1px solid #dbdbdb; padding: 12px 24px; border-radius: 25px; font-weight: bold; font-size: 1.1rem; cursor: pointer; display: flex; align-items: center; gap: 10px; margin: 0 auto; box-shadow: 0 2px 10px rgba(0,0,0,0.05); transition: transform 0.15s ease;">
            <svg width="24" height="24" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
            Přihlásit se přes Google
        </button>
        <div style="margin-top: 20px;">
            <button id="guest-login-btn" style="background: transparent; color: #555555; border: 1px solid #dbdbdb; padding: 8px 20px; border-radius: 20px; font-size: 0.9rem; cursor: pointer; transition: background 0.15s;">Pokračovat bez přihlášení</button>
        </div>
    </div>
`;
document.body.appendChild(loginOverlay);

const bypassGuestLogin = () => {
    currentUser = { uid: 'guest', displayName: 'franta14_', photoURL: '' };
    loginOverlay.style.opacity = '0';
    setTimeout(() => loginOverlay.style.display = 'none', 500);
    if (typeof renderProfileSaved === "function") renderProfileSaved();
};

const guestBtn = document.getElementById('guest-login-btn');
if (guestBtn) guestBtn.addEventListener('click', bypassGuestLogin);

// Návrat k Popup metodě
document.getElementById('google-login-btn').addEventListener('click', () => {
    const provider = new firebase.auth.GoogleAuthProvider();
    auth.signInWithPopup(provider).catch(err => {
        alert("Chyba: " + err.message);
    });
});

// Sledování stavu
auth.onAuthStateChanged(async (user) => {
    if (user) {
        currentUser = user;

        // Pokud je přihlášený, ujistíme se, že nepoužíváme .show-login (logo zůstane uprostřed)
        loginOverlay.classList.remove('show-login');

        // Plynulé skrytí splash/login screenu až po dokončení 2s úvodní animace
        const elapsed = Date.now() - (window.splashStartTime || Date.now());
        const remaining = Math.max(0, 2200 - elapsed);

        setTimeout(() => {
            loginOverlay.style.opacity = '0';
            setTimeout(() => loginOverlay.style.display = 'none', 500);
        }, remaining);

        try {
            // Zápis do databáze
            const userRef = db.collection('users').doc(user.uid);
            const doc = await userRef.get();

            if (!doc.exists) {
                let localSaved = JSON.parse(localStorage.getItem('saved_postupy') || '[]');
                await userRef.set({
                    name: user.displayName,
                    email: user.email,
                    photo: user.photoURL,
                    saved_routes: localSaved,
                    created_at: firebase.firestore.FieldValue.serverTimestamp()
                });
            }

            localStorage.setItem('profile_picture', user.photoURL);
            if (typeof renderProfileSaved === "function") renderProfileSaved();
        } catch (e) {
            console.error("Chyba při komunikaci s databází:", e);
        }

    } else {
        currentUser = null;
        loginOverlay.style.display = 'flex';
        loginOverlay.style.opacity = '1';

        // Plynulý posuv loga nahoru a zobrazení přihlašovacích tlačítek (2s)
        const elapsed = Date.now() - (window.splashStartTime || Date.now());
        const remaining = Math.max(0, 2000 - elapsed);

        setTimeout(() => {
            // Přidáme třídu pro plynulý posun loga z prostředka na horní pozici
            loginOverlay.classList.add('show-login');

            const loginBox = document.getElementById('splash-login-container');
            if (loginBox) {
                loginBox.style.opacity = '1';
                loginBox.style.pointerEvents = 'auto';
            }
        }, remaining);
    }
});

let currentCommentsUnsubscribe = null;
let currentChatUnsubscribe = null;

document.addEventListener('click', async (e) => {
    const sendCommentBtn = e.target.closest('#send-comment-btn');
    if (sendCommentBtn) {
        if (!currentUser) { alert("Musíš být přihlášený!"); return; }
        const input = document.getElementById('new-comment-input');
        const text = input.value.trim();
        if (!text) return;
        const routeId = document.getElementById('comments-panel').getAttribute('data-current-route');
        input.value = '';
        await db.collection('comments').add({
            routeId: routeId, text: text, authorUid: currentUser.uid,
            authorName: currentUser.displayName, authorPhoto: currentUser.photoURL || 'https://i.pravatar.cc/100?img=1',
            timestamp: firebase.firestore.FieldValue.serverTimestamp()
        });
    }

    const sendChatBtn = e.target.closest('#send-chat-btn');
    if (sendChatBtn) {
        if (!currentUser) { alert("Musíš být přihlášený!"); return; }
        const input = document.getElementById('new-chat-input');
        const text = input.value.trim();
        if (!text) return;
        input.value = '';
        await db.collection('global_chat').add({
            text: text, authorUid: currentUser.uid, authorName: currentUser.displayName,
            timestamp: firebase.firestore.FieldValue.serverTimestamp()
        });
    }
});

document.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        if (e.target.id === 'new-comment-input') document.getElementById('send-comment-btn').click();
        if (e.target.id === 'new-chat-input') document.getElementById('send-chat-btn').click();
    }
});


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
    --bg-color: #ffffff; --text-color: #000000; --secondary-bg: #fafafa; --border-color: #dbdbdb;
    --pill-bg: #efefef; --pill-text: #000; --pill-active-bg: #000; --pill-active-text: #fff;
    --accent: #0095f6; --nav-icon-color: #000000; --search-bg: #efefef;
    --nav-bg: #ffffff; --nav-border: rgba(0, 0, 0, 0.1);
}
:root[data-theme="dark"] {
    --bg-color: #000000; --text-color: #ffffff; --secondary-bg: #121212; --border-color: #262626;
    --pill-bg: #262626; --pill-text: #fff; --pill-active-bg: #fff; --pill-active-text: #000;
    --nav-icon-color: #ffffff; --search-bg: #262626;
    --nav-bg: #000000; --nav-border: rgba(255, 255, 255, 0.1);
}
@media (prefers-color-scheme: dark) {
    :root[data-theme="system"] {
        --bg-color: #000000; --text-color: #ffffff; --secondary-bg: #121212; --border-color: #262626;
        --pill-bg: #262626; --pill-text: #fff; --pill-active-bg: #fff; --pill-active-text: #000;
        --nav-icon-color: #ffffff; --search-bg: #262626;
        --nav-bg: #000000; --nav-border: rgba(255, 255, 255, 0.1);
    }
}

html, body { margin: 0; padding: 0; width: 100%; height: 100%; background-color: var(--bg-color) !important; color: var(--text-color) !important; overflow: hidden; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 14px; }

/* SCROLLOVÁNÍ NA IPHONECH */
#screen-scroll { position: absolute; top: 0; left: 0; right: 0; bottom: 0; height: 100dvh !important; overflow: hidden; }
#reels-container { position: absolute; top: 0; left: 0; right: 0; bottom: 0; height: 100dvh !important; overflow-y: scroll; scroll-snap-type: y mandatory; -webkit-overflow-scrolling: touch; overscroll-behavior-y: none; }
.reel { height: 100dvh !important; width: 100%; scroll-snap-align: start; scroll-snap-stop: always; position: relative; }

/* DŮLEŽITÉ: Touch akce povoluje scrollování a pinch zoom v mapě */
.leaflet-container { touch-action: pan-y pinch-zoom !important; }
.leaflet-container.zoomed-in { touch-action: none !important; }

/* SPODNÍ LIŠTA – čistá, jednoduchá jako IG */
#bottom-nav { 
    background: var(--nav-bg) !important; 
    border-top: 0.5px solid var(--nav-border) !important; 
    display: flex; justify-content: space-around; align-items: center;
    transition: background 0.3s ease, border-color 0.3s ease;
}
#bottom-nav.nav-dark { 
    background: rgba(0, 0, 0, 0.95) !important; 
    border-top-color: rgba(255, 255, 255, 0.08) !important; 
}
#bottom-nav.nav-dark .nav-btn { color: rgba(255, 255, 255, 0.5) !important; }
#bottom-nav.nav-dark .nav-btn.active { color: #ffffff !important; }
.nav-btn { color: var(--nav-icon-color) !important; opacity: 0.4 !important; background: transparent; border: none; padding: 8px; cursor: pointer; flex: 1; text-align: center; -webkit-tap-highlight-color: transparent; }
.nav-btn.active { color: var(--nav-icon-color) !important; opacity: 1 !important; }

/* STORIES A HLEDÁNÍ */
.story-item, .story-item span, .story-item div { color: var(--text-color) !important; }

/* PILLS A NASTAVENÍ */
.profile-pills-container::-webkit-scrollbar { display: none; }
.profile-pills-container { -ms-overflow-style: none; scrollbar-width: none; }
.ig-pill { padding: 7px 16px; border-radius: 8px; border: 1px solid var(--border-color); background: var(--pill-bg); color: var(--pill-text); font-weight: 600; font-size: 13px; cursor: pointer; white-space: nowrap; font-family: inherit; }
.ig-pill.active { background: var(--pill-active-bg); color: var(--pill-active-text); border-color: var(--pill-active-bg); }
.settings-section { margin-bottom: 0; box-sizing: border-box; width: 100%; }
input[type=range] { flex-grow: 1; margin: 0 14px; accent-color: var(--text-color); }
#screen-settings, #screen-chat { box-sizing: border-box; overflow-x: hidden; width: 100%; height: 100dvh; padding-bottom: 80px; overflow-y: auto; display: none; }
#screen-settings.active, #screen-chat.active { display: block; }

/* IG-LIKE SAVED MODE */
body.saved-mode-active .map-clip { height: 100% !important; }
#saved-mode-header { position: absolute; top: 0; left: 0; width: 100%; height: 70px; z-index: 9999; display: none; align-items: flex-end; padding: 0 20px 15px 20px; background: linear-gradient(to bottom, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0.2) 60%, transparent 100%); color: #fff; text-shadow: 0 1px 3px rgba(0,0,0,0.8); font-size: 1.1rem; font-weight: 600; cursor: pointer; box-sizing: border-box; pointer-events: auto; user-select: none; -webkit-user-select: none; }
body.saved-mode-active #saved-mode-header { display: flex; }

/* IG SETTINGS STYLES */
.ig-settings-content { padding: 0; display: flex; flex-direction: column; }
.ig-settings-search { margin: 12px 16px; display: flex; align-items: center; gap: 8px; background: var(--search-bg); border-radius: 10px; padding: 8px 12px; }
.ig-settings-search svg { width: 16px; height: 16px; color: var(--text-secondary); flex-shrink: 0; }
.ig-settings-search input { flex: 1; border: none; background: transparent; outline: none; font-size: 15px; font-family: inherit; color: var(--text-color); }
.ig-settings-search input::placeholder { color: var(--text-secondary); }
.ig-settings-section-title { padding: 16px 16px 8px; font-size: 13px; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.5px; }
.ig-setting-row { display: flex; align-items: center; padding: 14px 16px; cursor: pointer; gap: 14px; background: var(--bg-color); transition: background 0.2s; }
.ig-setting-row:active { background: var(--secondary-bg); }
.ig-setting-icon { width: 24px; height: 24px; flex-shrink: 0; color: var(--text-color); }
.ig-setting-text { flex: 1; display: flex; flex-direction: column; }
.ig-setting-label { font-size: 15px; font-weight: 400; color: var(--text-color); }
.ig-setting-val { font-size: 15px; color: var(--text-secondary); }
.ig-setting-chevron { width: 20px; height: 20px; color: var(--text-secondary); opacity: 0.5; }
.ig-modal-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100dvh; background: rgba(0,0,0,0.5); z-index: 20000; display: flex; align-items: center; justify-content: center; opacity: 0; pointer-events: none; transition: opacity 0.3s; }
.ig-modal-overlay.active { opacity: 1; pointer-events: auto; }
.ig-modal-content { background: var(--bg-color); border-radius: 16px; width: 85%; max-width: 340px; overflow: hidden; display: flex; flex-direction: column; box-shadow: 0 10px 30px rgba(0,0,0,0.3); transform: scale(0.95); transition: transform 0.3s cubic-bezier(0.2, 0.9, 0.3, 1); }
.ig-modal-overlay.active .ig-modal-content { transform: scale(1); }
.ig-modal-header { padding: 16px; text-align: center; border-bottom: 0.5px solid var(--border-color); font-weight: 600; font-size: 16px; }
.ig-modal-body { padding: 20px; }
.ig-modal-footer { display: flex; border-top: 0.5px solid var(--border-color); }
.ig-modal-btn { flex: 1; padding: 14px; background: transparent; border: none; font-size: 15px; font-weight: 600; cursor: pointer; font-family: inherit; }
.ig-modal-cancel { border-right: 0.5px solid var(--border-color); color: var(--text-color); }
.ig-modal-confirm { color: var(--accent); }

/* TUTORIAL OVERLAY */
#interactive-tutorial { 
    position: fixed; top: 0; left: 0; right: 0; bottom: 0; 
    z-index: 10000; overflow: hidden; pointer-events: auto; transition: opacity 0.4s; 
}
#tut-hole { 
    position: absolute; box-shadow: 0 0 0 9999px rgba(0,0,0,0.55); 
    transition: all 0.4s ease-in-out, box-shadow 0.4s; pointer-events: none; border-radius: 12px; 
}
#tut-hotspot { 
    position: absolute; z-index: 10005; cursor: pointer; 
    background: transparent; display: none; border-radius: 12px; pointer-events: auto;
}
#tut-content { 
    position: absolute; left: 10%; width: 80%; color: white; text-align: center; 
    transition: all 0.3s ease-in-out; pointer-events: none; 
    font-size: 16px; font-weight: 600; line-height: 1.5; letter-spacing: 0.2px;
    text-shadow: 0px 2px 5px rgba(0,0,0,0.95), 0px 4px 15px rgba(0,0,0,0.8); z-index: 10002;
}

body.tutorial-active button:not(.tut-allow-interaction),
body.tutorial-active .nav-btn:not(.tut-allow-interaction),
body.tutorial-active .story-item:not(.tut-allow-interaction),
body.tutorial-active input:not(.tut-allow-interaction),
body.tutorial-active select:not(.tut-allow-interaction) {
    pointer-events: none !important;
}
.tut-allow-interaction { pointer-events: auto !important; position: relative !important; z-index: 10006 !important; }

/* --------------------------------- */
/* KOMENTÁŘE                         */
/* --------------------------------- */
#comments-overlay { position: fixed; top:0; left:0; right:0; bottom:0; background: rgba(0,0,0,0.5); z-index: 9998; opacity: 0; pointer-events: none; transition: opacity 0.3s; }
#comments-overlay.active { opacity: 1; pointer-events: auto; }
#comments-panel { 
    position: fixed; bottom: 0; left: 0; right: 0; height: 65vh; 
    background: var(--bg-color); z-index: 9999; border-radius: 14px 14px 0 0; 
    transform: translateY(100%); transition: transform 0.3s cubic-bezier(0.2, 0.9, 0.3, 1); 
    display: flex; flex-direction: column;
}
#comments-panel.active { transform: translateY(0); }
.comments-header { display: flex; justify-content: center; align-items: center; padding: 14px 20px; border-bottom: 0.5px solid var(--border-color); font-weight: 600; font-size: 15px; position: relative; }
.comments-header::before { content: ''; position: absolute; top: 8px; left: 50%; transform: translateX(-50%); width: 36px; height: 4px; background: var(--border-color); border-radius: 2px; }
.comments-close { cursor: pointer; font-size: 1.3rem; line-height: 1; opacity: 0.5; padding: 0 5px; position: absolute; right: 16px; }
.comments-list { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 16px; }
.comment-item { display: flex; gap: 12px; }
.comment-avatar { width: 32px; height: 32px; border-radius: 50%; background: #ccc; flex-shrink: 0; overflow: hidden; }
.comment-body { display: flex; flex-direction: column; font-size: 14px; }
.comment-author { font-weight: 600; margin-bottom: 2px; display: flex; align-items: center; gap: 6px; font-size: 13px; }
.comment-time { font-size: 12px; opacity: 0.4; font-weight: 400; }
.comments-input-area { padding: 12px 16px 20px; border-top: 0.5px solid var(--border-color); display: flex; gap: 8px; background: var(--bg-color); }
.comments-input-area input { flex: 1; padding: 9px 14px !important; border-radius: 20px !important; border: 1px solid var(--border-color) !important; background: var(--secondary-bg) !important; font-size: 14px; font-family: inherit; }
.comments-input-area button { background: var(--accent); color: white; border: none; border-radius: 50%; width: 36px; height: 36px; display: flex; justify-content: center; align-items: center; cursor: pointer; flex-shrink: 0; }

/* --------------------------------- */
/* CHAT ZPRÁVY (IG Direct style)     */
/* --------------------------------- */
.chat-header-main { padding: 14px 16px 10px; font-size: 22px; font-weight: 700; letter-spacing: -0.3px; }
.chat-search-bar { margin: 0 16px 10px; display: flex; align-items: center; gap: 8px; background: var(--search-bg); border-radius: 10px; padding: 7px 12px; }
.chat-search-bar svg { width: 16px; height: 16px; color: var(--text-secondary, #737373); flex-shrink: 0; }
.chat-search-bar input { flex: 1; border: none; background: transparent; outline: none; font-size: 14px; font-family: inherit; color: var(--text-color); }
.chat-search-bar input::placeholder { color: var(--text-secondary, #737373); }
.chat-list { display: flex; flex-direction: column; }
.chat-row { display: flex; align-items: center; gap: 12px; padding: 10px 16px; cursor: pointer; }
.chat-row:active { background: var(--secondary-bg); }
.chat-row-avatar { width: 54px; height: 54px; border-radius: 50%; background: var(--secondary-bg); overflow: hidden; flex-shrink: 0; display: flex; align-items: center; justify-content: center; }
.chat-row-info { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.chat-row-name { font-weight: 600; font-size: 14px; margin-bottom: 2px; color: var(--text-color); }
.chat-row-msg { font-size: 14px; color: var(--text-secondary, #737373); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: 400; }
.chat-row-time { font-size: 12px; color: var(--text-secondary, #737373); white-space: nowrap; }
.chat-row-camera { width: 24px; height: 24px; color: var(--text-secondary, #737373); flex-shrink: 0; opacity: 0.5; }

/* Aktivní Konverzace */
#chat-conversation { position: fixed; top: 0; left: 0; width: 100%; height: 100dvh; background: var(--bg-color); z-index: 10005; display: flex; flex-direction: column; transform: translateX(100%); transition: transform 0.3s ease; }
#chat-conversation.active { transform: translateX(0); }
.conv-header { display: flex; align-items: center; padding: 12px 16px; border-bottom: 0.5px solid var(--border-color); font-weight: 600; font-size: 16px; gap: 12px; background: var(--bg-color); }
.conv-back { cursor: pointer; opacity: 0.7; display: flex; }
.conv-messages { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 6px; background: var(--bg-color); }
.msg-bubble { max-width: 70%; padding: 10px 14px; border-radius: 22px; font-size: 15px; line-height: 1.35; }
.msg-incoming { background: var(--secondary-bg); color: var(--text-color); align-self: flex-start; border-bottom-left-radius: 4px; }
.msg-outgoing { background: var(--accent); color: #fff; align-self: flex-end; border-bottom-right-radius: 4px; }

/* Rich Link – obdélníkový tvar jako na IG */
.rich-link-card { width: 240px; border-radius: 16px; overflow: hidden; background: var(--bg-color); cursor: pointer; border: 1px solid var(--border-color); margin-top: 4px; align-self: flex-start;}
.rich-link-img { width: 100%; height: 140px; background-size: cover; background-position: center; position: relative; }
.rich-link-info { padding: 10px 12px; display: flex; flex-direction: column; gap: 2px; }
.rich-link-title { font-weight: 600; font-size: 14px; color: var(--text-color); }
.rich-link-sub { font-size: 12px; color: var(--text-secondary, #737373); }

/* IG Reel Share card v chatu - 9:16 poměr stran přesně jako sdílení Reel na IG */
.ig-reel-card { width: 145px; max-width: 44vw; aspect-ratio: 9 / 16; border-radius: 14px; overflow: hidden; position: relative; background: #111; margin-top: 4px; box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2); cursor: pointer; border: 1px solid var(--border-color); transition: transform 0.15s ease, box-shadow 0.15s ease; -webkit-tap-highlight-color: transparent; }
.ig-reel-card:hover { transform: translateY(-2px); box-shadow: 0 6px 22px rgba(0, 0, 0, 0.28); }
.ig-reel-card:active { transform: scale(0.97); }
.ig-reel-card img { width: 100%; height: 100%; object-fit: cover; display: block; image-rendering: -webkit-optimize-contrast; image-rendering: crisp-edges; }


.conv-input { padding: 10px 16px 20px; background: var(--bg-color); display: flex; gap: 8px; border-top: 0.5px solid var(--border-color); align-items: center; }
.conv-input input { flex: 1; padding: 9px 14px !important; border-radius: 22px !important; border: 1px solid var(--border-color) !important; background: var(--secondary-bg) !important; font-size: 14px; font-family: inherit; color: var(--text-color); }
.conv-input button { background: var(--accent); color: white; border: none; border-radius: 50%; width: 36px; height: 36px; cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
`;
document.head.appendChild(style);


function applyTheme() { document.documentElement.setAttribute('data-theme', userSettings.theme); }
applyTheme();

// ==========================================
// 4. MĚŘENÍ ČASU V APLIKACI A TUTORIAL
// ==========================================
function replayTutorial() {
    localStorage.removeItem('tutorial_seen');
    // Přepnutí na výchozí obrazovku "Objevuj", kde tutoriál začíná
    document.querySelectorAll('.app-screen').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    const exploreBtn = document.querySelector('.nav-btn[data-target="screen-explore"]');
    if (exploreBtn) exploreBtn.classList.add('active');
    document.getElementById('screen-explore').classList.add('active');

    showTutorial();
}


setInterval(() => {
    let accMs = parseInt(localStorage.getItem('app_time_ms') || '0');
    accMs += 5000;
    localStorage.setItem('app_time_ms', accMs.toString());
    const hrsEl = document.getElementById('stat-hours');
    if (hrsEl) hrsEl.innerText = (accMs / 3600000).toFixed(1);
}, 5000);

function showTutorial() {
    // Přidáno: Pokud už uživatel tutoriál viděl, funkce se rovnou ukončí
    if (localStorage.getItem('tutorial_seen') === 'true') return;
    // Skip tutorial via URL parameter (e.g. ?notutorial) — useful for automated testing
    if (new URLSearchParams(window.location.search).has('notutorial')) {
        localStorage.setItem('tutorial_seen', 'true');
        return;
    }

    document.body.classList.add('tutorial-active');

    const overlay = document.createElement('div');
    overlay.id = 'interactive-tutorial';

    const hole = document.createElement('div');
    hole.id = 'tut-hole';

    const hotspot = document.createElement('div');
    hotspot.id = 'tut-hotspot';

    const content = document.createElement('div');
    content.id = 'tut-content';

    const navBlocker = document.createElement('div');
    navBlocker.style.cssText = 'position:fixed; bottom:0; left:0; width:100%; height:80px; z-index:10001; display:none; pointer-events: auto;';

    const skipBtn = document.createElement('button');
    skipBtn.id = 'tut-skip-btn';
    skipBtn.className = 'tut-allow-interaction';
    skipBtn.innerText = 'Přeskočit';
    skipBtn.style.cssText = 'position:fixed; top:16px; right:16px; background:rgba(0,0,0,0.65); backdrop-filter:blur(8px); border:1px solid rgba(255,255,255,0.3); color:#fff; font-size:13px; font-weight:600; padding:6px 14px; border-radius:20px; z-index:10005; cursor:pointer; pointer-events:auto;';
    const closeTutorial = () => {
        overlay.style.opacity = '0';
        setTimeout(() => {
            overlay.remove();
            navBlocker.remove();
            skipBtn.remove();
            document.body.classList.remove('tutorial-active');
        }, 300);
        localStorage.setItem('tutorial_seen', 'true');
    };
    skipBtn.onclick = closeTutorial;
    window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && document.body.classList.contains('tutorial-active')) closeTutorial();
    }, { once: true });

    overlay.appendChild(hole);
    overlay.appendChild(hotspot);
    overlay.appendChild(content);
    overlay.appendChild(skipBtn);
    document.body.appendChild(overlay);
    document.body.appendChild(navBlocker);

    let currentStep = 0;
    const navBtns = document.querySelectorAll('.nav-btn');

    const steps = [
        {
            pre: () => { if (navBtns[0]) navBtns[0].click(); },
            selector: "#explore-grid-container",
            msg: "Záložka Objevuj. Níže se zobrazují dostupné mapy s postupy.",
            action: 'click_anywhere'
        },
        {
            selector: ".story-item",
            msg: "Volbou vybraného filtru se mapy zúží pouze na daný terén.",
            action: 'click_target'
        },
        {
            selector: ".nav-btn[data-target='screen-scroll']",
            msg: "Číslo u ikonky ukazuje počet aktivních filtrů. Nyní přejdeme do hlavního feedu pro prohlížení.",
            action: 'click_target',
            delay: 300
        },
        {
            selector: null,
            msg: "Zde se nachází hlavní feed. Posun na další postup probíhá plynulým tahem nahoru.",
            action: 'native_scroll',
            delay: 600
        },
        {
            selector: null,
            msg: "Detailní průzkum mapy se aktivuje přiblížením dvěma prsty.",
            action: 'native_zoom',
            delay: 100
        },
        {
            selector: null,
            msg: "Rychlým dvojitým poklepáním na mapu se pohled opět oddálí.",
            action: 'native_dblclick',
            delay: 100
        },
        {
            selector: () => `.reel[data-index="${Math.max(0, activeIndex)}"] .bookmark-btn`,
            msg: "Tímto tlačítkem se postup uloží do osobní sbírky.",
            action: 'click_target',
            delay: 100
        },
        {
            selector: () => `.reel[data-index="${Math.max(0, activeIndex)}"] .btn-primary`,
            msg: "Tlačítko Volby zobrazí detailní porovnání variant a časů.",
            action: 'click_target',
            delay: 100
        },
        {
            undarken: true,
            selector: null,
            msg: "Zde je zobrazeno porovnání. Aplikace časy přepočítává přímo na míru tvému tempu.",
            action: 'click_anywhere',
            delay: 400
        },
        {
            pre: () => { if (isPanelOpen && typeof toggleVariants === 'function') toggleVariants(activeIndex); },
            selector: ".nav-btn[data-target='screen-profile']",
            msg: "Na osobním profilu se shromažďují všechny dříve uložené postupy a statistiky.",
            action: 'click_target',
            delay: 300
        },
        {
            selector: "#profile-content-wrapper",
            msg: "Tady jsou tvá osobní data přehledně k dispozici.",
            action: 'click_anywhere',
            delay: 400
        },
        {
            selector: ".nav-btn[data-target='screen-settings']",
            msg: "Nastavení aplikace umožňuje přizpůsobit její chování.",
            action: 'click_target',
            delay: 100
        },
        {
            selector: "#pace-slider",
            msg: "Zde se upravuje průměrné tempo pro co nejpřesnější odhady časů.",
            action: 'native_input',
            delay: 400
        },
        {
            pre: () => { if (navBtns[0]) navBtns[0].click(); },
            selector: null,
            msg: "Tutoriál je u konce. Dvojklik na oddálené mapě slouží zároveň i pro 'To se mi líbí'.",
            action: 'end'
        }
    ];

    function advanceTutorial() {
        document.querySelectorAll('.tut-allow-interaction').forEach(e => e.classList.remove('tut-allow-interaction'));
        currentStep++;
        renderStep();
    }

    function getTargetElement(stepSelector) {
        if (!stepSelector) return null;
        let res = typeof stepSelector === 'function' ? stepSelector() : stepSelector;
        return typeof res === 'string' ? document.querySelector(res) : res;
    }

    function renderStep() {
        if (currentStep >= steps.length) {
            overlay.style.opacity = '0';
            setTimeout(() => {
                overlay.remove();
                document.body.classList.remove('tutorial-active');
            }, 400);
            localStorage.setItem('tutorial_seen', 'true');
            if (navBtns[0]) navBtns[0].click();
            return;
        }

        let step = steps[currentStep];
        if (step.pre) step.pre();

        if (step.undarken) {
            hole.style.boxShadow = 'none';
        } else {
            hole.style.boxShadow = '0 0 0 9999px rgba(0,0,0,0.55)';
        }

        setTimeout(() => {
            let el = getTargetElement(step.selector);
            let pad = 12;

            if (el && el.getBoundingClientRect().width > 0) {
                let rect = el.getBoundingClientRect();

                if (rect.top > window.innerHeight * 0.5) {
                    content.style.bottom = (window.innerHeight - rect.top + pad + 15) + 'px';
                    content.style.top = 'auto';
                } else {
                    content.style.top = (rect.bottom + pad + 15) + 'px';
                    content.style.bottom = 'auto';
                }

                hole.style.opacity = '1';
                hole.style.width = (rect.width + pad * 2) + 'px';
                hole.style.height = (rect.height + pad * 2) + 'px';
                hole.style.left = (rect.left - pad) + 'px';
                hole.style.top = (rect.top - pad) + 'px';

                if (step.action === 'click_target') {
                    hotspot.style.display = 'block';
                    hotspot.style.width = (rect.width + pad * 2) + 'px';
                    hotspot.style.height = (rect.height + pad * 2) + 'px';
                    hotspot.style.left = (rect.left - pad) + 'px';
                    hotspot.style.top = (rect.top - pad) + 'px';
                } else {
                    hotspot.style.display = 'none';
                }
            } else {
                content.style.top = '45%';
                content.style.bottom = 'auto';

                if (!step.undarken) {
                    hole.style.opacity = '1';
                    hole.style.width = '0px';
                    hole.style.height = '0px';
                    hole.style.left = '50%';
                    hole.style.top = '50%';
                }
                hotspot.style.display = 'none';
            }

            content.innerHTML = step.msg;

            overlay.onclick = null;
            hotspot.onclick = null;

            if (step.action === 'click_anywhere' || step.action === 'end') {
                overlay.style.pointerEvents = 'auto';
                navBlocker.style.display = 'none';
                overlay.onclick = () => advanceTutorial();
            } else {
                overlay.style.pointerEvents = 'none';

                if (step.action === 'click_target' && el) {
                    overlay.style.pointerEvents = 'auto';
                    navBlocker.style.display = 'none';

                    hotspot.onclick = (e) => {
                        e.stopPropagation();
                        el.click();
                        advanceTutorial();
                    };

                    overlay.onclick = () => {
                        content.style.transform = 'scale(1.03)';
                        setTimeout(() => content.style.transform = 'none', 150);
                    };
                }
                else if (step.action === 'native_scroll') {
                    navBlocker.style.display = 'block';
                    let startIdx = activeIndex;
                    const rc = document.getElementById('reels-container');
                    if (rc) {
                        let scrollCheck = setInterval(() => {
                            if (activeIndex !== startIdx && activeIndex !== -1) {
                                clearInterval(scrollCheck);
                                advanceTutorial();
                            }
                        }, 200);
                    } else { advanceTutorial(); }
                }
                else if (step.action === 'native_zoom') {
                    navBlocker.style.display = 'block';
                    let zoomCheck = setInterval(() => {
                        let map = mapInstances[activeIndex];
                        if (map) {
                            clearInterval(zoomCheck);
                            const handler = () => {
                                if (map.getZoom() > map.getMinZoom() + 0.05) {
                                    map.off('zoomend', handler);
                                    advanceTutorial();
                                }
                            };
                            map.on('zoomend', handler);
                        }
                    }, 200);
                }
                else if (step.action === 'native_dblclick') {
                    navBlocker.style.display = 'block';
                    let dblCheck = setInterval(() => {
                        let map = mapInstances[activeIndex];
                        if (map) {
                            clearInterval(dblCheck);
                            const handler = () => {
                                if (map.getZoom() <= map.getMinZoom() + 0.05) {
                                    map.off('zoomend', handler);
                                    advanceTutorial();
                                }
                            };
                            map.on('zoomend', handler);
                        }
                    }, 200);
                }
                else if (step.action === 'native_input' && el) {
                    navBlocker.style.display = 'block';
                    el.classList.add('tut-allow-interaction');
                    const handler = () => {
                        el.removeEventListener('change', handler);
                        advanceTutorial();
                    };
                    el.addEventListener('change', handler);
                } else {
                    advanceTutorial();
                }
            }
        }, step.delay || 50);
    }

    renderStep();
}

// ==========================================
// 5. INICIALIZACE APLIKACE A UI SOCIÁLNÍCH FUNKCÍ
// ==========================================
let searchTimeout = null;

function debounceSearchUsers(e) {
    clearTimeout(searchTimeout);
    const query = e.target.value.trim().toLowerCase();
    const resultsEl = document.getElementById('user-search-results');
    const chatListEl = document.getElementById('chat-list-container');

    // Pokud je text moc krátký, vrátíme se na seznam chatů
    if (query.length < 2) {
        resultsEl.style.display = 'none';
        chatListEl.style.display = 'block';
        return;
    }

    searchTimeout = setTimeout(async () => {
        chatListEl.style.display = 'none';
        resultsEl.style.display = 'flex';
        resultsEl.innerHTML = '<div style="opacity:0.5; padding: 10px 0; text-align:center;">Hledám uživatele...</div>';

        try {
            const usersRef = db.collection('users');
            const snapshot = await usersRef.get();

            let found = [];
            snapshot.forEach(doc => {
                const data = doc.data();
                // Filtrace jmen bez rozlišení velikosti písmen a vynechání vlastního profilu
                if (data.name && data.name.toLowerCase().includes(query) && (!currentUser || doc.id !== currentUser.uid)) {
                    found.push({ id: doc.id, ...data });
                }
            });

            if (found.length === 0) {
                resultsEl.innerHTML = '<div style="opacity:0.5; padding: 10px 0; text-align:center;">Uživatel nenalezen.</div>';
            } else {
                resultsEl.innerHTML = '<div style="font-size:0.85rem; opacity:0.6; padding-left:5px;">Výsledky hledání:</div>' + found.map(u => `
                    <div class="chat-row" style="padding:10px 0; border:none;" onclick="startDirectMessage('${u.id}', '${u.name}')">
                        <div class="chat-row-avatar" style="background-image:url('${u.photo || 'https://i.pravatar.cc/100?img=1'}'); background-size:cover; border:1px solid var(--border-color);"></div>
                        <div class="chat-row-info">
                            <div class="chat-row-name">${u.name}</div>
                        </div>
                    </div>
                `).join('');
            }
        } catch (err) {
            resultsEl.innerHTML = `<div style="color:red; padding: 10px 0;">Chyba databáze: ${err.message}</div>`;
        }
    }, 400); // 400ms prodleva, aby se neodesílal dotaz s každým úhozem do klávesnice
}

function startDirectMessage(targetUid, targetName) {
    // Příprava UI pro budoucí vytvoření soukromé 1-on-1 kolekce
    alert(`Zde se vytvoří soukromá konverzace s uživatelem ${targetName}. (Backend propojení připravíme v dalším kroku)`);

    // Reset vyhledávače
    document.getElementById('user-search-input').value = '';
    document.getElementById('user-search-results').style.display = 'none';
    document.getElementById('chat-list-container').style.display = 'block';
}


function injectChatAndCommentsUI() {
    // Přidání 5. ikony (Zprávy) do spodního menu, pokud tam ještě není
    const navContainer = document.querySelector('nav') || document.querySelector('.bottom-nav');
    if (navContainer && navContainer.querySelectorAll('.nav-btn').length === 4) {
        const chatBtn = document.createElement('button');
        chatBtn.className = 'nav-btn';
        chatBtn.setAttribute('data-target', 'screen-chat');
        // Ikonka "Zprávy/Paper Plane" pro Instagram feel
        chatBtn.innerHTML = `<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>`;

        // Vložení před profil
        const profileBtn = navContainer.querySelector('[data-target="screen-profile"]');
        if (profileBtn) navContainer.insertBefore(chatBtn, profileBtn);
        else navContainer.appendChild(chatBtn);
    }

    // Vygenerování globálního panelu pro Komentáře
    const commentsOverlay = document.createElement('div');
    commentsOverlay.id = 'comments-overlay';
    commentsOverlay.onclick = closeComments;

    const commentsPanel = document.createElement('div');
    commentsPanel.id = 'comments-panel';
    commentsPanel.innerHTML = `
        <div class="comments-header">Komentáře <span class="comments-close" onclick="closeComments()">&times;</span></div>
        <div class="comments-list">
            <!-- Dummy komentáře -->
            <div class="comment-item">
                <div class="comment-avatar" style="background-image:url('https://i.pravatar.cc/100?img=11'); background-size:cover;"></div>
                <div class="comment-body">
                    <div class="comment-author">Tomas_bez <span class="comment-time">2h</span></div>
                    <div class="comment-text">Ty jo, ta levá varianta vypadá rychlejší, zkoušel to někdo? 🤔</div>
                </div>
            </div>
            <div class="comment-item">
                <div class="comment-avatar" style="background-image:url('https://i.pravatar.cc/100?img=5'); background-size:cover;"></div>
                <div class="comment-body">
                    <div class="comment-author">Klara123 <span class="comment-time">5h</span></div>
                    <div class="comment-text">Šla jsem rovně a bylo tam hrozný hustníkové peklo... Doporučuju obíhat. 🌲🏃‍♀️</div>
                </div>
            </div>
        </div>
        <div class="comments-input-area">
            <input type="text" placeholder="Přidat komentář...">
            <button><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg></button>
        </div>
    `;
    document.body.appendChild(commentsOverlay);
    document.body.appendChild(commentsPanel);
}

function renderChatScreen() {
    let screen = document.getElementById('screen-chat');
    if (!screen) return;

    let userName = (currentUser && currentUser.displayName) ? currentUser.displayName : (localStorage.getItem('profile_username') || 'franta14_');

    screen.innerHTML = `
        <div class="chat-header-main">${userName}</div>
        
        <!-- KOMPAKTNÍ VYHLEDÁVAČ (IG style) -->
        <div class="chat-search-bar">
            <svg viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5" fill="none"><circle cx="11" cy="11" r="7"></circle><line x1="16.5" y1="16.5" x2="21" y2="21" stroke-linecap="round"></line></svg>
            <input type="text" id="user-search-input" placeholder="Hledat">
        </div>
        
        <!-- KONTEJNER PRO VÝSLEDKY -->
        <div id="user-search-results" style="padding: 0 16px; display: none; flex-direction: column; gap:4px;"></div>

        <!-- SEZNAM AKTIVNÍCH CHATŮ -->
        <div class="chat-list" id="chat-list-container">
            <div class="chat-row" onclick="openChatConversation('Globální Diskuzní Klub')">
                <div class="chat-row-avatar">
                    <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="#999" stroke-width="1.5"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
                </div>
                <div class="chat-row-info">
                    <div class="chat-row-name">Globální Diskuzní Klub</div>
                    <div class="chat-row-msg">Klikni a vstup do živého chatu!</div>
                </div>
            </div>
        </div>

        <!-- SAMOTNÉ OKNO KONVERZACE -->
        <div id="chat-conversation">
            <div class="conv-header">
                <div class="conv-back" onclick="closeChatConversation()"><svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg></div>
                <div id="conv-name">Chat</div>
            </div>
            <div class="conv-messages" id="conv-messages-box"></div>
            <div class="conv-input">
                <input type="text" id="new-chat-input" placeholder="Napsat zprávu...">
                <button id="send-chat-btn"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg></button>
            </div>
        </div>
    `;

    document.getElementById('user-search-input').addEventListener('input', debounceSearchUsers);
}


function openChatConversation(name) {
    document.getElementById('conv-name').innerText = name;
    document.getElementById('chat-conversation').classList.add('active');
    document.getElementById('bottom-nav').style.display = 'none';

    if (!document.getElementById('new-chat-input')) {
        document.querySelector('.conv-input').innerHTML = `
            <input type="text" id="new-chat-input" placeholder="Napsat zprávu..." style="flex:1; padding:10px; border-radius:20px; border:1px solid var(--border-color); background:var(--secondary-bg); color:var(--text-color);">
            <button id="send-chat-btn" style="background:var(--accent); color:white; border:none; border-radius:50%; width:40px; height:40px; display:flex; justify-content:center; align-items:center;"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg></button>
        `;
    }

    const msgsEl = document.querySelector('.conv-messages');
    msgsEl.innerHTML = '<div style="text-align:center; padding: 20px; opacity: 0.5;">Připojuji se...</div>';

    if (currentChatUnsubscribe) currentChatUnsubscribe();
    currentChatUnsubscribe = db.collection('global_chat')
        .orderBy('timestamp', 'asc')
        .onSnapshot(snapshot => {
            msgsEl.innerHTML = '';
            snapshot.forEach(doc => {
                const data = doc.data();
                const isMe = currentUser && data.authorUid === currentUser.uid;
                const bubbleClass = isMe ? 'msg-outgoing' : 'msg-incoming';

                if (data.type === 'shared_route') {
                    let bName = data.basename;
                    let targetIndex = data.routeIndex;
                    if (!bName && postupyData && postupyData.length > 0) {
                        let found = postupyData.find(p => p.id === data.routeId || p.map_id === data.routeId);
                        if (found) {
                            bName = found.file ? found.file.replace('.geojson', '') : '';
                            targetIndex = postupyData.indexOf(found);
                        } else {
                            bName = postupyData[0].file ? postupyData[0].file.replace('.geojson', '') : '';
                            targetIndex = 0;
                        }
                    }
                    let vParam = (thumbsMeta && thumbsMeta.version) ? '?v=' + thumbsMeta.version : '';
                    let shareImg = bName ? `thumbs/share_${bName}.jpg${vParam}` : `thumbs/map_homolka.jpg${vParam}`;
                    let fallbackImg = bName ? `thumbs/${bName}.jpg${vParam}` : `thumbs/map_homolka.jpg${vParam}`;
                    let rName = data.routeName || 'Homolka';

                    msgsEl.innerHTML += `
                        <div class="msg-bubble ${bubbleClass}" style="background:transparent; border:none; padding:0; box-shadow:none;">
                            ${!isMe ? `<div style="font-size: 0.75rem; margin-bottom: 3px; opacity: 0.7; color:var(--text-color); font-weight: 500;">${data.authorName}</div>` : ''}
                            <div class="ig-reel-card" onclick="openSharedRoute('${data.mapId || 'homolka'}', ${targetIndex !== undefined ? targetIndex : -1})">
                                <img src="${shareImg}" alt="${rName}" onerror="this.onerror=null; this.src='${fallbackImg}';">
                            </div>
                        </div>`;
                } else {
                    msgsEl.innerHTML += `
                        <div class="msg-bubble ${bubbleClass}">
                            ${!isMe ? `<div style="font-size: 0.7rem; margin-bottom: 3px; opacity: 0.6;">${data.authorName}</div>` : ''}
                            ${data.text}
                        </div>`;
                }
            });
            msgsEl.scrollTop = msgsEl.scrollHeight;
        });
}

function closeChatConversation() {
    document.getElementById('chat-conversation').classList.remove('active');
    document.getElementById('bottom-nav').style.display = '';
    if (currentChatUnsubscribe) { currentChatUnsubscribe(); currentChatUnsubscribe = null; }
}


function openSharedRoute(mapId, targetIndex) {
    closeChatConversation();
    openFeed(mapId || 'homolka', false, targetIndex);
}
function openComments(index) {
    const postup = postupyData[index];
    const routeId = postup.map_id + "_" + postup.id;

    document.getElementById('comments-overlay').classList.add('active');
    const panel = document.getElementById('comments-panel');
    panel.classList.add('active');
    panel.setAttribute('data-current-route', routeId);

    if (!document.getElementById('new-comment-input')) {
        document.querySelector('.comments-input-area').innerHTML = `
            <input type="text" id="new-comment-input" placeholder="Přidat komentář..." style="flex:1; padding:10px; border-radius:20px; border:1px solid var(--border-color); background:var(--secondary-bg); color:var(--text-color);">
            <button id="send-comment-btn" style="background:var(--accent); color:white; border:none; border-radius:50%; width:40px; height:40px; display:flex; justify-content:center; align-items:center;"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg></button>
        `;
    }

    const listEl = document.querySelector('.comments-list');
    listEl.innerHTML = '<div style="text-align:center; padding: 20px; opacity: 0.5;">Načítám komentáře...</div>';

    if (currentCommentsUnsubscribe) currentCommentsUnsubscribe();

    // Změna: Odebráno .orderBy(), řazení probíhá lokálně
    currentCommentsUnsubscribe = db.collection('comments')
        .where('routeId', '==', routeId)
        .onSnapshot(snapshot => {
            listEl.innerHTML = '';
            if (snapshot.empty) {
                listEl.innerHTML = '<div style="text-align:center; padding: 20px; opacity: 0.5;">Zatím žádné komentáře. Buď první!</div>';
                return;
            }

            // Lokální seřazení podle času
            let commentsArray = [];
            snapshot.forEach(doc => commentsArray.push(doc.data()));
            commentsArray.sort((a, b) => {
                let timeA = a.timestamp ? a.timestamp.toMillis() : Date.now();
                let timeB = b.timestamp ? b.timestamp.toMillis() : Date.now();
                return timeA - timeB;
            });

            commentsArray.forEach(data => {
                const time = data.timestamp ? new Date(data.timestamp.toDate()).toLocaleTimeString('cs-CZ', { hour: '2-digit', minute: '2-digit' }) : 'Teď';
                listEl.innerHTML += `
                    <div class="comment-item">
                        <div class="comment-avatar" style="background-image:url('${data.authorPhoto}'); background-size:cover;"></div>
                        <div class="comment-body">
                            <div class="comment-author">${data.authorName} <span class="comment-time">${time}</span></div>
                            <div class="comment-text">${data.text}</div>
                        </div>
                    </div>`;
            });
            listEl.scrollTop = listEl.scrollHeight;
        }, error => {
            // Zachycení chyb pro snazší ladění
            listEl.innerHTML = `<div style="text-align:center; padding: 20px; color: red;">Chyba DB: ${error.message}</div>`;
        });
}

function closeComments() {
    document.getElementById('comments-overlay').classList.remove('active');
    document.getElementById('comments-panel').classList.remove('active');
    if (currentCommentsUnsubscribe) { currentCommentsUnsubscribe(); currentCommentsUnsubscribe = null; }
}


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
    } catch (e) { }

    injectChatAndCommentsUI(); // Inicializace nových UI komponent

    const navButtons = document.querySelectorAll('.nav-btn');
    const screens = document.querySelectorAll('.app-screen');

    navButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const targetId = btn.getAttribute('data-target');

            let wasSavedMode = document.body.classList.contains('saved-mode-active');

            if (wasSavedMode) {
                document.body.classList.remove('saved-mode-active');
                updateExploreBadge(document.getElementById('nav-badge'));

                const screenScroll = document.getElementById('screen-scroll');
                if (screenScroll) {
                    screenScroll.style.transform = '';
                    screenScroll.style.transition = '';
                }

                if (targetId === 'screen-scroll') {
                    let currentMapId = activeIndex !== -1 ? postupyData[activeIndex].id : null;
                    let visibleReels = Array.from(document.querySelectorAll('.reel')).filter(r => r.style.display !== 'none');
                    if (visibleReels.length > 0) {
                        let nextReel = visibleReels.find(r => postupyData[r.dataset.index].id !== currentMapId) || visibleReels[0];
                        activeIndex = parseInt(nextReel.dataset.index);
                        const reelsContainer = document.getElementById('reels-container');
                        if (reelsContainer) reelsContainer.scrollTo({ top: nextReel.offsetTop, behavior: 'instant' });
                    }
                }
            } else if (targetId === 'screen-scroll') {
                updateExploreBadge(document.getElementById('nav-badge'));
            }

            navButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Bottom nav ztmavení na reels feedu (jako IG)
            const bottomNav = document.getElementById('bottom-nav');
            if (targetId === 'screen-scroll') {
                bottomNav.classList.add('nav-dark');
            } else {
                bottomNav.classList.remove('nav-dark');
            }

            screens.forEach(screen => {
                if (screen.id === targetId) {
                    screen.classList.add('active');
                    if (targetId === 'screen-profile') renderProfileSaved();
                    if (targetId === 'screen-settings') renderSettings();
                    if (targetId === 'screen-chat') renderChatScreen();

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
    smh.innerHTML = `<svg style="width:28px; height:28px; margin-right:10px; margin-bottom:-2px;" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/></svg>`;
    smh.onclick = (e) => {
        e.stopPropagation();
        closeSavedFeed();
    };
    const screenScrollElContainer = document.getElementById('screen-scroll');
    if (screenScrollElContainer) {
        screenScrollElContainer.appendChild(smh);
    } else {
        document.body.appendChild(smh);
    }

    let startX = 0;
    let startY = 0;
    let isSwiping = false;
    let gestureDetermined = false;
    let screenScrollEl = null;

    window.addEventListener('touchstart', e => {
        if (!document.body.classList.contains('saved-mode-active')) return;
        if (e.touches.length === 1) {
            startX = e.touches[0].clientX;
            startY = e.touches[0].clientY;
            isSwiping = false;
            gestureDetermined = false;
            screenScrollEl = document.getElementById('screen-scroll');
            if (screenScrollEl) {
                screenScrollEl.style.transition = 'none';
            }
        } else {
            isSwiping = false;
            gestureDetermined = true;
            if (screenScrollEl) {
                screenScrollEl.style.transform = '';
                screenScrollEl.style.transition = '';
            }
        }
    }, { passive: true, capture: true });

    window.addEventListener('touchmove', e => {
        if (!document.body.classList.contains('saved-mode-active') || !screenScrollEl) return;
        if (e.touches.length !== 1) {
            if (isSwiping) {
                isSwiping = false;
                gestureDetermined = true;
                screenScrollEl.style.transform = '';
                screenScrollEl.style.transition = '';
            }
            return;
        }

        let deltaX = e.touches[0].clientX - startX;
        let deltaY = e.touches[0].clientY - startY;
        let absY = Math.abs(deltaY);

        if (!gestureDetermined) {
            if (Math.hypot(deltaX, deltaY) > 8) {
                gestureDetermined = true;
                if (deltaX > 0 && deltaX > absY * 1.1) {
                    isSwiping = true;
                } else {
                    isSwiping = false;
                }
            }
        }

        if (isSwiping) {
            // Uzamknout vertikální posun a zabránit Leaflet map drag
            e.preventDefault();
            e.stopPropagation();
            let currentX = Math.max(0, deltaX);
            screenScrollEl.style.transform = `translateX(${currentX}px)`;
        }
    }, { passive: false, capture: true });

    const handleTouchEnd = (e) => {
        if (!isSwiping || !screenScrollEl) {
            isSwiping = false;
            gestureDetermined = false;
            return;
        }
        isSwiping = false;
        gestureDetermined = false;
        e.preventDefault();
        e.stopPropagation();

        let changedTouch = e.changedTouches ? e.changedTouches[0] : null;
        let deltaX = changedTouch ? changedTouch.clientX - startX : 0;

        screenScrollEl.style.transition = 'transform 0.28s cubic-bezier(0.25, 1, 0.5, 1)';

        if (deltaX > window.innerWidth / 3 || deltaX > 90) {
            screenScrollEl.style.transform = 'translateX(100%)';
            setTimeout(() => {
                closeSavedFeed(true);
                screenScrollEl.style.transform = '';
                screenScrollEl.style.transition = '';
            }, 280);
        } else {
            screenScrollEl.style.transform = 'translateX(0)';
            setTimeout(() => {
                screenScrollEl.style.transform = '';
                screenScrollEl.style.transition = '';
            }, 280);
        }
    };

    window.addEventListener('touchend', handleTouchEnd, { passive: false, capture: true });
    window.addEventListener('touchcancel', () => {
        if (isSwiping && screenScrollEl) {
            isSwiping = false;
            gestureDetermined = false;
            screenScrollEl.style.transition = 'transform 0.2s ease-out';
            screenScrollEl.style.transform = 'translateX(0)';
            setTimeout(() => {
                screenScrollEl.style.transform = '';
                screenScrollEl.style.transition = '';
            }, 200);
        }
    }, { passive: true });

    loadData();
    setTimeout(updateUITexts, 200);
});

let selectedTerrains = new Set();

let thumbsMeta = null;

function loadData() {
    Promise.all([
        fetch('postupy/postupy_index.json?v=' + Date.now()).then(res => res.json()),
        fetch('thumbs/thumbs_meta.json?v=' + Date.now()).then(res => res.json()).catch(() => null)
    ]).then(([data, metaData]) => {
        postupyData = data;
        thumbsMeta = metaData;
        postupyData.forEach((map, index) => {
            map.terrain = 'cesko';
            map.map_id = 'homolka';
            map.map_name = 'Homolka';
            if (!map.id) map.id = index + 1;
        });

        buildReels();
        setupObserver();
        renderExploreGrid();
        setupExploreStories();
        renderProfileSaved();
        renderChatScreen(); // Předgenerujeme chat screen
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
        <div class="screen-header"><h2>${t('settings')} a aktivita</h2></div>
        <div class="screen-content ig-settings-content">
            <div class="ig-settings-search">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                <input type="text" placeholder="${t('searchRoutes')}">
            </div>
            
            <div class="ig-settings-section-title">${t('runner')}</div>
            <div class="ig-setting-row" onclick="openPaceModal()">
                <div class="ig-setting-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg></div>
                <div class="ig-setting-text">
                    <div class="ig-setting-label">${t('paceOnRoad')}</div>
                </div>
                <div class="ig-setting-val" id="setting-pace-val">${formatPace(userSettings.pace)}</div>
                <div class="ig-setting-chevron"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg></div>
            </div>

            <div class="ig-settings-section-title">${t('application')}</div>
            <div class="ig-setting-row" onclick="openLanguageModal()">
                <div class="ig-setting-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg></div>
                <div class="ig-setting-text"><div class="ig-setting-label">${t('language')}</div></div>
                <div class="ig-setting-val" id="setting-lang-val">${userSettings.language === 'cs' ? 'Čeština' : 'English'}</div>
                <div class="ig-setting-chevron"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg></div>
            </div>
            <div class="ig-setting-row" onclick="openThemeModal()">
                <div class="ig-setting-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg></div>
                <div class="ig-setting-text"><div class="ig-setting-label">${t('theme')}</div></div>
                <div class="ig-setting-val" id="setting-theme-val">${t('theme_' + userSettings.theme)}</div>
                <div class="ig-setting-chevron"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg></div>
            </div>
            <div class="ig-setting-row" onclick="startOfflineSync()">
                <div class="ig-setting-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg></div>
                <div class="ig-setting-text"><div class="ig-setting-label">${t('offlineMaps')}</div></div>
                <div class="ig-setting-chevron"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg></div>
            </div>

            <div class="ig-settings-section-title">${t('maps')}</div>
            <div class="ig-setting-row" onclick="clearAppCache()">
                <div class="ig-setting-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg></div>
                <div class="ig-setting-text"><div class="ig-setting-label">${t('clearCache')}</div></div>
                <div class="ig-setting-val" id="cache-size">0 MB</div>
                <div class="ig-setting-chevron"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg></div>
            </div>
            
            <div class="ig-settings-section-title">Nápověda</div>
            <div class="ig-setting-row" onclick="replayTutorial()">
                <div class="ig-setting-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><line x1="12" y1="17" x2="12.01" y2="17"></line></svg></div>
                <div class="ig-setting-text"><div class="ig-setting-label">Znovu spustit tutoriál</div></div>
                <div class="ig-setting-chevron"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg></div>
            </div>
        </div>
    `;

    if (typeof updateCacheSize === 'function') updateCacheSize();
}

function openLanguageModal() {
    openSelectionModal('language', t('language'), [
        { value: 'cs', label: 'Čeština' },
        { value: 'en', label: 'English' }
    ], userSettings.language, (selected) => {
        updateSettings('language', selected);
    });
}

function openThemeModal() {
    openSelectionModal('theme', t('theme'), [
        { value: 'system', label: t('theme_system') },
        { value: 'light', label: t('theme_light') },
        { value: 'dark', label: t('theme_dark') }
    ], userSettings.theme, (selected) => {
        updateSettings('theme', selected);
    });
}

function openSelectionModal(type, title, options, currentValue, onSelect) {
    let overlay = document.getElementById('settings-select-modal-overlay');
    let titleEl = document.getElementById('settings-select-title');
    let optionsEl = document.getElementById('settings-select-options');
    if (!overlay || !titleEl || !optionsEl) return;

    titleEl.innerText = title;
    optionsEl.innerHTML = options.map(opt => {
        const isSelected = opt.value === currentValue;
        return `
        <div class="ig-select-option ${isSelected ? 'selected' : ''}" onclick="window._onSelectSetting('${opt.value}')" style="display: flex; justify-content: space-between; align-items: center; padding: 14px 20px; cursor: pointer; border-bottom: 0.5px solid var(--border-color); font-size: 15px; font-weight: ${isSelected ? '600' : '400'}; color: ${isSelected ? 'var(--accent)' : 'inherit'};">
            <span>${opt.label}</span>
            ${isSelected ? `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>` : ''}
        </div>`;
    }).join('');

    window._onSelectSetting = (val) => {
        closeSettingsSelectModal();
        onSelect(val);
    };

    overlay.style.display = 'flex';
    requestAnimationFrame(() => overlay.classList.add('active'));
}

function closeSettingsSelectModal(e) {
    if (e && e.target && e.target.closest && e.target.closest('.ig-modal-content')) return;
    const overlay = document.getElementById('settings-select-modal-overlay');
    if (overlay) {
        overlay.classList.remove('active');
        setTimeout(() => overlay.style.display = 'none', 250);
    }
}

function openPaceModal() {
    const modal = document.getElementById('pace-modal-overlay');
    if (modal) {
        let m = Math.floor(userSettings.pace / 60);
        let s = userSettings.pace % 60;
        document.getElementById('pace-min').value = m;
        document.getElementById('pace-sec').value = s;
        modal.style.display = 'flex';
        setTimeout(() => modal.classList.add('active'), 10);
    }
}

function closePaceModal(e) {
    const modal = document.getElementById('pace-modal-overlay');
    if (modal) {
        modal.classList.remove('active');
        setTimeout(() => modal.style.display = 'none', 300);
    }
}

function savePaceModal() {
    let m = parseInt(document.getElementById('pace-min').value) || 3;
    let s = parseInt(document.getElementById('pace-sec').value) || 0;
    let totalSecs = m * 60 + s;
    updateSettings('pace', totalSecs);
    closePaceModal();
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
        } catch (e) { console.warn(e); }
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

        // Přidána ikonka pro KOMENTÁŘE mezi like a share
        reel.innerHTML = `
            <div class="map-clip" id="clip-${index}">
                <div class="map-container" id="map-${index}"></div>
                <div class="like-animation-container" id="like-anim-${index}">
                    <svg viewBox="0 0 24 24" fill="currentColor"><path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z"/></svg>
                </div>
            </div>
            <div class="reel-actions">
                <button class="action-btn like-btn" onclick="toggleLike(${index}, this)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z"/></svg></button>
                <button class="action-btn comment-btn" onclick="openComments(${index})"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg></button>
                <button class="action-btn share-btn" onclick="sharePostup(${index})"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg></button>
                <button class="${bookmarkClass}" onclick="toggleBookmark(${index}, this)">${bookmarkSvg}</button>
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
            let timeStr = `${Math.floor(adjCasS / 60)}:${Math.floor(adjCasS % 60).toString().padStart(2, '0')}`;
            let paceStr = `${Math.floor(adjTempoS / 60)}:${Math.floor(adjTempoS % 60).toString().padStart(2, '0')} min/km`;

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
                let dist = Math.sqrt(dx * dx + dy * dy);
                if (dist > 0) {
                    let ux = dx / dist, uy = dy / dist, vx = -uy, vy = ux;
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
                    let bulges = [{ corner: 'pos-top-left', val: maxLeftTop }, { corner: 'pos-top-right', val: maxRightTop }, { corner: 'pos-bottom-left', val: maxLeftBot }];
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
    Math.round = function (val) {
        if (val === zoom && typeof val === 'number') {
            // Vybíráme ostřejší úroveň dlaždic (ceil z desetinného zoomu, min. 3)
            return Math.min(6, Math.max(3, Math.ceil(val)));
        }
        return oldRound(val);
    };
    try { return originalSetView.call(this, center, zoom, noPrune, noUpdate); }
    finally { Math.round = oldRound; }
};

function initMapForReel(index) {
    const mapContainer = document.getElementById(`map-${index}`);
    if (!mapContainer) return;
    const map = L.map(`map-${index}`, {
        crs: L.CRS.Simple, minZoom: 0, maxZoom: 8, zoomSnap: 0,
        zoomControl: false, gestureHandling: false, inertia: false,
        tap: false,
        scrollWheelZoom: 'center',
        touchZoom: 'center',
        maxBoundsViscosity: 1.0,
        dragging: false, // Výchozí stav: posouvání zakázáno
        bounceAtZoomLimits: false // Zakáže "gumové" oddalování pod povolený minZoom
    });
    map.createPane('maskPane');
    map.getPane('maskPane').style.zIndex = 250;
    map.doubleClickZoom.disable();

    let mc = map.getContainer();

    // Intuitivní plynulé přiblížení / oddálení dvojklikem (nebo dvojklepnutím)
    let lastClickTime = 0;
    map.on('click', function (e) {
        let currentTime = Date.now();
        if (currentTime - lastClickTime < 350) {
            let currentZoom = map.getZoom();
            let minZoom = map.getMinZoom();
            if (currentZoom > minZoom + 0.1) {
                // Již přiblíženo -> plynule oddálit zpět na výchozí celkový pohled
                if (map.originalMidX !== undefined && map.originalMidY !== undefined) {
                    map.setView([map.originalMidY, map.originalMidX], map.originalZoom || minZoom, { animate: true, duration: 0.25 });
                } else {
                    map.setZoom(minZoom, { animate: true, duration: 0.25 });
                }
            } else {
                // Oddáleno -> plynule přiblížit (+1.3 zoom) do středu pro detailní čtení mapy
                let targetZoom = Math.min(map.getMaxZoom() || 8, currentZoom + 1.3);
                if (map.originalMidX !== undefined && map.originalMidY !== undefined) {
                    map.setView([map.originalMidY, map.originalMidX], targetZoom, { animate: true, duration: 0.25 });
                } else {
                    map.setZoom(targetZoom, { animate: true, duration: 0.25 });
                }
            }
            lastClickTime = 0;
        } else {
            lastClickTime = currentTime;
        }
    });

    // Přizpůsobení posunu (pan / drag) pro zrotovaný kontejner mapy
    if (map.dragging && map.dragging._draggable) {
        let origDraggableOnMove = map.dragging._draggable._onMove;
        map.dragging._draggable._onMove = function (e) {
            let bearing = map._targetBearing || 0;
            if (!bearing) return origDraggableOnMove.call(this, e);
            if (e.touches && e.touches.length > 1) { this._moved = true; return; }
            let first = (e.touches && e.touches.length === 1 ? e.touches[0] : e);
            let screenOffset = new L.Point(first.clientX, first.clientY).subtract(this._startPoint);
            if (!screenOffset.x && !screenOffset.y) return;
            if (Math.abs(screenOffset.x) + Math.abs(screenOffset.y) < this.options.clickTolerance) return;

            // Rotace vektoru posunu o úhel otočení mapy, aby prst/myš posouvala mapu ve správném směru obrazovky
            let rad = -bearing * Math.PI / 180;
            let rotX = screenOffset.x * Math.cos(rad) - screenOffset.y * Math.sin(rad);
            let rotY = screenOffset.x * Math.sin(rad) + screenOffset.y * Math.cos(rad);
            let rotatedOffset = new L.Point(rotX, rotY);

            L.DomEvent.stop(e);
            if (!this._moved) {
                this.fire('dragstart');
                this._moved = true;
            }
            this._moving = true;
            this._newPos = this._startPos.add(rotatedOffset);
            L.DomUtil.setPosition(this._element, this._newPos);
            this.fire('predrag');
            this.fire('drag', e);
        };
    }

    L.control.zoom({ position: 'topleft' }).addTo(map);

    map.on('zoomend', function () {
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
                tileSize: 512, minZoom: 0, maxZoom: 8, maxNativeZoom: 6,
                noWrap: true, tms: false, keepBuffer: 4, updateWhenIdle: false, updateWhenZooming: true, detectRetina: true
            }).addTo(map);
            currentTileLayers[index] = tl;
        }

        let showVariants = showVariantsForIndex[index] || false;
        let layer = L.geoJSON(geojson, {
            filter: function (f) {
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
            let dist = Math.sqrt(dx * dx + dy * dy);
            if (dist > 0) {
                let distM = postupyData[index].dist_m || 0;
                let R = 1.10 + Math.max(0, Math.min(1, (distM - 1600) / 800)) * 0.40;
                let gap = 0.10;
                let ux = dx / dist, uy = dy / dist;
                let targetBearing = (Math.atan2(dy, dx) * 180 / Math.PI) - 90;

                const mContainer = document.getElementById(`map-${index}`);
                if (mContainer) mContainer.style.transform = `rotate(${targetBearing}deg)`;
                map._targetBearing = targetBearing;

                let lineWeight = Math.max(2, Math.min(3, 2 + dist / 150));
                let lineStart = [startCoords[0] + ux * (R + gap), startCoords[1] + uy * (R + gap)];
                let lineEnd = [endCoords[0] - ux * (R + gap), endCoords[1] - uy * (R + gap)];
                if (dist > R * 2 + gap * 2) {
                    let polyline = L.polyline([[lineStart[1], lineStart[0]], [lineEnd[1], lineEnd[0]]],
                        { color: iofPurple, weight: lineWeight, pane: 'markerPane', interactive: false });
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
                    overlays.addLayer(L.svgOverlay(svgText, boundsText, { interactive: false, pane: 'markerPane' }));
                });
            }
        }

        layer.addTo(map);
        currentLayers[index] = layer;

        if (startCoords && endCoords) {
            let w = window.innerWidth, h = window.innerHeight;
            let dx = endCoords[0] - startCoords[0], dy = endCoords[1] - startCoords[1];
            let dist = Math.sqrt(dx * dx + dy * dy);

            let targetPixelsY = h * 0.84;
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
        if (ui) ui.style.display = calibMode ? 'block' : 'none';
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
                try { await fetch(url, { cache: 'no-store' }); } catch (e) { }
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
    if (!currentUser) { alert("Pro sdílení se musíš přihlásit!"); return; }
    const postup = postupyData[index];

    // Vytvoření IG-style share sheet overlay
    let overlay = document.getElementById('share-overlay');
    let sheet = document.getElementById('share-sheet');

    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'share-overlay';
        overlay.onclick = closeShareSheet;
        document.body.appendChild(overlay);
    }

    if (!sheet) {
        sheet = document.createElement('div');
        sheet.id = 'share-sheet';
        document.body.appendChild(sheet);
    }

    // Dummy avatary kontaktů
    const contacts = [
        { name: 'Globální Chat', img: '', isGroup: true },
        { name: 'Tomas', img: 'https://i.pravatar.cc/100?img=11' },
        { name: 'Klara', img: 'https://i.pravatar.cc/100?img=5' },
        { name: 'Ondřej', img: 'https://i.pravatar.cc/100?img=12' },
        { name: 'Martin', img: 'https://i.pravatar.cc/100?img=15' },
        { name: 'Jana', img: 'https://i.pravatar.cc/100?img=9' },
    ];

    sheet.innerHTML = `
        <div class="share-sheet-handle"></div>
        <div class="share-sheet-avatars">
            ${contacts.map(c => `
                <div class="share-avatar-item" onclick="sendShareToChat(${index}, '${c.name}', ${c.isGroup || false})">
                    <div class="share-avatar-circle" style="${c.img ? 'background-image:url(' + c.img + ')' : 'display:flex; align-items:center; justify-content:center;'}">
                        ${!c.img ? '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#999" stroke-width="1.5"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>' : ''}
                    </div>
                    <div class="share-avatar-name">${c.name}</div>
                </div>
            `).join('')}
        </div>
        <div class="share-search-bar">
            <svg class="share-search-icon" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5" fill="none"><circle cx="11" cy="11" r="7"/><line x1="16.5" y1="16.5" x2="21" y2="21" stroke-linecap="round"/></svg>
            <input type="text" placeholder="Hledat">
        </div>
        <div class="share-contact-list">
            ${contacts.map(c => `
                <div class="share-contact-row">
                    <div class="share-contact-avatar" style="${c.img ? 'background-image:url(' + c.img + ')' : 'display:flex; align-items:center; justify-content:center; background:var(--secondary-bg);'}">
                        ${!c.img ? '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#999" stroke-width="1.5"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle></svg>' : ''}
                    </div>
                    <div class="share-contact-name">${c.name}</div>
                    <button class="share-contact-btn" onclick="sendShareToChat(${index}, '${c.name}', ${c.isGroup || false}); this.innerText='Odesláno'; this.classList.add('sent');">Odeslat</button>
                </div>
            `).join('')}
        </div>
    `;

    // Animace
    requestAnimationFrame(() => {
        overlay.classList.add('active');
        sheet.classList.add('active');
    });
}

function closeShareSheet() {
    const overlay = document.getElementById('share-overlay');
    const sheet = document.getElementById('share-sheet');
    if (overlay) overlay.classList.remove('active');
    if (sheet) sheet.classList.remove('active');
}

function sendShareToChat(index, targetName, isGroup) {
    const postup = postupyData[index];
    if (!postup) return;
    const basename = postup.file ? postup.file.replace('.geojson', '') : '';
    if (isGroup) {
        db.collection('global_chat').add({
            type: 'shared_route',
            routeIndex: index,
            routeId: postup.id,
            mapId: postup.map_id,
            basename: basename,
            routeName: postup.map_name || 'Homolka',
            distM: Math.round(postup.dist_m || 0),
            authorUid: currentUser ? currentUser.uid : 'anon',
            authorName: currentUser ? currentUser.displayName : (localStorage.getItem('profile_username') || 'franta14_'),
            timestamp: firebase.firestore.FieldValue.serverTimestamp()
        });
    }
    setTimeout(closeShareSheet, 600);
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
    fileInput.addEventListener('change', function (e) {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = function (event) {
                localStorage.setItem('profile_picture', event.target.result);
                renderProfileSaved();
            };
            reader.readAsDataURL(file);
        }
    });
    document.body.appendChild(fileInput);

    let savedUsername = localStorage.getItem('profile_username') || 'franta14_';
    let savedBio = localStorage.getItem('profile_bio') || t('bioDesc');

    profileContent.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; padding: 12px 16px 8px; color: inherit; border-bottom: 0.5px solid var(--border-color);">
            <div style="font-size: 20px; font-weight: 700; display:flex; align-items:center; gap: 6px; letter-spacing: -0.3px;">
                <span id="profile-username-val" contenteditable="true" spellcheck="false" class="editable-profile-field" title="Klikni pro úpravu">${savedUsername}</span>
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="opacity: 0.4; cursor: pointer;" onclick="document.getElementById('profile-username-val').focus()"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
            </div>
        </div>

        <div style="display:flex; padding: 16px 16px 12px; align-items:center;">
            <div onclick="document.getElementById('profile-pic-upload').click()" style="width: 77px; height: 77px; border-radius: 50%; background: var(--secondary-bg); overflow:hidden; flex-shrink: 0; border: 0.5px solid var(--border-color); display:flex; align-items:center; justify-content:center; cursor: pointer;">
                ${avatarContent}
            </div>
            <div style="display:flex; flex-grow: 1; justify-content: space-evenly; text-align:center;">
                <div>
                    <div style="font-weight:700; font-size:16px; color: inherit;">${videnoCislo}</div>
                    <div style="font-size:13px; color: inherit;">${t('analyzed')}</div>
                </div>
                <div>
                    <div style="font-weight:700; font-size:16px; color: inherit;">${ulozenaCislo}</div>
                    <div style="font-size:13px; color: inherit;">${t('saved')}</div>
                </div>
                <div>
                    <div id="stat-hours" style="font-weight:700; font-size:16px; color: inherit;">${hodinCislo}</div>
                    <div style="font-size:13px; color: inherit;">${t('hours')}</div>
                </div>
            </div>
        </div>
        
        <div style="padding: 0 16px 12px; font-size: 14px; color: inherit;">
            <div style="font-weight: 600; margin-bottom:2px;">František Čtrnáct</div>
            <div style="display: flex; align-items: flex-start; gap: 4px;">
                <div id="profile-bio-val" contenteditable="true" spellcheck="false" class="editable-profile-field" style="color: var(--text-secondary, #737373); font-weight: 400; line-height: 1.4; flex: 1;" title="Klikni pro úpravu">${savedBio}</div>
                <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="opacity: 0.4; cursor: pointer; flex-shrink: 0; margin-top: 3px;" onclick="document.getElementById('profile-bio-val').focus()"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
            </div>
        </div>
        <div id="profile-dynamic-content"></div>
    `;

    const uValEl = document.getElementById('profile-username-val');
    if (uValEl) {
        uValEl.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                uValEl.blur();
            }
        });
        uValEl.addEventListener('blur', () => {
            let val = uValEl.innerText.trim();
            if (!val) val = 'franta14_';
            uValEl.innerText = val;
            localStorage.setItem('profile_username', val);
            const chatHeader = document.querySelector('.chat-header-main');
            if (chatHeader) chatHeader.innerText = val;
        });
    }

    const bValEl = document.getElementById('profile-bio-val');
    if (bValEl) {
        bValEl.addEventListener('blur', () => {
            let val = bValEl.innerText.trim();
            if (!val) val = t('bioDesc');
            bValEl.innerText = val;
            localStorage.setItem('profile_bio', val);
        });
    }

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

    const terrainDisplayNames = {
        'cesko': 'Česko',
        'cesky-les': 'Česko',
        'skandinavie': 'Skandinávie',
        'madarsko': 'Maďarsko',
        'piskovce': 'Pískovce',
        'alpy': 'Alpy',
        'mesto': 'Město'
    };

    pillsContainer.appendChild(createPill('Vše', t('all')));
    uniqueTerrains.forEach(t => {
        const niceName = terrainDisplayNames[t] || (t.charAt(0).toUpperCase() + t.slice(1).replace('-', ' '));
        pillsContainer.appendChild(createPill(t, niceName));
    });
    dynamicContent.appendChild(pillsContainer);

    const gridContainer = document.createElement('div');
    gridContainer.style.display = 'grid';
    gridContainer.style.gridTemplateColumns = 'repeat(3, 1fr)';
    gridContainer.style.gap = '2px';
    gridContainer.style.width = '100%';

    const displayData = profileSelectedTerrain === 'Vše' ? savedData : savedData.filter(map => map.terrain === profileSelectedTerrain);

    displayData.forEach((route, idx) => {
        const el = document.createElement('div');
        el.className = 'explore-grid-item';
        el.style.position = 'relative';
        el.style.aspectRatio = '4 / 5';
        el.style.background = 'var(--secondary-bg)';
        el.style.overflow = 'hidden';
        el.style.cursor = 'pointer';

        const thumbRoute = route;
        let thumbSrc = '';
        let basename = '';
        if (thumbRoute.thumb) {
            thumbSrc = thumbRoute.thumb;
            basename = thumbSrc.split('/').pop().replace('.jpg', '');
        } else if (thumbRoute.file) {
            basename = thumbRoute.file.replace('.geojson', '');
            thumbSrc = 'thumbs/' + basename + '.jpg';
        } else {
            thumbSrc = 'thumbs/map_' + route.map_id + '.jpg'; // fallback
        }

        let thumbImgSrc = thumbSrc + (thumbsMeta && thumbsMeta.version ? '?v=' + thumbsMeta.version : '');
        let metaStyle = '';
        let animClass = 'animated-map-drift';
        if (thumbsMeta && thumbsMeta.routes && thumbsMeta.routes[basename]) {
            let pts = thumbsMeta.routes[basename];

            // Jednotné přiblížení pro všechny postupy (normalizované podle výřezu)
            let baseZoom = 13.0;
            let cropScale = pts.crop_scale || 0.6;
            let zoom = baseZoom * cropScale;

            let dx = pts.end[0] - pts.start[0];
            let dy = pts.end[1] - pts.start[1];
            let maxDiff = Math.max(Math.abs(dx), Math.abs(dy));

            let distance = Math.hypot(dx, dy);
            let animDur = Math.max(12, distance * 1.2); // Zpomaleno o 50% navíc: 1.2s na každý 1% bod délky

            animClass = 'animated-route-follow';
            let maskId = 'mask-' + basename + '-' + idx;

            // Už žádný drift, kolečko bude PERFEKTNĚ po celou dobu uprostřed.
            let yCorr = 0.0;

            // Kolečka zmenšena o cca 17% a tloušťka o cca 8% (r=10, stroke-width=2.8)
            let svgOverlay = `
            <svg style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; overflow: visible;">
                <defs>
                    <mask id="${maskId}">
                        <rect x="0" y="0" width="100%" height="100%" fill="white" />
                        <circle cx="${pts.start[0]}%" cy="${pts.start[1]}%" r="11" fill="black" />
                        <circle cx="${pts.end[0]}%" cy="${pts.end[1]}%" r="11" fill="black" />
                    </mask>
                </defs>
                <line x1="${pts.start[0]}%" y1="${pts.start[1]}%" x2="${pts.end[0]}%" y2="${pts.end[1]}%" stroke="#b300ff" stroke-width="2.8" stroke-opacity="0.8" stroke-linecap="round" mask="url(#${maskId})" />
                <circle cx="${pts.start[0]}%" cy="${pts.start[1]}%" r="10" stroke="#b300ff" stroke-width="2.8" fill="none" />
                <circle cx="${pts.end[0]}%" cy="${pts.end[1]}%" r="10" stroke="#b300ff" stroke-width="2.8" fill="none" />
            </svg>`;

            el.innerHTML = `
                <div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; overflow: hidden;">
                    <div class="${animClass}" style="position: absolute; top: 50%; left: 50%; width: ${zoom * 100}%; height: auto; --anim-dur: ${animDur.toFixed(1)}s; --ts-x: -${pts.start[0].toFixed(3)}%; --ts-y: -${(pts.start[1] - yCorr).toFixed(3)}%; --te-x: -${pts.end[0].toFixed(3)}%; --te-y: -${(pts.end[1] - yCorr).toFixed(3)}%;">
                        <img src="${thumbImgSrc}" alt="${route.map_name}" style="width: 100%; height: auto; display: block;">
                        ${svgOverlay}
                    </div>
                </div>
            `;
        } else {
            metaStyle = `style="position: absolute; top: 0; left: 0; width: 150%; height: 150%;"`;
            el.innerHTML = `
                <div class="${animClass}" ${metaStyle}>
                    <img src="${thumbImgSrc}" alt="${route.map_name}" style="width: 100%; height: 100%; object-fit: cover; display: block;">
                </div>
            `;
        }
        el.addEventListener('click', () => openFeed(route.map_id, true));
        gridContainer.appendChild(el);
    });
    dynamicContent.appendChild(gridContainer);
}

function openFeed(map_id, isSavedMode, specificIndex) {
    let saved = JSON.parse(localStorage.getItem('saved_postupy') || '[]');
    let savedStrings = saved.map(String);

    let firstVisibleIndex = -1;
    let groupName = postupyData.find(m => m.map_id === map_id)?.map_name || t('saved');

    if (isSavedMode) {
        document.body.classList.add('saved-mode-active');
        const header = document.getElementById('saved-mode-header');
        if (header) {
            header.innerHTML = `<svg style="width:28px; height:28px; margin-right:10px; margin-bottom:-2px;" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/></svg>`;
        }
    } else {
        document.body.classList.remove('saved-mode-active');
    }

    document.querySelectorAll('.reel').forEach(reel => {
        let mIndex = reel.dataset.index;
        let postup = postupyData[mIndex];

        let isMatch = (postup && postup.map_id === map_id);
        if (isSavedMode) {
            isMatch = isMatch && savedStrings.includes(String(postup.id));
        }

        if (isMatch) {
            reel.style.display = 'block';
            if (specificIndex !== undefined && Number(specificIndex) >= 0) {
                if (Number(mIndex) === Number(specificIndex)) firstVisibleIndex = mIndex;
            } else {
                if (firstVisibleIndex === -1) firstVisibleIndex = mIndex;
            }
        } else {
            reel.style.display = 'none';
        }
    });

    if (firstVisibleIndex === -1 && specificIndex !== undefined && Number(specificIndex) >= 0) {
        firstVisibleIndex = specificIndex;
        let tReel = document.querySelector(`.reel[data-index="${firstVisibleIndex}"]`);
        if (tReel) tReel.style.display = 'block';
    }

    if (firstVisibleIndex === -1) return;

    document.querySelectorAll('.app-screen').forEach(s => {
        if (isSavedMode && s.id === 'screen-profile') return;
        s.classList.remove('active');
    });
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));

    if (isSavedMode) {
        const profileNavBtn = document.querySelector('.nav-btn[data-target="screen-profile"]');
        if (profileNavBtn) profileNavBtn.classList.add('active');
    } else {
        const scrollNavBtn = document.querySelector('.nav-btn[data-target="screen-scroll"]');
        if (scrollNavBtn) scrollNavBtn.classList.add('active');
    }

    document.getElementById('bottom-nav').classList.add('nav-dark');

    const screenScroll = document.getElementById('screen-scroll');
    const reelsContainer = document.getElementById('reels-container');
    const targetReel = document.querySelector(`.reel[data-index="${firstVisibleIndex}"]`);

    if (isSavedMode && screenScroll) {
        // Umístíme obrazovku mimo zobrazení vpravo ještě před aktivací
        screenScroll.style.transition = 'none';
        screenScroll.style.transform = 'translateX(100%)';
        screenScroll.classList.add('active');

        if (targetReel && reelsContainer) {
            reelsContainer.scrollTo({ top: targetReel.offsetTop, behavior: 'instant' });
        }

        const activeMap = mapInstances[firstVisibleIndex];
        if (activeMap) {
            activeMap.invalidateSize();
            if (activeMap.originalMidX !== undefined) {
                activeMap.setView([activeMap.originalMidY, activeMap.originalMidX], activeMap.originalZoom, { animate: false });
            }
        }
        activateReel(firstVisibleIndex);

        // Double RAF zaručí vykreslení počáteční pozice (100%) a plynulý přejezd doleva na (0)
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                screenScroll.style.transition = 'transform 0.28s cubic-bezier(0.25, 1, 0.5, 1)';
                screenScroll.style.transform = 'translateX(0)';

                setTimeout(() => {
                    screenScroll.style.transition = '';
                    screenScroll.style.transform = '';
                    // Dodatečný přepočet ostatních map až po dokončení animace
                    Object.values(mapInstances).forEach(m => {
                        if (m !== activeMap) m.invalidateSize();
                    });
                }, 300);
            });
        });
    } else if (screenScroll) {
        screenScroll.style.transition = '';
        screenScroll.style.transform = '';
        screenScroll.classList.add('active');

        if (targetReel && reelsContainer) {
            setTimeout(() => {
                reelsContainer.scrollTo({ top: targetReel.offsetTop, behavior: 'instant' });
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
}

function closeSavedFeed(isAlreadyAnimatedOut = false) {
    const doClose = () => {
        document.body.classList.remove('saved-mode-active');
        updateExploreBadge(document.getElementById('nav-badge'));

        document.querySelectorAll('.app-screen').forEach(s => {
            if (s.id !== 'screen-profile') s.classList.remove('active');
        });
        document.getElementById('screen-profile').classList.add('active');

        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        const profileNavBtn = document.querySelector('.nav-btn[data-target="screen-profile"]');
        if (profileNavBtn) profileNavBtn.classList.add('active');
        document.getElementById('bottom-nav').classList.remove('nav-dark');

        const screenScroll = document.getElementById('screen-scroll');
        if (screenScroll) {
            screenScroll.style.transform = '';
            screenScroll.style.transition = '';
            screenScroll.classList.remove('slide-out-right');
            screenScroll.classList.remove('slide-in-right');
        }
    };

    if (isAlreadyAnimatedOut === true) {
        doClose();
    } else {
        const screenScroll = document.getElementById('screen-scroll');
        if (screenScroll) {
            screenScroll.style.transition = 'transform 0.28s cubic-bezier(0.25, 1, 0.5, 1)';
            screenScroll.style.transform = 'translateX(100%)';
            setTimeout(doClose, 280);
        } else {
            doClose();
        }
    }
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

    groups.forEach((group, idx) => {
        const el = document.createElement('div');
        el.className = 'explore-grid-item';
        el.style.aspectRatio = '4 / 5';
        el.style.overflow = 'hidden';
        el.style.cursor = 'pointer';
        el.style.position = 'relative';

        const countText = getRoutesCountText(group.routes.length);

        // Získání metadat mapy (cesta a automatický drift z pipeline)
        let mapMeta = (thumbsMeta && thumbsMeta.maps && thumbsMeta.maps[group.map_id]) ? thumbsMeta.maps[group.map_id] : null;
        let thumbPath = (mapMeta && typeof mapMeta === 'object' && mapMeta.thumb)
            ? mapMeta.thumb
            : ('thumbs/map_' + group.map_id + '.jpg');
        const thumbVersion = (thumbsMeta && thumbsMeta.version) ? `?v=${thumbsMeta.version}` : '';
        const thumbSrc = thumbPath + thumbVersion;

        // 1. Priorita: Manuální override z ANIMATION_CONFIG (pokud existuje)
        // 2. Priorita: Automatický bezpečný výpočet z thumbs_meta.json
        let b = null;
        if (window.ANIMATION_CONFIG && window.ANIMATION_CONFIG.exploreMaps && window.ANIMATION_CONFIG.exploreMaps[group.map_id]) {
            b = window.ANIMATION_CONFIG.exploreMaps[group.map_id];
        } else if (mapMeta && typeof mapMeta === 'object' && mapMeta.drift) {
            b = mapMeta.drift;
        }

        // Pomalé, elegantní a plynulé časování (zrychleno o 15 %): každá dlaždice má lehce odlišnou periodu a fázový posun,
        // aby nepůsobily synchronizovaně a pohyb byl přirozený.
        const baseDur = 72;
        const dur = baseDur + (idx % 4) * 10; // např. 72s, 82s, 92s, 102s
        const delay = -((idx * 27) % baseDur);

        let driftVars = `--drift-dur: ${dur}s; --drift-delay: ${delay}s;`;
        if (b) {
            driftVars += ` --drift-start-x: ${b.startX}%; --drift-start-y: ${b.startY}%; --drift-mid-x: ${b.midX}%; --drift-mid-y: ${b.midY}%; --drift-end-x: ${b.endX}%; --drift-end-y: ${b.endY}%;`;
        }

        const zoom = (b && b.zoom) ? b.zoom : 700;
        const driftStyle = `style="position: absolute; top: 0; left: 0; width: ${zoom}%; height: ${zoom}%; ${driftVars}"`;

        el.innerHTML = `
            <div class="animated-map-drift" ${driftStyle}>
                <img src="${thumbSrc}" alt="${group.map_name}" style="width: 100%; height: 100%; object-fit: cover; display: block; image-rendering: -webkit-optimize-contrast;" loading="lazy">
            </div>
            <div style="position:absolute; bottom:0; left:0; width:100%; background:linear-gradient(to top, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.3) 70%, transparent 100%); color:#fff; font-size:13px; padding:12px 8px 8px 8px; box-sizing:border-box; z-index: 1000;">
                <div style="font-weight:700; text-shadow: 1px 1px 2px rgba(0,0,0,0.8);">${group.map_name}</div>
                <div style="font-size:10px; font-weight:600; color:#ddd; margin-top:2px;">${countText}</div>
            </div>
        `;
        el.addEventListener('click', () => openFeed(group.map_id, false));
        container.appendChild(el);
    });
}
