const mapCanvas = document.getElementById('mapCanvas');
const ctx = mapCanvas.getContext('2d');
const mapSelect = document.getElementById('mapSelect');
const routeSelect = document.getElementById('routeSelect');
const statsContainer = document.getElementById('statsContainer');
const timeSlider = document.getElementById('timeSlider');
const timeDisplay = document.getElementById('timeDisplay');
const btnPlayPause = document.getElementById('btnPlayPause');
const speedSelect = document.getElementById('speedSelect');
const tailInput = document.getElementById('tailInput');
const canvasContainer = document.getElementById('canvasContainer');

let currentData = null;
let maxTime = 0;
let currentTime = 0;
let isPlaying = false;
let lastFrameTime = 0;
let mapImage = new Image();
let mapLoaded = false;

// Pan & Zoom
let transform = { x: 0, y: 0, scale: 1 };
let isDragging = false;
let startDragOffset = { x: 0, y: 0 };

const colors = ['#FF3366', '#33CCFF', '#33FF66', '#FF9933', '#00FFFF'];

// Init
async function init() {
    // Load maps index
    try {
        const res = await fetch('data/maps.json?t=' + Date.now());
        const maps = await res.json();
        
        mapSelect.innerHTML = '<option value="">-- Vyber mapu --</option>';
        maps.forEach(map => {
            const opt = document.createElement('option');
            opt.value = map.id;
            opt.dataset.image = map.image;
            opt.dataset.index = map.indexFile;
            opt.textContent = `${map.name} (${map.count} postupů)`;
            mapSelect.appendChild(opt);
        });
    } catch (e) {
        mapSelect.innerHTML = '<option value="">Chyba načítání map (nebo žádné nejsou)</option>';
    }

    // Events
    mapSelect.addEventListener('change', loadMap);
    routeSelect.addEventListener('change', loadRoute);
    btnPlayPause.addEventListener('click', togglePlay);
    timeSlider.addEventListener('input', (e) => {
        currentTime = parseFloat(e.target.value);
        updateTimeDisplay();
        updateUI();
        draw();
    });

    // Pan & Zoom events
    canvasContainer.addEventListener('mousedown', (e) => {
        isDragging = true;
        startDragOffset = { x: e.clientX - transform.x, y: e.clientY - transform.y };
    });
    window.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        transform.x = e.clientX - startDragOffset.x;
        transform.y = e.clientY - startDragOffset.y;
        updateTransform();
    });
    window.addEventListener('mouseup', () => isDragging = false);
    
    canvasContainer.addEventListener('wheel', (e) => {
        e.preventDefault();
        const zoomIntensity = 0.1;
        const wheel = e.deltaY < 0 ? 1 : -1;
        const zoom = Math.exp(wheel * zoomIntensity);
        
        const rect = canvasContainer.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        transform.x = mouseX - (mouseX - transform.x) * zoom;
        transform.y = mouseY - (mouseY - transform.y) * zoom;
        transform.scale *= zoom;
        updateTransform();
    });

    requestAnimationFrame(animationLoop);
}

async function loadMap(e) {
    const selected = mapSelect.options[mapSelect.selectedIndex];
    if (!selected.value) {
        routeSelect.innerHTML = '<option value="">Vyberte mapu</option>';
        return;
    }

    // Load map image
    mapLoaded = false;
    mapImage.src = selected.dataset.image;
    mapImage.onload = () => {
        mapLoaded = true;
        mapCanvas.width = mapImage.width;
        mapCanvas.height = mapImage.height;
        
        // Reset view
        transform = { x: 0, y: 0, scale: 1 };
        updateTransform();
        draw();
    };

    // Load routes index for this map
    try {
        const res = await fetch(selected.dataset.index + '?t=' + Date.now());
        const index = await res.json();
        
        routeSelect.innerHTML = '<option value="">-- Vyber postup --</option>';
        index.forEach(item => {
            const opt = document.createElement('option');
            opt.value = item.file;
            opt.textContent = item.name;
            routeSelect.appendChild(opt);
        });
    } catch (err) {
        routeSelect.innerHTML = '<option value="">Chyba načítání dat tras</option>';
    }
}

function updateTransform() {
    mapCanvas.style.transform = `translate(${transform.x}px, ${transform.y}px) scale(${transform.scale})`;
}

