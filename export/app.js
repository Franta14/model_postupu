let postupyData = [];
let geojsonCache = {};
let mapInstances = {}; 
let currentLayers = {}; 
let currentOverlays = {}; 
let currentTileLayers = {}; 

const iofPurple = "#b300ff";
let profileSelectedTerrain = 'Vše';

// CSS pro posuvné štítky a režim "Uloženého Feedu" (Overlay)
const style = document.createElement('style');
style.innerHTML = `
.profile-pills-container::-webkit-scrollbar { display: none; }
.profile-pills-container { -ms-overflow-style: none; scrollbar-width: none; }

/* IG-like Saved Mode Styles */
body.saved-mode-active .bottom-nav, 
body.saved-mode-active .nav-bar { display: none !important; }
#saved-mode-header {
    position: fixed; top: 0; left: 0; width: 100%; height: 90px;
    z-index: 9999; display: none; align-items: flex-end; padding: 0 20px 15px 20px;
    background: linear-gradient(to bottom, rgba(0,0,0,0.9) 0%, rgba(0,0,0,0.6) 60%, transparent 100%);
    color: #fff; font-size: 1.3rem; font-weight: 600; cursor: pointer;
}
body.saved-mode-active #saved-mode-header { display: flex; }
body.saved-mode-active #screen-scroll { height: 100vh; padding-bottom: 0; }
body.saved-mode-active .reel { height: 100vh; }
`;
document.head.appendChild(style);

document.addEventListener("DOMContentLoaded", () => {
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

    loadData();

    // Spodní navigace
    const navButtons = document.querySelectorAll('.nav-btn');
    const screens = document.querySelectorAll('.app-screen');

    navButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const targetId = btn.getAttribute('data-target');
            navButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            screens.forEach(screen => {
                if (screen.id === targetId) {
                    screen.classList.add('active');
                    if (targetId === 'screen-profile') renderProfileSaved();
                } else {
                    screen.classList.remove('active');
                }
            });
        });
    });

    // Hlavička a Swipe-to-close pro režim uložených map
    let smh = document.createElement('div');
    smh.id = 'saved-mode-header';
    smh.innerHTML = '<svg style="width:28px; height:28px; margin-right:10px; margin-bottom:-2px;" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/></svg> Uložené';
    smh.onclick = closeSavedFeed;
    document.body.appendChild(smh);

    let startX = 0;
    document.body.addEventListener('touchstart', e => {
        if (document.body.classList.contains('saved-mode-active')) startX = e.touches[0].clientX;
    }, {passive: true});
    
    document.body.addEventListener('touchend', e => {
        if (document.body.classList.contains('saved-mode-active')) {
            if (e.changedTouches[0].clientX - startX > 100) closeSavedFeed();
        }
    }, {passive: true});
});

let selectedTerrains = new Set();

