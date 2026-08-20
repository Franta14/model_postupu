let postupyData = [];
let geojsonCache = {};
let mapInstances = {}; // stores { index: L.map }
let currentLayers = {}; // stores { index: L.geoJSON }
let currentOverlays = {}; // stores { index: L.featureGroup }
let currentTileLayers = {}; // stores { index: L.tileLayer }

const iofPurple = "#b300ff";

document.addEventListener("DOMContentLoaded", () => {
    // Monkey-patch pro správné posouvání mapy při CSS rotaci
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
                    
                    this._newPos = new L.Point(
                        this._startPos.x + dx_local,
                        this._startPos.y + dy_local
                    );
                }
            }
        }
        originalUpdatePosition.call(this);
    };

    // panBy patch was removed because it caused internal coordinate desync during setView

    loadData();
});

function loadData() {
    fetch('postupy/postupy_index.json?v=' + Date.now())
        .then(res => res.json())
        .then(data => {
            postupyData = data;
            buildReels();
            setupObserver();
            
            setTimeout(() => {
                document.getElementById('loader').style.opacity = 0;
                setTimeout(() => document.getElementById('loader').remove(), 500);
            }, 500);
        })
        .catch(err => {
            alert("Chyba při načítání dat: " + err);
        });
}

function buildReels() {
    const container = document.getElementById('reels-container');
    container.innerHTML = '';
    
    postupyData.forEach((postup, index) => {
        const reel = document.createElement('div');
        reel.className = 'reel';
        reel.dataset.index = index;

        reel.innerHTML = `
            <div class="map-clip" id="clip-${index}">
                <div class="map-container" id="map-${index}"></div>
            </div>
            <div class="reel-ui">
                <div class="reel-header">
                    <div class="reel-subtitle">${postup.dist_m.toFixed(0)} m vzdušně</div>
                    <button class="btn-primary" onclick="toggleVariants(${index})"><svg class="btn-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M4 6h16M4 12h16M4 18h16" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" fill="none"/></svg>Volby</button>
                </div>
            </div>
        `;
        
        container.appendChild(reel);
    });
}

let scrollTimeout = null;
function setupObserver() {
    let options = {
        root: document.getElementById('app'),
        rootMargin: '0px',
        threshold: 0.5
    };
    let observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const index = entry.target.dataset.index;
                if (scrollTimeout) clearTimeout(scrollTimeout);
                scrollTimeout = setTimeout(() => {
                    activateReel(index);
                }, 250);
            }
        });
    }, options);
    
    document.querySelectorAll('.reel').forEach(reel => {
        observer.observe(reel);
    });
}

let showVariantsForIndex = {};
let isPanelOpen = false;
let activeIndex = -1;

