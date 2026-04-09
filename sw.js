// sw.js — Hike Planner Service Worker
// Cache version: increment CACHE_VER when deploying significant updates
// to force clients to download fresh files.
const CACHE_VER = 'v1';
const CACHE_NAME = 'hike-planner-' + CACHE_VER;

// Files to pre-cache on install.
// Trail data files are large — we cache them on first fetch (below)
// rather than pre-caching all of them upfront.
const PRECACHE_URLS = [
  '/hike_planner/',
  '/hike_planner/index.html',
  '/hike_planner/manifest.json',
  '/hike_planner/registry.json',
];

// ── Install: pre-cache core shell ────────────────────────────────────────────
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  );
});

// ── Activate: delete old caches ───────────────────────────────────────────────
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys
          .filter(key => key.startsWith('hike-planner-') && key !== CACHE_NAME)
          .map(key => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

// ── Fetch: serve from cache, fall back to network ────────────────────────────
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Never cache map tiles — too large, always dynamic
  if (url.hostname.includes('opentopomap.org') ||
      url.hostname.includes('openstreetmap.org') ||
      url.hostname.includes('nationalmap.gov') ||
      url.hostname.includes('fonts.googleapis.com') ||
      url.hostname.includes('fonts.gstatic.com') ||
      url.hostname.includes('cdnjs.cloudflare.com')) {
    event.respondWith(fetch(event.request));
    return;
  }

  // Cache-first for all same-origin requests (trail data, app shell)
  // On cache miss: fetch from network and cache the response for next time
  if (url.origin === self.location.origin) {
    event.respondWith(
      caches.match(event.request)
        .then(cached => {
          if (cached) return cached;
          return fetch(event.request)
            .then(response => {
              // Only cache successful responses to same-origin URLs
              if (!response || response.status !== 200 || response.type !== 'basic') {
                return response;
              }
              const toCache = response.clone();
              caches.open(CACHE_NAME)
                .then(cache => cache.put(event.request, toCache));
              return response;
            });
        })
    );
    return;
  }

  // All other requests (cross-origin non-tile): network only
  event.respondWith(fetch(event.request));
});