function loadData() {
    fetch('postupy/postupy_index.json?v=' + Date.now())
        .then(res => res.json())
        .then(data => {
            postupyData = data;
            postupyData.forEach((map, index) => {
                map.terrain = 'cesky-les';
                if (!map.id) map.id = index + 1;
            });
            
            buildReels();
            setupObserver();
            renderExploreGrid();
            setupExploreStories();
            renderProfileSaved();
            
            setTimeout(() => {
                const loader = document.getElementById('loader');
                if (loader) { loader.style.opacity = 0; setTimeout(() => loader.remove(), 500); }
            }, 500);
        })
        .catch(err => alert("Chyba při načítání dat: " + err));
}

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
                    <div class="reel-subtitle">${postup.dist_m ? postup.dist_m.toFixed(0) : ''} m vzdušně</div>
                    <button class="btn-primary" onclick="toggleVariants(${index})"><svg class="btn-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M4 6h16M4 12h16M4 18h16" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" fill="none"/></svg>Volby</button>
                </div>
            </div>
        `;
        container.appendChild(reel);
    });
}

let scrollTimeout = null;
function setupObserver() {
    let options = { root: document.getElementById('app'), rootMargin: '0px', threshold: 0.5 };
    let observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const index = entry.target.dataset.index;
                if (scrollTimeout) clearTimeout(scrollTimeout);
                scrollTimeout = setTimeout(() => { activateReel(index); }, 250);
            }
        });
    }, options);
    document.querySelectorAll('.reel').forEach(reel => observer.observe(reel));
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

function activateReel(indexStr) {
    const index = parseInt(indexStr);
    if (activeIndex !== index) {
        if (isPanelOpen) {
            const panel = document.getElementById('global-variants-panel');
            if (panel) { panel.classList.remove('active'); panel.classList.remove('collapsed'); }
            isPanelOpen = false;
            showVariantsForIndex[activeIndex] = false;
            const prevPostup = postupyData[activeIndex];
            if (prevPostup && geojsonCache[prevPostup.file]) renderMapData(activeIndex, geojsonCache[prevPostup.file]);
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
            .catch(err => console.error("GeoJSON load error:", err));
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
        zoomControl: false, gestureHandling: false, inertia: false
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
    map.on('zoomend', updateCalibrationShift);
    mapInstances[index] = map;
}

function renderMapData(index, geojsonOriginal) {
    try {
        const map = mapInstances[index];
        if (!map) return;
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
            let marginLng = Math.max(100, (maxLng - minLng) * 0.50);
            let marginLat = Math.max(100, (maxLat - minLat) * 0.50);
            let tileBounds = [[minLat - marginLat, minLng - marginLng], [maxLat + marginLat, maxLng + marginLng]];
            
            map.setMaxBounds(tileBounds);
            let tl = L.tileLayer('tiles/{z}/{x}/{y}.png', {
                tileSize: 512, minZoom: 0, maxZoom: 8, maxNativeZoom: 5,
                noWrap: true, tms: false, keepBuffer: 4, updateWhenIdle: false, updateWhenZooming: true, detectRetina: true
            }).addTo(map);
            currentTileLayers[index] = tl;
            
            if (index === activeIndex) {
                tl.once('load', () => { preloadReel(index + 1); preloadReel(index - 1); });
                setTimeout(() => { preloadReel(index + 1); preloadReel(index - 1); }, 500);
            }
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
            
            let targetPixelsY = h * 0.70;
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
            let routeHalfW = maxAbsX + (60 / pixelScale), routeHalfH = (dist / 2) + (80 / pixelScale);
            
            let holeHalfW = Math.max(screenHalfW, routeHalfW), holeHalfH = Math.max(screenHalfH, routeHalfH);
            
            let innerRing = [
                [midY + uy * holeHalfH + vy * holeHalfW, midX + ux * holeHalfH + vx * holeHalfW],
                [midY + uy * holeHalfH - vy * holeHalfW, midX + ux * holeHalfH - vx * holeHalfW],
                [midY - uy * holeHalfH - vy * holeHalfW, midX - ux * holeHalfH - vx * holeHalfW],
                [midY - uy * holeHalfH + vy * holeHalfW, midX - ux * holeHalfH + vx * holeHalfW]
            ];
            let outerRing = [[-50000, -50000], [-50000, 50000], [50000, 50000], [50000, -50000]];
            
            let mask = L.polygon([outerRing, innerRing], { color: 'transparent', fillColor: '#ffffff', fillOpacity: 1.0, interactive: false, pane: 'maskPane' });
            overlays.addLayer(mask);
            
            setTimeout(() => {
                map.invalidateSize();
                map.originalMidX = midX; map.originalMidY = midY; map.originalZoom = idealZoom;
                map.setView([midY, midX], idealZoom, { animate: false });
            }, 50);
        }
    } catch (e) {
        alert("renderMapData Error at index " + index + ": " + e.message + "\nStack: " + e.stack);
    }
}

// === KALIBRACE ===
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

function toggleLike(index, btn) {
    btn.classList.toggle('liked');
    if (btn.classList.contains('liked')) {
        btn.innerHTML = '<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1.5"><path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z" stroke-linecap="round" stroke-linejoin="round"/></svg>';
        let anim = document.getElementById(`like-anim-${index}`);
        if (anim) { anim.classList.remove('active'); void anim.offsetWidth; anim.classList.add('active'); }
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

// === GENIÁLNÍ MINIMAPY ===
// Pole pro úklid paměti po starých mapách
window.miniMaps = window.miniMaps || [];

function createMiniMap(containerId, mapData) {
    const el = document.getElementById(containerId);
    if (!el) return null;
    
    // Tvorba čisté mapy bez jakéhokoliv ovládání
    const miniMap = L.map(containerId, {
        crs: L.CRS.Simple, minZoom: 0, maxZoom: 8, zoomControl: false, attributionControl: false,
        dragging: false, touchZoom: false, scrollWheelZoom: false, doubleClickZoom: false, boxZoom: false, keyboard: false
    });

    L.tileLayer('tiles/{z}/{x}/{y}.png', {
        tileSize: 512, minZoom: 0, maxZoom: 8, maxNativeZoom: 5, noWrap: true, keepBuffer: 2
    }).addTo(miniMap);

    if (geojsonCache[mapData.file]) {
        drawMiniMap(miniMap, geojsonCache[mapData.file]);
    } else {
        fetch('postupy/' + mapData.file + '?v=' + Date.now())
            .then(r => r.json())
            .then(data => {
                geojsonCache[mapData.file] = data;
                drawMiniMap(miniMap, data);
            }).catch(e => console.log(e));
    }
    return miniMap;
}

function drawMiniMap(miniMap, geojson) {
    let allLngs = [], allLats = [];
    let startC = null, endC = null;
    
    geojson.features.forEach(f => {
        if (f.properties && f.properties.type === 'start') startC = f.geometry.coordinates;
        if (f.properties && f.properties.type === 'end') endC = f.geometry.coordinates;
        if (f.geometry.type === 'Point') {
            allLngs.push(f.geometry.coordinates[0]); allLats.push(f.geometry.coordinates[1]);
        } else if (f.geometry.type === 'LineString') {
            f.geometry.coordinates.forEach(c => { allLngs.push(c[0]); allLats.push(c[1]); });
        }
    });

    // Nakreslení variant v jejich barvách
    L.geoJSON(geojson, {
        filter: f => (f.properties && f.properties.type === 'variant'),
        style: f => ({ color: f.properties.color, weight: 3, opacity: 0.9 })
    }).addTo(miniMap);

    // Vykreslení zjednodušených kontrol (bez textu)
    if (startC) L.circle([startC[1], startC[0]], {radius: 1.5, color: iofPurple, weight: 2, fill: false}).addTo(miniMap);
    if (endC) L.circle([endC[1], endC[0]], {radius: 1.5, color: iofPurple, weight: 2, fill: false}).addTo(miniMap);

    if (allLngs.length > 0) {
        let minLng = Math.min(...allLngs), maxLng = Math.max(...allLngs);
        let minLat = Math.min(...allLats), maxLat = Math.max(...allLats);
        // Vycentrujeme přímo na trasu s okrajem 15 pixelů
        miniMap.fitBounds([[minLat, minLng], [maxLat, maxLng]], { padding: [15, 15], animate: false });
    }
}

// === VYKRESLENÍ PROFILU ===
function renderProfileSaved() {
    const profileScreen = document.getElementById('screen-profile');
    if (!profileScreen) return;
    
    // Vyčistíme staré Leaflet minimapy z paměti
    if (window.profileMaps) { window.profileMaps.forEach(m => m.remove()); }
    window.profileMaps = [];

    const oldTabs = profileScreen.querySelectorAll('.profile-tabs, .nav-tabs');
    oldTabs.forEach(tab => tab.style.display = 'none');
    
    let profileContent = document.getElementById('profile-content-wrapper');
    if (!profileContent) {
        profileContent = document.createElement('div');
        profileContent.id = 'profile-content-wrapper';
        const oldGridContainers = profileScreen.querySelectorAll('.explore-grid-container, .profile-grid');
        oldGridContainers.forEach(g => g.remove());
        profileScreen.appendChild(profileContent);
    }
    
    profileContent.innerHTML = ''; 
    let saved = JSON.parse(localStorage.getItem('saved_postupy') || '[]');
    let savedIds = saved.map(String);
    
    if (savedIds.length === 0) {
        profileContent.innerHTML = `
            <div style="text-align:center; padding: 4rem 1.5rem; color: #888; font-size: 0.95rem;">
                <svg style="width: 42px; height: 42px; margin-bottom: 10px; stroke: #666;" viewBox="0 0 24 24" fill="none" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M19 21l-7-5-7 5V5a2 2 0 012-2h10a2 2 0 012 2z"/>
                </svg>
                <div style="font-weight: 600; color: #aaa; margin-bottom: 4px;">Žádné uložené postupy</div>
                <div style="font-size: 0.8rem;">Klikni ve feedu na ikonku záložky pro uložení.</div>
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
    pillsContainer.style.padding = '15px';
    pillsContainer.style.borderBottom = '1px solid #333';
    
    const createPill = (terrainName, label) => {
        const pill = document.createElement('button');
        pill.innerText = label;
        pill.style.padding = '8px 16px';
        pill.style.borderRadius = '20px';
        pill.style.border = 'none';
        pill.style.whiteSpace = 'nowrap';
        pill.style.fontSize = '0.85rem';
        pill.style.fontWeight = '600';
        pill.style.cursor = 'pointer';
        pill.style.transition = 'all 0.2s';
        if (profileSelectedTerrain === terrainName) { pill.style.background = '#fff'; pill.style.color = '#000'; } 
        else { pill.style.background = '#333'; pill.style.color = '#ccc'; }
        pill.onclick = () => { profileSelectedTerrain = terrainName; renderProfileSaved(); };
        return pill;
    };

    pillsContainer.appendChild(createPill('Vše', 'Vše'));
    uniqueTerrains.forEach(t => {
        const niceName = t.charAt(0).toUpperCase() + t.slice(1).replace('-', ' ');
        pillsContainer.appendChild(createPill(t, niceName));
    });
    profileContent.appendChild(pillsContainer);
    
    const gridContainer = document.createElement('div');
    gridContainer.style.display = 'grid';
    gridContainer.style.gridTemplateColumns = 'repeat(3, 1fr)';
    gridContainer.style.gap = '2px';
    gridContainer.style.width = '100%';
    gridContainer.style.padding = '2px 0 80px 0';
    
    const displayData = profileSelectedTerrain === 'Vše' ? savedData : savedData.filter(map => map.terrain === profileSelectedTerrain);
    
    displayData.forEach((map) => {
        const el = document.createElement('div');
        el.className = 'explore-grid-item';
        el.style.position = 'relative';
        el.style.aspectRatio = '1 / 1';
        
        let distBadge = map.dist_m ? `<div style="position:absolute; bottom:6px; left:6px; background:rgba(0,0,0,0.7); color:#fff; font-size:10px; padding:2px 5px; border-radius:3px; font-weight:600; z-index: 1001;">${map.dist_m.toFixed(0)}m</div>` : '';
        const minimapId = 'minimap-prof-' + map.id;
        
        // Krycí DIV zachytí kliknutí, aby nepropadlo do Leafletu
        el.innerHTML = `
            <div id="${minimapId}" style="width: 100%; height: 100%; background: #e5e5e5; z-index: 1;"></div>
            <div style="position:absolute; top:0; left:0; width:100%; height:100%; z-index:1000; cursor:pointer;"></div>
            ${distBadge}
        `;
        el.addEventListener('click', () => openSavedMapInFeed(map.id));
        gridContainer.appendChild(el);
        
        setTimeout(() => {
            const m = createMiniMap(minimapId, map);
            if(m) window.profileMaps.push(m);
        }, 50);
    });
    profileContent.appendChild(gridContainer);
}

