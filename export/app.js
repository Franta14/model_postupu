let postupyData = [];
let geojsonCache = {};
let mapInstances = {}; // stores { index: L.map }
let currentLayers = {}; // stores { index: L.geoJSON }
let currentOverlays = {}; // stores { index: L.featureGroup }

const iofPurple = "#D81E5B";

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
            <div class="map-container" id="map-${index}"></div>
            <div class="reel-ui">
                <div class="reel-header">
                    <div class="reel-subtitle">${postup.dist_m.toFixed(0)} m vzdušně</div>
                    <button class="btn-primary" onclick="toggleVariants(${index})">Volby</button>
                </div>
            </div>
            <div class="scroll-area">↑ Další postup ↓</div>
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
                if (dx * dy > 0) panelClass = 'pos-top-left';
            }
        }
        
        panel.className = 'variants-panel ' + panelClass;
        void panel.offsetWidth; // force reflow
        
        document.getElementById('global-close-btn').onclick = () => {
            panel.classList.remove('active');
            isPanelOpen = false;
            showVariantsForIndex[index] = false;
            renderMapData(index, geojsonCache[postup.file]); // redraw to hide variants
        };
        
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
    
    // Předvykreslení následujícího a předchozího postupu na pozadí,
    // čímž dosáhneme naprosto plynulého scrollování bez zpoždění.
    setTimeout(() => {
        preloadReel(index + 1);
        preloadReel(index - 1);
    }, 200);
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
    Math.round = Math.ceil;
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
        maxZoom: 8, // reduced maxZoom slightly to prevent excessive overzoom
        zoomSnap: 0,
        zoomControl: false,
        gestureHandling: false,
        maxBoundsViscosity: 1.0,
        inertia: false
    });
    
    L.control.zoom({ position: 'topleft' }).addTo(map);

    var bounds = [[-256, 0], [0, 256]];
    L.tileLayer('tiles/{z}/{x}/{y}.png', {
        minZoom: 0,
        maxZoom: 8,
        maxNativeZoom: 6,
        noWrap: true,
        tms: false,
        bounds: bounds,
        keepBuffer: 1,
        updateWhenZooming: false,
        detectRetina: true
    }).addTo(map);
    
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
    
    geojson.features.forEach(f => {
        if (f.properties && f.properties.type === 'start') startCoords = f.geometry.coordinates;
        if (f.properties && f.properties.type === 'end') endCoords = f.geometry.coordinates;
    });
    
    
    
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
            let R = 0.55; 
            let gap = 0.05;
            let ux = dx / dist;
            let uy = dy / dist;
            let targetBearing = (Math.atan2(dy, dx) * 180 / Math.PI) - 90;
            document.getElementById(`map-${index}`).style.transform = `rotate(${targetBearing}deg)`;
            let lineWeight = Math.max(2.5, Math.min(3.5, 2.5 + dist / 100));
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
                let strokeW = Math.max(8, Math.min(12, 8 + dist/50));
                // 1. Circle Overlay
                let svgCircle = document.createElementNS("http://www.w3.org/2000/svg", "svg");
                svgCircle.setAttribute('xmlns', "http://www.w3.org/2000/svg");
                svgCircle.setAttribute('viewBox', "0 0 100 100");
                svgCircle.innerHTML = `<circle cx="50" cy="50" r="${50 - strokeW/2}" fill="none" stroke="${iofPurple}" stroke-width="${strokeW}" />`;
                let boundsCircle = [[coords[1] - R, coords[0] - R], [coords[1] + R, coords[0] + R]];
                overlays.addLayer(L.svgOverlay(svgCircle, boundsCircle, {interactive: false, pane: 'markerPane'}));
                
                // 2. Text Overlay (Offset)
                let nx = -uy, ny = ux;
                let textDist = R + 0.40;
                let cx = coords[0] + nx * textDist, cy = coords[1] + ny * textDist;
                
                let svgText = document.createElementNS("http://www.w3.org/2000/svg", "svg");
                svgText.setAttribute('xmlns', "http://www.w3.org/2000/svg");
                svgText.setAttribute('viewBox', "0 0 100 100");
                svgText.innerHTML = `<text x="50" y="80" transform="rotate(${-targetBearing}, 50, 50)" font-family="Arial, sans-serif" font-size="75" font-weight="bold" fill="${iofPurple}" text-anchor="middle">${num}</text>`;
                let halfSizeText = 0.45;
                let boundsText = [[cy - halfSizeText, cx - halfSizeText], [cy + halfSizeText, cx + halfSizeText]];
                overlays.addLayer(L.svgOverlay(svgText, boundsText, {interactive: false, pane: 'markerPane'}));
            });
        }
    }
    
    layer.addTo(map);
    currentLayers[index] = layer;
    
    let bounds = layer.getBounds();
    if (bounds.isValid() && startCoords && endCoords) {
        let w = window.innerWidth;
        let h = window.innerHeight - 60; // visible height
        
        let dx = endCoords[0] - startCoords[0];
        let dy = endCoords[1] - startCoords[1];
        let dist = Math.sqrt(dx*dx + dy*dy);
        
        // Cílová délka postupu na obrazovce v pixelech (např. 90% výšky displeje)
        let targetPixelsY = h * 0.90;
        let idealZoom = 0;
        if (dist > 0) {
            idealZoom = Math.log2(targetPixelsY / dist);
        }
        
        let HARD_MIN_ZOOM = 2; 
        let maxZoom = map.getMaxZoom() || 8;
        idealZoom = Math.max(HARD_MIN_ZOOM, Math.min(maxZoom, idealZoom));
        
        let midX = (startCoords[0] + endCoords[0]) / 2;
        let midY = (startCoords[1] + endCoords[1]) / 2;
        
        map.setMinZoom(idealZoom);
        
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
