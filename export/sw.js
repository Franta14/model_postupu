const CACHE_NAME = 'model-postupu-cache-v22';

self.addEventListener('install', event => {
    // Instalace proběhne rychle, nebudeme čekat na obří preload
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    // Smaže staré verze cache
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cache => {
                    if (cache !== CACHE_NAME) {
                        return caches.delete(cache);
                    }
                })
            );
        })
    );
    self.clients.claim();
});

// Rozdělená strategie: Dlaždice Cache-First, Zbytek Network-First
self.addEventListener('fetch', event => {
    if (event.request.method !== 'GET') return;
    
    const url = new URL(event.request.url);

    // 1. Dlaždice a data postupů - Cache First (nikdy se nemění)
    if (url.pathname.includes('/tiles/') || url.pathname.includes('/postupy/')) {
        event.respondWith(
            caches.match(event.request).then(cachedResponse => {
                if (cachedResponse) return cachedResponse;
                return fetch(event.request).then(networkResponse => {
                    if (networkResponse && networkResponse.status === 200) {
                        let responseToCache = networkResponse.clone();
                        caches.open(CACHE_NAME).then(cache => {
                            cache.put(event.request, responseToCache);
                        });
                    }
                    return networkResponse;
                }).catch(() => {});
            })
        );
    } 
    // 2. Aplikace (HTML, CSS, JS) - Network First s 'no-cache' (vynutí čerstvou verzi)
    else {
        event.respondWith(
            fetch(event.request, { cache: 'no-store' }).then(networkResponse => {
                if (networkResponse && networkResponse.status === 200) {
                    let responseToCache = networkResponse.clone();
                    caches.open(CACHE_NAME).then(cache => {
                        cache.put(event.request, responseToCache);
                    });
                }
                return networkResponse;
            }).catch(() => {
                // Offline fallback z cache
                return caches.match(event.request);
            })
        );
    }
});