async function loadRoute(e) {
    const file = e.target.value;
    if (!file) return;

    const res = await fetch(file + '?t=' + Date.now());
    currentData = await res.json();
    
    // Find max time
    maxTime = 0;
    currentData.variants.forEach(v => {
        const vTime = v.time || v.total_time;
        if (vTime > maxTime) maxTime = vTime;
    });

    timeSlider.max = maxTime;
    currentTime = 0;
    timeSlider.value = 0;
    
    // Build sidebar stats
    statsContainer.innerHTML = '';
    currentData.variants.forEach((v, i) => {
        const colorClass = `v-${i % 5}`;
        const vTime = v.time || v.total_time;
        const vDist = v.distance || v.total_dist;
        statsContainer.innerHTML += `
            <div class="variant-card ${colorClass}" id="var-card-${i}">
                <div class="variant-header">
                    <span>Varianta ${String.fromCharCode(65 + i)}</span>
                    <span id="var-time-${i}">00:00</span>
                </div>
                <div class="variant-pace" id="var-pace-${i}">--:-- /km</div>
                <div class="variant-meta">
                    <span>${Math.round(vDist)} m</span>
                    <span>Cíl: ${formatTime(vTime)}</span>
                    <span id="var-ele-${i}">-- m n.m.</span>
                </div>
            </div>
        `;
    });

    // Auto-focus camera on the entire route
    if (mapLoaded) {
        const cw = canvasContainer.clientWidth;
        const ch = canvasContainer.clientHeight;
        
        let minX = currentData.start.x;
        let maxX = currentData.start.x;
        let minY = currentData.start.y;
        let maxY = currentData.start.y;
        
        currentData.variants.forEach(v => {
            v.points.forEach(p => {
                if (p.x < minX) minX = p.x;
                if (p.x > maxX) maxX = p.x;
                if (p.y < minY) minY = p.y;
                if (p.y > maxY) maxY = p.y;
            });
        });
        
        const routeWidth = maxX - minX;
        const routeHeight = maxY - minY;
        
        const padding = 200; // padding in pixels
        const scaleX = cw / (routeWidth + padding * 2);
        const scaleY = ch / (routeHeight + padding * 2);
        
        transform.scale = Math.min(scaleX, scaleY, 2.0); // max zoom 2.0x
        
        const cx = (minX + maxX) / 2;
        const cy = (minY + maxY) / 2;
        
        transform.x = (cw / 2) - (cx * transform.scale);
        transform.y = (ch / 2) - (cy * transform.scale);
        updateTransform();
    }

    updateTimeDisplay();
    updateUI();
    draw();
}

function togglePlay() {
    isPlaying = !isPlaying;
    btnPlayPause.textContent = isPlaying ? 'âŹ¸ Pause' : 'â–¶ Play';
    if (isPlaying) {
        lastFrameTime = performance.now();
    }
}

function animationLoop(timestamp) {
    if (isPlaying && currentData) {
        const dt = (timestamp - lastFrameTime) / 1000.0; // seconds
        lastFrameTime = timestamp;
        
        const speed = parseFloat(speedSelect.value);
        currentTime += dt * speed;
        
        if (currentTime >= maxTime) {
            currentTime = maxTime;
            isPlaying = false;
            btnPlayPause.textContent = 'â–¶ Play';
        }
        
        timeSlider.value = currentTime;
        updateTimeDisplay();
        updateUI();
        draw();
    }
    requestAnimationFrame(animationLoop);
}

