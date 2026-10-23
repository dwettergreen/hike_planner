// sw.js — Hike Planner Service Worker
//
// Strategy: NETWORK-FIRST for all same-origin files (app shell and trail data).
//   - Online: always fetch the current file (HTTP revalidation via ETag makes
//     unchanged files cheap, a 304), update the cache, and serve it.
//   - Offline or slow (no response within NETWORK_TIMEOUT_MS): serve the cached
//     copy if there is one.
// Deploys therefore reach installed apps on the next launch without bumping
// CACHE_VER. Bump CACHE_VER only to discard old caches entirely.
//
// Map tiles, fonts and CDN libraries are network-only (never cached).

const CACHE_VER = 'v3';
const CACHE_NAME = 'hike-planner-' + CACHE_VER;
const NETWORK_TIMEOUT_MS = 4000;

// Core shell, relative to this worker's scope.
const PRECACHE_PATHS = ['./', 'index.html', 'manifest.json', 'registry.json'];

const NETWORK_ONLY_HOSTS = [
  'opentopomap.org', 'openstreetmap.org', 'nationalmap.gov',
  'fonts.googleapis.com', 'fonts.gstatic.com', 'cdnjs.cloudflare.com',
];

// ── Install: pre-cache core shell (bypassing the HTTP cache) ─────────────────
self.addEventListener('install', event => {
  const urls = PRECACHE_PATHS.map(p => new URL(p, self.registration.scope).href);
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urls.map(u => new Request(u, { cache: 'reload' }))))
      .then(() => self.skipWaiting())
  );
});

// ── Activate: delete old caches, take control of open pages ─────────────────
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

// Fetch from the network (revalidating the HTTP cache); store good responses.
function fetchAndCache(request) {
  return fetch(request, { cache: 'no-cache' }).then(response => {
    if (response && response.status === 200 && response.type === 'basic') {
      const copy = response.clone();
      caches.open(CACHE_NAME).then(cache => cache.put(request, copy));
    }
    return response;
  });
}

// Network-first with a timeout fallback to the cache.
function networkFirst(request) {
  const network = fetchAndCache(request);
  const timeout = new Promise(resolve =>
    setTimeout(() => resolve(null), NETWORK_TIMEOUT_MS));
  return Promise.race([network.catch(() => null), timeout])
    .then(response => response ||
      caches.match(request, { ignoreSearch: true })
        .then(cached => cached || network));   // no cached copy: wait for the network
}

// ── Fetch ────────────────────────────────────────────────────────────────────
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);

  if (NETWORK_ONLY_HOSTS.some(h => url.hostname.includes(h))) {
    event.respondWith(fetch(event.request));
    return;
  }
  if (url.origin === self.location.origin) {
    event.respondWith(networkFirst(event.request));
    return;
  }
  event.respondWith(fetch(event.request));
});