function toggleVariants(index) {
    const panel = document.getElementById('global-variants-panel');
    const content = document.getElementById('global-variants-content');
    
    if (isPanelOpen) {
        panel.classList.remove('active');
        panel.classList.remove('collapsed');
        isPanelOpen = false;
        showVariantsForIndex[index] = false;
    } else {
        const postup = postupyData[index];
        content.innerHTML = postup.variants.map(v => `
            <div class="variant-item">
                <div class="variant-color" style="background-color: ${v.color}; color: ${v.color}"></div>
                <div class="variant-stats">
                    <div class="variant-main">V${v.id} • ${Math.floor(v.cas_s/60)}:${(v.cas_s%60).toString().padStart(2,'0')}</div>
                    <div class="variant-sub">${v.vzdal_m.toFixed(0)}m • ${v.prevyseni_m.toFixed(0)}m↑<br>${v.tempo_str}</div>
                </div>
            </div>
        `).join('');
        
        let panelClass = 'pos-top-right'; // default
        if (geojsonCache[postup.file]) {
            let startC = null, endC = null;
            geojsonCache[postup.file].features.forEach(f => {
                if (f.properties && f.properties.type === 'start') startC = f.geometry.coordinates;
                if (f.properties && f.properties.type === 'end') endC = f.geometry.coordinates;
            });
            if (startC && endC) {
                let dx = endC[0] - startC[0];
                let dy = endC[1] - startC[1];
                let dist = Math.sqrt(dx*dx + dy*dy);
                if (dist > 0) {
                    let ux = dx / dist;
                    let uy = dy / dist;
                    let vx = -uy; // kolmice (ukazuje vlevo na obrazovce po rotaci)
                    let vy = ux;
                    
                    let maxLeftTop = 0, maxRightTop = 0;
                    let maxLeftBot = 0, maxRightBot = 0;
                    
                    geojsonCache[postup.file].features.forEach(f => {
                        if (f.properties && f.properties.type === 'variant' && f.geometry.type === 'LineString') {
                            f.geometry.coordinates.forEach(c => {
                                let px = c[0] - startC[0];
                                let py = c[1] - startC[1];
                                let localY = px * ux + py * uy; // 0 u startu, dist u cíle
                                let localX = px * vx + py * vy; // kladné je vlevo, záporné vpravo na obrazovce
                                
                                if (localY > dist * 0.6) { // Měříme jen v horních 40 % obrazovky (tam kde fyzicky tabulka je)
                                    if (localX > maxLeftTop) maxLeftTop = localX;
                                    if (-localX > maxRightTop) maxRightTop = -localX;
                                } else if (localY < dist * 0.4) { // Měříme jen v dolních 40 % obrazovky
                                    if (localX > maxLeftBot) maxLeftBot = localX;
                                    if (-localX > maxRightBot) maxRightBot = -localX;
                                }
                            });
                        }
                    });
                    
                    // Hodnoty reprezentují, jak moc do daného rohu varianty zasahují.
                    // Vybereme roh s nejmenším zásahem.
                    let bulges = [
                        { corner: 'pos-top-left', val: maxLeftTop },
                        { corner: 'pos-top-right', val: maxRightTop },
                        { corner: 'pos-bottom-left', val: maxLeftBot },
                        { corner: 'pos-bottom-right', val: maxRightBot }
                    ];
                    bulges.sort((a, b) => a.val - b.val);
                    panelClass = bulges[0].corner;
                }
            }
        }
        
        panel.className = 'variants-panel ' + panelClass;
        void panel.offsetWidth; // force reflow
        
        document.getElementById('global-toggle-btn').innerHTML = '<svg class="toggle-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>';
        document.getElementById('global-toggle-btn').onclick = () => {
            panel.classList.toggle('collapsed');
        };
        
        panel.classList.remove('collapsed'); // always start expanded
        panel.classList.add('active');
        isPanelOpen = true;
        showVariantsForIndex[index] = true;
    }
    
    // redraw active map
    const postup = postupyData[index];
    if (geojsonCache[postup.file]) {
        renderMapData(index, geojsonCache[postup.file]);
    }
}

function activateReel(indexStr) {
    const index = parseInt(indexStr);
    
    // Zruš panel při přechodu na jiný reel
    if (activeIndex !== index) {
        if (isPanelOpen) {
            const panel = document.getElementById('global-variants-panel');
            panel.classList.remove('active');
            panel.classList.remove('collapsed');
            isPanelOpen = false;
            showVariantsForIndex[activeIndex] = false;
            
            // hide variants on previous map
            const prevPostup = postupyData[activeIndex];
            if (prevPostup && geojsonCache[prevPostup.file]) {
                renderMapData(activeIndex, geojsonCache[prevPostup.file]);
            }
        }
        activeIndex = index;
    }
    
    preloadReel(index);
    
    // O chytré předvykreslení (smart preloading) se teď stará událost 'load'
    // přímo na L.tileLayer v renderMapData, takže se další mapa začne stahovat
    // až ve chvíli, kdy má uživatel ostrou mapu před sebou.
}

