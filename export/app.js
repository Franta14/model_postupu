let postupyData = [];
let geojsonCache = {};
let mapInstances = {}; 
let currentLayers = {}; 
let currentOverlays = {}; 
let currentTileLayers = {}; 

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

    loadData();

    // 1. Spodní navigace a Router
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
                    // Když otevřeme profil, vykreslíme uložené položky
                    if (targetId === 'screen-profile') {
                        renderProfileSaved();
                    }
                } else {
                    screen.classList.remove('active');
                }
            });
        });
    });

    // 2. Podpora pro klikání na záložky uvnitř Profilu (např. Uložené)
    const profileTabs = document.querySelectorAll('#screen-profile .profile-tab, #screen-profile .tab-item');
    if (profileTabs.length > 0) {
        profileTabs.forEach(tab => {
            tab.addEventListener('click', () => {
                profileTabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                renderProfileSaved(); // Znovunačtení gridu při překliknutí
            });
        });
    }
});

const TERRAINS = ['cesky-les', 'skandinavie', 'madarsko', 'piskovce', 'alpy', 'mesto'];
let selectedTerrains = new Set();

function loadData() {
    fetch('postupy/postupy_index.json?v=' + Date.now())
        .then(res => res.json())
        .then(data => {
            postupyData = data;
            // DUMMY: Assign a terrain to each map for demonstration purposes
            postupyData.forEach((map, index) => {
                map.terrain = TERRAINS[index % TERRAINS.length];
            });
            
            buildReels();
            setupObserver();
            renderExploreGrid();
            setupExploreStories();
            
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
    
    // Načteme uložené stavy z paměti
    let saved = JSON.parse(localStorage.getItem('saved_postupy') || '[]');
    
    postupyData.forEach((postup, index) => {
        const reel = document.createElement('div');
        reel.className = 'reel';
        reel.dataset.index = index;
        reel.dataset.terrain = postup.terrain; 

        const isSaved = saved.includes(postup.id);
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
        
        let panelClass = 'pos-top-right';
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
                    let vx = -uy; 
                    let vy = ux;
                    
                    let maxLeftTop = 0, maxRightTop = 0;
                    let maxLeftBot = 0, maxRightBot = 0;
                    
                    geojsonCache[postup.file].features.forEach(f => {
                        if (f.properties && f.properties.type === 'variant' && f.geometry.type === 'LineString') {
                            f.geometry.coordinates.forEach(c => {
                                let px = c[0] - startC[0];
                                let py = c[1] - startC[1];
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
                    
                    let bulges = [
                        { corner: 'pos-top-left', val: maxLeftTop },
                        { corner: 'pos-top-right', val: maxRightTop },
                        { corner: 'pos-bottom-left', val: maxLeftBot }
                    ];
                    bulges.sort((a, b) => a.val - b.val);
                    panelClass = bulges[0].corner;
                }
            }
        }
        
        panel.className = 'variants-panel ' + panelClass;
        void panel.offsetWidth; 
        
        document.getElementById('global-toggle-btn').innerHTML = '<svg class="toggle-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>';
        document.getElementById('global-toggle-btn').onclick = () => {
            panel.classList.toggle('collapsed');
        };
        
        panel.classList.remove('collapsed'); 
        panel.classList.add('active');
        isPanelOpen = true;
        showVariantsForIndex[index] = true;
    }
    
    const postup = postupyData[index];
    if (geojsonCache[postup.file]) {
        renderMapData(index, geojsonCache[postup.file]);
    }
}

function activateReel(indexStr) {
    const index = parseInt(indexStr);
    
    if (activeIndex !== index) {
        if (isPanelOpen) {
            const panel = document.getElementById('global-variants-panel');
            panel.classList.remove('active');
            panel.classList.remove('collapsed');
            isPanelOpen = false;
            showVariantsForIndex[activeIndex] = false;
            
            const prevPostup = postupyData[activeIndex];
            if (prevPostup && geojsonCache[prevPostup.file]) {
                renderMapData(activeIndex, geojsonCache[prevPostup.file]);
            }
        }
        activeIndex = index;
    }
    
    preloadReel(index);
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

const originalSetView = L.GridLayer.prototype._setView;
L.GridLayer.prototype._setView = function (center, zoom, noPrune, noUpdate) {
    let oldRound = Math.round;
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
    map.getPane('maskPane').style.zIndex = 250; 
    
    map.doubleClickZoom.disable();
    
    let lastClickTime = 0;
    map.on('click', function(e) {
        let currentTime = Date.now();
        if (currentTime - lastClickTime < 400) {
            let currentZoom = map.getZoom();
            let minZoom = map.getMinZoom();
            if (currentZoom > minZoom + 0.05) {
                if (map.originalMidX !== undefined && map.originalMidY !== undefined) {
                    map.setView([map.originalMidY, map.originalMidX], map.originalZoom || minZoom);
                } else {
                    map.setZoom(minZoom);
                }
            } else {
                let btn = document.querySelector(`.reel[data-index="${index}"] .like-btn`);
                if (btn && !btn.classList.contains('liked')) {
                    toggleLike(index, btn);
                } else {
                    triggerLikeAnimation(index);
                }
            }
            lastClickTime = 0; 
        } else {
            lastClickTime = currentTime;
        }
    });

    L.control.zoom({ position: 'topleft' }).addTo(map);
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
    
    if (!currentTileLayers[index] && allLngs.length > 0) {
        let minLng = Math.min(...allLngs), maxLng = Math.max(...allLngs);
        let minLat = Math.min(...allLats), maxLat = Math.max(...allLats);
        let marginLng = Math.max(100, (maxLng - minLng) * 0.50);
        let marginLat = Math.max(100, (maxLat - minLat) * 0.50);
        let tileBounds = [
            [minLat - marginLat, minLng - marginLng],
            [maxLat + marginLat, maxLng + marginLng]
        ];
        
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
        
        if (index === activeIndex) {
            tl.once('load', () => {
                preloadReel(index + 1);
                preloadReel(index - 1);
            });
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
                layer.addLayer(L.circle([coords[1], coords[0]], {
                    radius: R,
                    color: iofPurple,
                    weight: lineWeight,
                    fill: false,
                    pane: 'markerPane',
                    interactive: false
                }));
                
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
        let h = window.innerHeight; 
        
        let dx = endCoords[0] - startCoords[0];
        let dy = endCoords[1] - startCoords[1];
        let dist = Math.sqrt(dx*dx + dy*dy);
        
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
        
        let ux = dx / dist;
        let uy = dy / dist;
        let vx = -uy; 
        let vy = ux;
        let maxAbsX = 0;
        
        allLngs.forEach((lng, idx) => {
            let px = lng - midX;
            let py = allLats[idx] - midY;
            let localX = px * vx + py * vy;
            if (Math.abs(localX) > maxAbsX) {
                maxAbsX = Math.abs(localX);
            }
        });
        
        let pixelScale = Math.pow(2, idealZoom); 
        
        let screenHalfW = (w / 2) / pixelScale;
        let screenHalfH = (h / 2) / pixelScale;
        
        let routeHalfW = maxAbsX + (60 / pixelScale);
        let routeHalfH = (dist / 2) + (80 / pixelScale);
        
        let holeHalfW = Math.max(screenHalfW, routeHalfW);
        let holeHalfH = Math.max(screenHalfH, routeHalfH);
        
        let p1x = midX + ux * holeHalfH + vx * holeHalfW;
        let p1y = midY + uy * holeHalfH + vy * holeHalfW;
        
        let p2x = midX + ux * holeHalfH - vx * holeHalfW;
        let p2y = midY + uy * holeHalfH - vy * holeHalfW;
        
        let p3x = midX - ux * holeHalfH - vx * holeHalfW;
        let p3y = midY - uy * holeHalfH - vy * holeHalfW;
        
        let p4x = midX - ux * holeHalfH + vx * holeHalfW;
        let p4y = midY - uy * holeHalfH + vy * holeHalfW;
        
        let innerRing = [
            [p1y, p1x],
            [p2y, p2x],
            [p3y, p3x],
            [p4y, p4x]
        ];
        
        let outerRing = [
            [-50000, -50000],
            [-50000, 50000],
            [50000, 50000],
            [50000, -50000]
        ];
        
        let mask = L.polygon([outerRing, innerRing], {
            color: 'transparent',
            fillColor: '#ffffff',
            fillOpacity: 1.0,
            interactive: false,
            pane: 'maskPane'
        });
        overlays.addLayer(mask);
        
        setTimeout(() => {
            map.invalidateSize();
            map.originalMidX = midX;
            map.originalMidY = midY;
            map.originalZoom = idealZoom;
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
    let btn = document.getElementById('offline-sync-btn');
    if (btn) btn.disabled = true;
    
    let progressOverlay = document.getElementById('sync-progress');
    let bar = document.getElementById('sync-bar');
    let text = document.getElementById('sync-text');
    if (progressOverlay) progressOverlay.style.display = 'flex';
    
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
        
        const chunkSize = 20;
        for (let i = 0; i < total; i += chunkSize) {
            let chunk = urlsToFetch.slice(i, i + chunkSize);
            await Promise.all(chunk.map(async (url) => {
                try {
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
            if(progressOverlay) progressOverlay.style.display = 'none';
            btn.innerHTML = '<svg class="sync-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M5 13l4 4L19 7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>';
            btn.style.background = "var(--bg-color)";
            btn.onclick = null;
        }, 500);
        
    } catch (err) {
        alert("Chyba při stahování: " + err.message);
        if(progressOverlay) progressOverlay.style.display = 'none';
    }
}

// === LIKES, BOOKMARKS, SHARE ===
function toggleLike(index, btn) {
    btn.classList.toggle('liked');
    if (btn.classList.contains('liked')) {
        btn.innerHTML = '<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1.5"><path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z" stroke-linecap="round" stroke-linejoin="round"/></svg>';
        triggerLikeAnimation(index);
    } else {
        btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z"/></svg>';
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

// UPRAVENÁ FUNKCE - Ukládání a odebírání ze Storage
function toggleBookmark(index, btn) {
    btn.classList.toggle('bookmarked');
    
    // Získáme unikátní ID konkrétního postupu z načtených dat
    const mapId = postupyData[index].id;
    let saved = JSON.parse(localStorage.getItem('saved_postupy') || '[]');
    
    if (btn.classList.contains('bookmarked')) {
        btn.innerHTML = '<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 012-2h10a2 2 0 012 2z"/></svg>';
        // Pokud ještě není uloženo, přidej
        if (!saved.includes(mapId)) {
            saved.push(mapId);
        }
    } else {
        btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 012-2h10a2 2 0 012 2z"/></svg>';
        // Odeber uložení
        saved = saved.filter(id => id !== mapId);
    }
    
    // Zapsat zpět do prohlížeče
    localStorage.setItem('saved_postupy', JSON.stringify(saved));
    
    // Pokud je profil otevřený, rovnou ho aktualizujeme
    renderProfileSaved();
}

function sharePostup(index) {
    if (navigator.share) {
        navigator.share({
            title: 'Zajímavý postup!',
            text: 'Podívej se na tuhle volbu postupu ve Scrollienteeringu.',
            url: window.location.href
        }).catch(err => console.log('Share error:', err));
    } else {
        alert("Odkaz zkopírován do schránky (simulace).");
    }
}

// === ZCELA NOVÁ FUNKCE: Vykreslení uložených položek v Profilu ===
function renderProfileSaved() {
    const profileScreen = document.getElementById('screen-profile');
    if (!profileScreen) return;
    
    // Zkusíme najít mřížku pro uložené položky v profilu
    let gridContainer = profileScreen.querySelector('.explore-grid-container') || profileScreen.querySelector('.profile-grid');
    
    // Fallback: Pokud žádná taková mřížka v profilu není, rovnou ji vytvoříme
    if (!gridContainer) {
        gridContainer = document.createElement('div');
        gridContainer.className = 'explore-grid-container profile-grid';
        profileScreen.appendChild(gridContainer);
    }
    
    gridContainer.innerHTML = '';
    
    let saved = JSON.parse(localStorage.getItem('saved_postupy') || '[]');
    
    if (saved.length === 0) {
        gridContainer.innerHTML = '<div style="grid-column: 1 / -1; text-align:center; padding: 3rem; color: #888; font-size: 0.9rem;">Zatím nemáš uloženy žádné postupy.</div>';
        return;
    }
    
    const localMapThumbs = [
        "tiles/3/1/2.png", "tiles/3/2/2.png", "tiles/3/1/3.png",
        "tiles/2/0/1.png", "tiles/3/2/3.png", "tiles/1/0/0.png"
    ];
    
    const savedData = postupyData.filter(map => saved.includes(map.id));
    
    savedData.forEach((map) => {
        const thumbUrl = localMapThumbs[(map.id - 1) % localMapThumbs.length] || localMapThumbs[0];
        const el = document.createElement('div');
        el.className = 'explore-grid-item';
        
        let iconHtml = '';
        if (map.variants_count > 1) {
            iconHtml = '<svg class="grid-icon" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2" stroke="#fff" stroke-width="2" fill="none"/></svg>';
        }
        
        el.innerHTML = `
            <div class="grid-img" style="background-image: url('${thumbUrl}');"></div>
            ${iconHtml}
        `;
        
        el.addEventListener('click', () => {
            openMapInFeed(map.id);
        });
        
        gridContainer.appendChild(el);
    });
}

// === EXPLORE LOGIKA ===
let appState = {
    selectedTerrains: ['*'] 
};

function setupExploreStories() {
    const stories = document.querySelectorAll('.story-item');
    const navBadge = document.getElementById('nav-badge');
    
    stories.forEach(story => {
        story.addEventListener('click', () => {
            const terrain = story.getAttribute('data-terrain');
            const ring = story.querySelector('.story-ring');
            
            if (selectedTerrains.has(terrain)) {
                selectedTerrains.delete(terrain);
                ring.classList.remove('active-story');
            } else {
                selectedTerrains.add(terrain);
                ring.classList.add('active-story');
            }
            
            updateExploreBadge(navBadge);
            renderExploreGrid(); 
        });
    });
}

function updateExploreBadge(badgeEl) {
    if (selectedTerrains.size > 0) {
        badgeEl.innerText = selectedTerrains.size;
        badgeEl.style.display = 'flex';
        appState.selectedTerrains = Array.from(selectedTerrains);
    } else {
        badgeEl.style.display = 'none';
        appState.selectedTerrains = ['*'];
    }
    
    const allReels = document.querySelectorAll('.reel');
    allReels.forEach(reel => {
        if (selectedTerrains.size === 0) {
            reel.style.display = 'block'; 
        } else {
            const t = reel.getAttribute('data-terrain');
            if (selectedTerrains.has(t)) {
                reel.style.display = 'block';
            } else {
                reel.style.display = 'none';
            }
        }
    });
}

function renderExploreGrid() {
    const container = document.getElementById('explore-grid-container');
    if (!container) return;
    container.innerHTML = '';
    
    let displayData = postupyData;
    if (selectedTerrains.size > 0) {
        displayData = postupyData.filter(map => selectedTerrains.has(map.terrain));
    }
    
    const localMapThumbs = [
        "tiles/3/1/2.png",
        "tiles/3/2/2.png",
        "tiles/3/1/3.png",
        "tiles/2/0/1.png",
        "tiles/3/2/3.png",
        "tiles/1/0/0.png"
    ];
    
    displayData.forEach((map, index) => {
        const thumbUrl = localMapThumbs[(map.id - 1) % localMapThumbs.length] || localMapThumbs[0];
        const isDoubleHeight = (index % 4 === 3);
        const isAnimated = (index === 0); 
        
        const el = document.createElement('div');
        el.className = 'explore-grid-item' + (isDoubleHeight ? ' double-height' : '');
        
        let iconHtml = '';
        if (isDoubleHeight) {
            iconHtml = '<svg class="grid-icon" viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21" stroke="#fff" stroke-width="2" fill="none"/></svg>';
        } else if (map.variants_count > 1) {
            iconHtml = '<svg class="grid-icon" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2" stroke="#fff" stroke-width="2" fill="none"/></svg>'; 
        }
        
        const animClass = isAnimated ? ' animated-map' : '';
        
        el.innerHTML = `
            <div class="grid-img${animClass}" style="background-image: url('${thumbUrl}');"></div>
            ${iconHtml}
        `;
        
        el.addEventListener('click', () => {
            openMapInFeed(map.id);
        });
        
        container.appendChild(el);
    });
}

function openMapInFeed(mapId) {
    const globalIndex = postupyData.findIndex(m => m.id === mapId);
    if (globalIndex === -1) return;
    
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.querySelector('.nav-btn[data-target="screen-scroll"]').classList.add('active');
    
    document.querySelectorAll('.app-screen').forEach(screen => {
        if (screen.id === 'screen-scroll') {
            screen.classList.add('active');
        } else {
            screen.classList.remove('active');
        }
    });
    
    const reelsContainer = document.getElementById('reels-container');
    const targetReel = document.querySelector(`.reel[data-index="${globalIndex}"]`);
    if (targetReel) {
        reelsContainer.scrollTo({
            top: targetReel.offsetTop,
            behavior: 'auto'
        });
    }
}