// === OVERLAY REŽIM PRO ULOŽENÉ MAPY ===
function openSavedMapInFeed(mapId) {
    const globalIndex = postupyData.findIndex(m => String(m.id) === String(mapId));
    if (globalIndex === -1) return;

    document.body.classList.add('saved-mode-active');
    
    let saved = JSON.parse(localStorage.getItem('saved_postupy') || '[]');
    let savedStrings = saved.map(String);
    
    document.querySelectorAll('.reel').forEach(reel => {
        let mId = postupyData[reel.dataset.index].id;
        if (savedStrings.includes(String(mId))) {
            reel.style.display = 'block';
        } else {
            reel.style.display = 'none';
        }
    });

    document.querySelectorAll('.app-screen').forEach(s => s.classList.remove('active'));
    document.getElementById('screen-scroll').classList.add('active');

    const reelsContainer = document.getElementById('reels-container');
    const targetReel = document.querySelector(`.reel[data-index="${globalIndex}"]`);
    if (targetReel && reelsContainer) {
        setTimeout(() => {
            reelsContainer.scrollTo({ top: targetReel.offsetTop, behavior: 'instant' });
            let activeMap = mapInstances[globalIndex];
            if (activeMap) activeMap.invalidateSize();
        }, 10);
    }
}

function closeSavedFeed() {
    document.body.classList.remove('saved-mode-active');
    updateExploreBadge(document.getElementById('nav-badge'));

    document.querySelectorAll('.app-screen').forEach(s => s.classList.remove('active'));
    document.getElementById('screen-profile').classList.add('active');
}