function preloadReel(i) {
    if (i < 0 || i >= postupyData.length) return;
    
    if (!mapInstances[i]) {
        initMapForReel(i);
    }
    
    const postup = postupyData[i];
    if (geojsonCache[postup.file]) {
        if (!currentLayers[i]) {
            renderMapData(i, geojsonCache[postup.file]);
        }
    } else {
        fetch('postupy/' + postup.file + '?v=' + Date.now())
            .then(res => res.json())
            .then(geojson => {
                geojsonCache[postup.file] = geojson;
                if (!currentLayers[i]) {
                    renderMapData(i, geojson);
                }
            })
            .catch(err => console.error("GeoJSON load error:", err));
    }
}

// Hack to force Leaflet to always pick the higher integer zoom level for tiles
// This ensures downscaling (sharper) instead of upscaling (blurry) during fractional zoom.
const originalSetView = L.GridLayer.prototype._setView;
L.GridLayer.prototype._setView = function (center, zoom, noPrune, noUpdate) {
    let oldRound = Math.round;
    // Cílený hack: změníme Math.round na Math.ceil POUZE pro hodnotu zoomu,
    // čímž zabráníme nechtěnému posunu (rozhození) pixelové mřížky mapy (pixelOrigin).
    Math.round = function(val) {
        if (val === zoom) return Math.ceil(val);
        return oldRound(val);
    };
    try {
        originalSetView.call(this, center, zoom, noPrune, noUpdate);
    } finally {
        Math.round = oldRound;
    }
};

function initMapForReel(index) {
    const map = L.map(`map-${index}`, {
        crs: L.CRS.Simple,
        minZoom: 0,
        maxZoom: 8,
        zoomSnap: 0,
        zoomControl: false,
        gestureHandling: false,
        inertia: false
    });
    
    map.createPane('maskPane');
    map.getPane('maskPane').style.zIndex = 250; // Nad dlaždicemi (200), pod overlay (400)
    
    L.control.zoom({ position: 'topleft' }).addTo(map);
    // Tile layer se přidá až v renderMapData — potřebujeme GeoJSON data pro ořez
    
    map.on('zoomend', updateCalibrationShift);
    mapInstances[index] = map;
}