function formatTime(secs) {
    if (isNaN(secs)) return '00:00';
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

function formatPace(paceSec) {
    if (!paceSec || paceSec <= 0 || isNaN(paceSec)) return '--:--';
    const m = Math.floor(paceSec / 60);
    const s = Math.floor(paceSec % 60);
    return `${m}:${s.toString().padStart(2, '0')} /km`;
}

function updateTimeDisplay() {
    timeDisplay.textContent = formatTime(currentTime);
}

function getInterpolatedState(variant, time) {
    if (time <= 0) return { ...variant.points[0] };
    if (time >= variant.total_time) return { ...variant.points[variant.points.length - 1], pace: 0, ele: variant.points[variant.points.length - 1].ele };
    
    // Find segment
    for (let i = 0; i < variant.points.length - 1; i++) {
        const p1 = variant.points[i];
        const p2 = variant.points[i+1];
        if (time >= p1.time && time <= p2.time) {
            const tDiff = p2.time - p1.time;
            const factor = tDiff > 0 ? (time - p1.time) / tDiff : 0;
            return {
                x: p1.x + (p2.x - p1.x) * factor,
                y: p1.y + (p2.y - p1.y) * factor,
                pace: p2.pace, // Current instantaneous pace for this segment
                ele: p1.ele + (p2.ele - p1.ele) * factor,
                dx: p2.x - p1.x,
                dy: p2.y - p1.y
            };
        }
    }
    return { ...variant.points[variant.points.length - 1], pace: 0 };
}

function updateUI() {
    if (!currentData) return;
    currentData.variants.forEach((v, i) => {
        const state = getInterpolatedState(v, currentTime);
        document.getElementById(`var-time-${i}`).textContent = formatTime(Math.min(currentTime, v.total_time));
        
        const paceEl = document.getElementById(`var-pace-${i}`);
        if (currentTime > v.total_time) {
            paceEl.textContent = 'V CĂŤLI';
            paceEl.style.color = 'var(--text-secondary)';
        } else {
            paceEl.textContent = formatPace(state.pace);
            paceEl.style.color = 'white';
        }

        const eleEl = document.getElementById(`var-ele-${i}`);
        if (state.ele !== undefined && eleEl) {
            eleEl.textContent = `${state.ele.toFixed(1)} m n.m.`;
        }
    });
}

function draw() {
    if (!mapLoaded) return;
    
    // Clear & draw map
    ctx.clearRect(0, 0, mapCanvas.width, mapCanvas.height);
    ctx.drawImage(mapImage, 0, 0);

    if (!currentData) return;

    // Draw connecting line Start -> End
    ctx.strokeStyle = '#9400D3';
    ctx.lineWidth = 4;
    ctx.globalAlpha = 0.5;
    ctx.beginPath();
    ctx.moveTo(currentData.start.x, currentData.start.y);
    ctx.lineTo(currentData.end.x, currentData.end.y);
    ctx.stroke();
    ctx.globalAlpha = 1.0;

    // Draw control markers (Start & End)
    drawControl(currentData.start.x, currentData.start.y, '1', true, currentData.end);
    drawControl(currentData.end.x, currentData.end.y, '2', false, null);

    // Draw paths (dimmed)
    ctx.lineWidth = 4;
    ctx.globalAlpha = 0.4;
    currentData.variants.forEach((v, i) => {
        ctx.strokeStyle = colors[i % colors.length];
        ctx.beginPath();
        ctx.moveTo(v.points[0].x, v.points[0].y);
        for (let j = 1; j < v.points.length; j++) {
            ctx.lineTo(v.points[j].x, v.points[j].y);
        }
        ctx.stroke();
    });
    ctx.globalAlpha = 1.0;

    // Draw active runners
    const tailDuration = parseFloat(tailInput.value) || 0;
    currentData.variants.forEach((v, i) => {
        const state = getInterpolatedState(v, currentTime);
        
        // Draw tail
        const tailTime = Math.max(0, currentTime - tailDuration);
        const tailState = getInterpolatedState(v, tailTime);
        
        ctx.strokeStyle = colors[i % colors.length];
        ctx.lineWidth = 6;
        ctx.beginPath();
        ctx.moveTo(tailState.x, tailState.y);
        
        // Vykresleni mezilehlych bodu pro ocásek
        for (let j = 0; j < v.points.length; j++) {
            const p = v.points[j];
            if (p.time > tailTime && p.time < currentTime) {
                ctx.lineTo(p.x, p.y);
            }
        }
        
        ctx.lineTo(state.x, state.y);
        ctx.stroke();
        
        // Draw runner head
        ctx.fillStyle = colors[i % colors.length];
        ctx.beginPath();
        ctx.arc(state.x, state.y, 10, 0, 2 * Math.PI);
        ctx.fill();
        ctx.strokeStyle = 'white';
        ctx.lineWidth = 2;
        ctx.stroke();
        
        // Label
        ctx.fillStyle = 'white';
        ctx.font = 'bold 16px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(String.fromCharCode(65 + i), state.x, state.y - 20);
    });
}

function drawControl(x, y, label, isStart, endPos) {
    ctx.strokeStyle = '#9400D3';
    ctx.lineWidth = 4;
    ctx.fillStyle = '#9400D3';
    ctx.font = 'bold 24px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    if (isStart && endPos) {
        const dx = endPos.x - x;
        const dy = endPos.y - y;
        const angle = Math.atan2(dy, dx);
        const r = 25;
        ctx.beginPath();
        for (let k = 0; k < 3; k++) {
            const a = angle + k * 2 * Math.PI / 3;
            const px = x + r * Math.cos(a);
            const py = y + r * Math.sin(a);
            if (k === 0) ctx.moveTo(px, py);
            else ctx.lineTo(px, py);
        }
        ctx.closePath();
        ctx.stroke();
    } else {
        ctx.beginPath();
        ctx.arc(x, y, 25, 0, 2 * Math.PI);
        ctx.stroke();
    }
    
    ctx.fillText(label, x, y);
}

init();