// === EXPLORE LOGIKA ===
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
    
    if (window.exploreMaps) { window.exploreMaps.forEach(m => m.remove()); }
    window.exploreMaps = [];
    container.innerHTML = '';
    
    let displayData = postupyData;
    if (selectedTerrains.size > 0) displayData = postupyData.filter(map => selectedTerrains.has(map.terrain));
    
    displayData.forEach((map) => {
        const el = document.createElement('div');
        el.className = 'explore-grid-item'; 
        el.style.aspectRatio = '1 / 1';
        el.style.position = 'relative';
        
        const minimapId = 'minimap-expl-' + map.id;
        
        el.innerHTML = `
            <div id="${minimapId}" style="width:100%; height:100%; background:#e5e5e5; z-index:1;"></div>
            <div style="position:absolute; top:0; left:0; width:100%; height:100%; z-index:1000; cursor:pointer;"></div>
        `;
        el.addEventListener('click', () => {
            const globalIndex = postupyData.findIndex(m => String(m.id) === String(map.id));
            if (globalIndex === -1) return;
            
            document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
            const scrollNavBtn = document.querySelector('.nav-btn[data-target="screen-scroll"]');
            if (scrollNavBtn) scrollNavBtn.classList.add('active');
            
            document.querySelectorAll('.app-screen').forEach(screen => {
                if (screen.id === 'screen-scroll') screen.classList.add('active');
                else screen.classList.remove('active');
            });
            
            const reelsContainer = document.getElementById('reels-container');
            const targetReel = document.querySelector(`.reel[data-index="${globalIndex}"]`);
            if (targetReel && reelsContainer) reelsContainer.scrollTo({ top: targetReel.offsetTop, behavior: 'auto' });
        });
        container.appendChild(el);
        
        setTimeout(() => {
            const m = createMiniMap(minimapId, map);
            if(m) window.exploreMaps.push(m);
        }, 50);
    });
}