function renderMapData(index, geojsonOriginal) {
    try {
        const map = mapInstances[index];
        if (!map) return;
    
    if (currentLayers[index]) {
        map.removeLayer(currentLayers[index]);
    }
    if (currentOverlays[index]) {
        map.removeLayer(currentOverlays[index]);
    }
    
    let geojson = JSON.parse(JSON.stringify(geojsonOriginal));
    let overlays = L.featureGroup().addTo(map);
    currentOverlays[index] = overlays;
    
    let startCoords = null;
    let endCoords = null;
    
    // Sesbírat VŠECHNY souřadnice pro výpočet bounding boxu
    let allLngs = [], allLats = [];
    geojson.features.forEach(f => {
        if (f.properties && f.properties.type === 'start') startCoords = f.geometry.coordinates;
        if (f.properties && f.properties.type === 'end') endCoords = f.geometry.coordinates;
        
        if (f.geometry.type === 'Point') {
            allLngs.push(f.geometry.coordinates[0]);
            allLats.push(f.geometry.coordinates[1]);
        } else if (f.geometry.type === 'LineString') {
            f.geometry.coordinates.forEach(c => { allLngs.push(c[0]); allLats.push(c[1]); });
        }
    });
    
    // Tile layer s ořezem na bounding box postupu + 30% margin
    if (!currentTileLayers[index] && allLngs.length > 0) {
        let minLng = Math.min(...allLngs), maxLng = Math.max(...allLngs);
        let minLat = Math.min(...allLats), maxLat = Math.max(...allLats);
        let marginLng = Math.max(100, (maxLng - minLng) * 0.50);
        let marginLat = Math.max(100, (maxLat - minLat) * 0.50);
        let tileBounds = [
            [minLat - marginLat, minLng - marginLng],
            [maxLat + marginLat, maxLng + marginLng]
        ];
        
        // Zabrání odjetí mapy do bílého prázdna
        map.setMaxBounds(tileBounds);
        
        let tl = L.tileLayer('tiles/{z}/{x}/{y}.png', {
            tileSize: 512,
            minZoom: 0,
            maxZoom: 8,
            maxNativeZoom: 5,
            noWrap: true,
            tms: false,
            keepBuffer: 4,
            updateWhenIdle: false,
            updateWhenZooming: true,
            detectRetina: true
        }).addTo(map);
        currentTileLayers[index] = tl;
        
        // Smart Preloading: pokud je tohle aktivní postup,
        // počkejme na stažení všech dlaždic, a teprve PAK začněme stahovat
        // na pozadí dlaždice pro následující postup. Zabrání to síťové zácpě.
        if (index === activeIndex) {
            tl.once('load', () => {
                preloadReel(index + 1);
                preloadReel(index - 1);
            });
            // Bezpečnostní pojistka: pokud by se událost neodpálila (např. vše je v cache)
            setTimeout(() => {
                preloadReel(index + 1);
                preloadReel(index - 1);
            }, 500);
        }
    }
    
    
    let showVariants = showVariantsForIndex[index] || false;

    let layer = L.geoJSON(geojson, {
        filter: function(feature) {
            if (feature.properties && feature.properties.type === 'variant' && !showVariants) return false;
            if (feature.properties && ['start', 'end', 'spojnice'].includes(feature.properties.type)) return false;
            return true;
        },
        style: function (feature) {
            if (feature.properties && feature.properties.type === 'variant') {
                return { color: feature.properties.color, weight: 6, opacity: 0.8, lineCap: 'round', lineJoin: 'round' };
            }
            if (feature.properties && feature.properties.type === 'spojnice') {
                return { color: iofPurple, weight: 3, opacity: 0.8, lineCap: 'round', lineJoin: 'round' };
            }
        },
    });
    
    if (startCoords && endCoords) {
        let dx = endCoords[0] - startCoords[0];
        let dy = endCoords[1] - startCoords[1];
        let dist = Math.sqrt(dx*dx + dy*dy);
        if (dist > 0) {
            // R: Dvojnásobek oproti předchozímu stavu, protože jsme zjemnili mapovou mřížku (scale z 32 na 16)
            let distM = postupyData[index].dist_m || 0;
            let R = 1.10 + Math.max(0, Math.min(1, (distM - 1600) / 800)) * 0.40; 
            let gap = 0.10;
            let ux = dx / dist;
            let uy = dy / dist;
            let targetBearing = (Math.atan2(dy, dx) * 180 / Math.PI) - 90;
            document.getElementById(`map-${index}`).style.transform = `rotate(${targetBearing}deg)`;
            let lineWeight = Math.max(2, Math.min(3, 2 + dist / 150));
            let lineStart = [startCoords[0] + ux * (R + gap), startCoords[1] + uy * (R + gap)];
            let lineEnd = [endCoords[0] - ux * (R + gap), endCoords[1] - uy * (R + gap)];
            if (dist > R*2 + gap*2) {
                let polyline = L.polyline([
                    [lineStart[1], lineStart[0]],
                    [lineEnd[1], lineEnd[0]]
                ], {color: iofPurple, weight: lineWeight, pane: 'markerPane', interactive: false});
                layer.addLayer(polyline);
            }
            [startCoords, endCoords].forEach((coords, idx) => {
                let num = idx === 0 ? "1" : "2";
                // 1. L.circle — matematicky dokonalá kružnice, přidaná do stejné vrstvy jako spojnice
                layer.addLayer(L.circle([coords[1], coords[0]], {
                    radius: R,
                    color: iofPurple,
                    weight: lineWeight,
                    fill: false,
                    pane: 'markerPane',
                    interactive: false
                }));
                
                // 2. Text Overlay (Offset)
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
        let w = window.innerWidth;
        let h = window.innerHeight; // full screen, no bottom bar in map
        
        let dx = endCoords[0] - startCoords[0];
        let dy = endCoords[1] - startCoords[1];
        let dist = Math.sqrt(dx*dx + dy*dy);
        
        // Cílová délka postupu na obrazovce v pixelech (změněno na 70% pro větší rezervu nad a pod)
        let targetPixelsY = h * 0.70;
        let idealZoom = 0;
        if (dist > 0) {
            idealZoom = Math.log2(targetPixelsY / dist);
        }
        
        let HARD_MIN_ZOOM = 0; 
        let maxZoom = map.getMaxZoom() || 8;
        idealZoom = Math.max(HARD_MIN_ZOOM, Math.min(maxZoom, idealZoom));
        
        let midX = (startCoords[0] + endCoords[0]) / 2;
        let midY = (startCoords[1] + endCoords[1]) / 2;
        
        map.setMinZoom(idealZoom);
        
        // === VÝPOČET CHYTRÉ MASKY ===
        let ux = dx / dist;
        let uy = dy / dist;
        let vx = -uy; // kolmice
        let vy = ux;
        let maxAbsX = 0;
        
        // Zjistit, jak daleko od osy jsou varianty
        allLngs.forEach((lng, idx) => {
            let px = lng - midX;
            let py = allLats[idx] - midY;
            let localX = px * vx + py * vy;
            if (Math.abs(localX) > maxAbsX) {
                maxAbsX = Math.abs(localX);
            }
        });
        
        let pixelScale = Math.pow(2, idealZoom); // Převod z mapových jednotek na pixely displeje na úvodním zoomu
        
        // Polovina šířky/výšky displeje v mapových jednotkách
        let screenHalfW = (w / 2) / pixelScale;
        let screenHalfH = (h / 2) / pixelScale;
        
        // Rozměry postupu včetně rezervy (60px šířka, 80px výška na displeji)
        let routeHalfW = maxAbsX + (60 / pixelScale);
        let routeHalfH = (dist / 2) + (80 / pixelScale);
        
        // Díra musí pokrýt displej, ale i celou trasu s rezervou
        let holeHalfW = Math.max(screenHalfW, routeHalfW);
        let holeHalfH = Math.max(screenHalfH, routeHalfH);
        
        // 4 rohy vnitřní díry (v mapových souřadnicích)
        let p1x = midX + ux * holeHalfH + vx * holeHalfW;
        let p1y = midY + uy * holeHalfH + vy * holeHalfW;
        
        let p2x = midX + ux * holeHalfH - vx * holeHalfW;
        let p2y = midY + uy * holeHalfH - vy * holeHalfW;
        
        let p3x = midX - ux * holeHalfH - vx * holeHalfW;
        let p3y = midY - uy * holeHalfH - vy * holeHalfW;
        
        let p4x = midX - ux * holeHalfH + vx * holeHalfW;
        let p4y = midY - uy * holeHalfH + vy * holeHalfW;
        
        // Ring pro Leaflet Polygon (formát [Lat, Lng] tedy [Y, X])
        let innerRing = [
            [p1y, p1x],
            [p2y, p2x],
            [p3y, p3x],
            [p4y, p4x]
        ];
        
        // Obrovský čtverec tvořící vnější hranu masky (pokryje celou mapu)
        let outerRing = [
            [-50000, -50000],
            [-50000, 50000],
            [50000, 50000],
            [50000, -50000]
        ];
        
        // Vykreslení masky (polygon s dírou)
        let mask = L.polygon([outerRing, innerRing], {
            color: 'transparent',
            fillColor: '#ffffff',
            fillOpacity: 1.0,
            interactive: false,
            pane: 'maskPane'
        });
        overlays.addLayer(mask);
        // === KONEC VÝPOČTU MASKY ===
        
        setTimeout(() => {
            map.invalidateSize();
            map.setView([midY, midX], idealZoom, {
                animate: false
            });
        }, 50);
    }
    } catch (e) {
        alert("renderMapData Error at index " + index + ": " + e.message + "\nStack: " + e.stack);
    }
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
    let shiftXConfig = calibX - 400;
    let shiftYConfig = calibY - (-300);
    let scale = Math.pow(2, map.getZoom()) / 64;
    pane.style.marginLeft = (shiftXConfig * scale) + 'px';
    pane.style.marginTop = (shiftYConfig * scale) + 'px';
}

// === OFFLINE SYNC ===
async function startOfflineSync() {
    if (!('serviceWorker' in navigator)) {
        alert("Offline režim není podporován (chybí Service Worker). Ujistěte se, že používáte HTTPS.");
        return;
    }
    
    const overlay = document.getElementById('sync-progress');
    const bar = document.getElementById('sync-bar');
    const text = document.getElementById('sync-text');
    const btn = document.getElementById('offline-sync-btn');
    
    overlay.classList.add('active');
    
    try {
        let urlsToFetch = [];
        urlsToFetch.push('postupy/postupy_index.json');
        
        postupyData.forEach(p => {
            urlsToFetch.push('postupy/' + p.file);
        });
        
        text.innerText = "Získávám index dlaždic...";
        let tilesResponse = await fetch('tiles_index.json?v=' + Date.now());
        if (tilesResponse.ok) {
            let tiles = await tilesResponse.json();
            urlsToFetch = urlsToFetch.concat(tiles);
        } else {
            console.warn("tiles_index.json nenalezen, dlaždice nebudou staženy.");
        }
        
        let total = urlsToFetch.length;
        let done = 0;
        
        // Fetch in chunks of 20 to avoid exhausting connection pool
        const chunkSize = 20;
        for (let i = 0; i < total; i += chunkSize) {
            let chunk = urlsToFetch.slice(i, i + chunkSize);
            await Promise.all(chunk.map(async (url) => {
                try {
                    // SW will intercept this and put it in cache automatically
                    let res = await fetch(url, { cache: 'no-store' }); 
                } catch(e) {
                    console.error("Failed to fetch", url, e);
                }
                done++;
            }));
            
            let percent = Math.floor((done / total) * 100);
            bar.style.width = percent + '%';
            text.innerText = `${done} / ${total}`;
        }
        
        setTimeout(() => {
            overlay.classList.remove('active');
            btn.innerHTML = '<svg class="sync-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M5 13l4 4L19 7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>';
            btn.style.background = "var(--bg-color)";
            btn.onclick = null;
        }, 500);
        
    } catch (err) {
        alert("Chyba při stahování: " + err.message);
        overlay.classList.remove('active');
    }
}

// === SPA ROUTER A LOGIKA VÝBĚRU ===

let appState = {
    selectedTerrains: ['*'] // Výchozí: Náhodný mix
};

document.addEventListener("DOMContentLoaded", () => {
    // 1. Spodní navigace
    const navButtons = document.querySelectorAll('.nav-btn');
    const screens = document.querySelectorAll('.app-screen');

    navButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const targetId = btn.getAttribute('data-target');
            
            // Přepnutí tlačítek
            navButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Přepnutí obrazovek
            screens.forEach(screen => {
                if (screen.id === targetId) {
                    screen.classList.add('active');
                } else {
                    screen.classList.remove('active');
                }
            });
        });
    });

    // 2. Logika karet terénů (IG Grid)
    const igSquares = document.querySelectorAll('.ig-square');
    const navBadge = document.getElementById('nav-badge');

    function updateBadge() {
        const selectedCount = document.querySelectorAll('.ig-square.selected').length;
        if (selectedCount > 0) {
            navBadge.innerText = selectedCount;
            navBadge.style.display = 'flex';
        } else {
            navBadge.style.display = 'none';
        }
        
        if (selectedCount === 0) {
            appState.selectedTerrains = ['*'];
        } else {
            appState.selectedTerrains = Array.from(document.querySelectorAll('.ig-square.selected'))
                .map(sq => sq.getAttribute('data-terrain'));
        }
    }

    igSquares.forEach(square => {
        square.addEventListener('click', () => {
            square.classList.toggle('selected');
            updateBadge();
        });
    });
    
    updateBadge();
});
