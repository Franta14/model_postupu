let postupyData = [];
let geojsonCache = {};
let mapInstances = {}; // stores { index: L.map }
let currentLayers = {}; // stores { index: L.geoJSON }

const iofPurple = "#D81E5B";

document.addEventListener("DOMContentLoaded", () => {
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

function setupObserver() {
    const options = {
        root: document.getElementById('reels-container'),
        rootMargin: '0px',
        threshold: 0.5
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const index = entry.target.dataset.index;
                activateReel(index);
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
    
    if (!mapInstances[index]) {
        initMapForReel(index);
    }
    
    const postup = postupyData[index];
    if (geojsonCache[postup.file]) {
        renderMapData(index, geojsonCache[postup.file]);
    } else {
        fetch('postupy/' + postup.file + '?v=' + Date.now())
            .then(res => res.json())
            .then(geojson => {
                geojsonCache[postup.file] = geojson;
                renderMapData(index, geojson);
            })
            .catch(err => {
                console.error("GeoJSON load error:", err);
            });
    }
}

function initMapForReel(index) {
    const map = L.map(`map-${index}`, {
        crs: L.CRS.Simple,
        minZoom: 0,
        maxZoom: 8, // reduced maxZoom slightly to prevent excessive overzoom
        zoomSnap: 0,
        zoomControl: false,
        gestureHandling: false
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
        keepBuffer: 8,
        updateWhenZooming: false,
        detectRetina: true
    }).addTo(map);
    
    map.fitBounds(bounds);
    mapInstances[index] = map;
}

function renderMapData(index, geojsonOriginal) {
    try {
        const map = mapInstances[index];
        if (!map) return;
    
    if (currentLayers[index]) {
        map.removeLayer(currentLayers[index]);
    }
    
    let geojson = JSON.parse(JSON.stringify(geojsonOriginal));
    
    let startCoords = null;
    let endCoords = null;
    
    geojson.features.forEach(f => {
        if (f.properties && f.properties.type === 'start') startCoords = f.geometry.coordinates;
        if (f.properties && f.properties.type === 'end') endCoords = f.geometry.coordinates;
    });
    
    if (startCoords && endCoords) {
        let dx = endCoords[0] - startCoords[0];
        let dy = endCoords[1] - startCoords[1];
        let dist = Math.sqrt(dx*dx + dy*dy);
        if (dist > 0) {
            let ux = dx / dist;
            let uy = dy / dist;
            
            let rStart = 0.75; 
            let rEnd = 0.55;   
            
            let lineStart = [startCoords[0] + ux * rStart * 1.5, startCoords[1] + uy * rStart * 1.5];
            let lineEnd = [endCoords[0] - ux * rEnd * 1.2, endCoords[1] - uy * rEnd * 1.2];
            
            geojson.features.push({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [lineStart, lineEnd]
                },
                "properties": {"type": "spojnice"}
            });
        }
    }
    
    let showVariants = showVariantsForIndex[index] || false;

    let layer = L.geoJSON(geojson, {
        filter: function(feature) {
            if (feature.properties && feature.properties.type === 'variant' && !showVariants) {
                return false;
            }
            return true;
        },
        style: function (feature) {
            if (feature.properties && feature.properties.type === 'variant') {
                return { color: feature.properties.color, weight: 6, opacity: 0.8 };
            }
            if (feature.properties && feature.properties.type === 'spojnice') {
                return { color: iofPurple, weight: 3, opacity: 0.8 };
            }
        },
        pointToLayer: function (feature, latlng) {
            if (feature.properties && feature.properties.type === 'end') {
                let rEnd = 0.55;
                let outer = L.circle(latlng, {radius: rEnd, color: iofPurple, weight: 3, fill: false, opacity: 0.9});
                let inner = L.circle(latlng, {radius: rEnd * 0.6, color: iofPurple, weight: 3, fill: false, opacity: 0.9});
                return L.featureGroup([outer, inner]);
            }
            
            if (feature.properties && feature.properties.type === 'start' && endCoords) {
                let rStart = 0.75;
                let dx = endCoords[0] - startCoords[0];
                let dy = endCoords[1] - startCoords[1];
                let dist = Math.sqrt(dx*dx + dy*dy);
                if (dist > 0) {
                    let ux = dx / dist;
                    let uy = dy / dist;
                    let vx = -uy;
                    let vy = ux;
                    
                    let p1 = [startCoords[1] + uy * rStart, startCoords[0] + ux * rStart];
                    let p2 = [startCoords[1] - 0.5 * uy * rStart + 0.866 * vy * rStart, startCoords[0] - 0.5 * ux * rStart + 0.866 * vx * rStart];
                    let p3 = [startCoords[1] - 0.5 * uy * rStart - 0.866 * vy * rStart, startCoords[0] - 0.5 * ux * rStart - 0.866 * vx * rStart];
                    
                    return L.polygon([p1, p2, p3], {color: iofPurple, weight: 3, fill: false, opacity: 0.9});
                }
            }
            
            return L.circleMarker(latlng, {radius: 5, color: "red"});
        }
    });
    
    layer.addTo(map);
    currentLayers[index] = layer;
    
    let bounds = layer.getBounds();
    if (bounds.isValid()) {
        let southWest = bounds.getSouthWest();
        let northEast = bounds.getNorthEast();
        let latDiff = northEast.lat - southWest.lat;
        let lngDiff = northEast.lng - southWest.lng;
        
        let newNorth = northEast.lat + latDiff * 0.30;
        let newEast = northEast.lng + lngDiff * 0.30;
        let newWest = southWest.lng - lngDiff * 0.30;
        let newSouth = southWest.lat - latDiff * 0.30;
        
        let paddedBounds = L.latLngBounds([newSouth, newWest], [newNorth, newEast]);
        
        map.setMaxBounds(paddedBounds);
        
        let minZoom = map.getBoundsZoom(paddedBounds);
        let maxZoom = map.getMaxZoom() || 8;
        if (minZoom > maxZoom) minZoom = maxZoom;
        map.setMinZoom(minZoom);
        
        map.fitBounds(paddedBounds, {
            animate: true,
            duration: 0.5
        });
    }
    } catch (e) {
        alert("renderMapData Error at index " + index + ": " + e.message + "\nStack: " + e.stack);
    }
}
