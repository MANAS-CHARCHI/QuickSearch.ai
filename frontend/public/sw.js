// Vault City PWA Service Worker
const CACHE_NAME = 'vaultcity-pwa-v1';

// Static application shell assets
const PRECACHE_URLS = [
  '/',
  '/index.html',
  '/favicon.svg',
  '/favicon.ico',
  '/favicon-32x32.png',
  '/favicon-16x16.png',
  '/apple-touch-icon.png',
  '/icon-192.png',
  '/icon-512.png',
  '/icon-512-maskable.png',
  '/site.webmanifest',
];

// Installation: pre-cache static shell assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
      .catch((err) => {
        console.warn('[PWA SW] Pre-caching warning:', err);
      })
  );
});

// Activation: delete stale caches and claim all clients
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((cacheNames) =>
        Promise.all(
          cacheNames.map((name) => {
            if (name !== CACHE_NAME) {
              return caches.delete(name);
            }
          })
        )
      )
      .then(() => self.clients.claim())
  );
});

// Fetch interceptor with tailored caching strategies
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // 1. Only process GET requests
  if (request.method !== 'GET') {
    return;
  }

  // 2. Ignore non-http schemes (e.g. chrome-extension://)
  if (!url.protocol.startsWith('http')) {
    return;
  }

  // 3. API & Auth requests -> Network-First (never stale, structured offline json fallback)
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/auth/')) {
    event.respondWith(
      fetch(request).catch(() => {
        return new Response(
          JSON.stringify({
            offline: true,
            detail: 'You are currently offline. Real-time encryption & vault features require an internet connection.',
          }),
          {
            status: 503,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      })
    );
    return;
  }

  // 4. Static assets (JS, CSS, fonts, icons) -> Cache-First with Network background refresh
  if (
    url.pathname.startsWith('/assets/') ||
    url.pathname.match(/\.(js|css|png|jpg|jpeg|svg|ico|webp|woff|woff2|ttf|eot)$/)
  ) {
    event.respondWith(
      caches.match(request).then((cachedResponse) => {
        if (cachedResponse) {
          // Revalidate cache in background
          fetch(request)
            .then((networkResponse) => {
              if (networkResponse && networkResponse.status === 200) {
                caches.open(CACHE_NAME).then((cache) => cache.put(request, networkResponse));
              }
            })
            .catch(() => {});
          return cachedResponse;
        }

        return fetch(request)
          .then((networkResponse) => {
            if (networkResponse && networkResponse.status === 200) {
              const toCache = networkResponse.clone();
              caches.open(CACHE_NAME).then((cache) => cache.put(request, toCache));
            }
            return networkResponse;
          })
          .catch(() => {
            if (url.pathname.match(/\.(png|jpg|jpeg|svg|ico|webp)$/)) {
              return caches.match('/favicon.svg');
            }
            return new Response('', { status: 408 });
          });
      })
    );
    return;
  }

  // 5. Navigation requests (HTML SPA) -> Network-First with /index.html offline shell fallback
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            const toCache = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, toCache));
          }
          return networkResponse;
        })
        .catch(async () => {
          const cachedIndex = await caches.match('/index.html');
          if (cachedIndex) return cachedIndex;
          const cachedRoot = await caches.match('/');
          if (cachedRoot) return cachedRoot;
          return new Response('Vault City is offline. Please reconnect to access your encrypted documents.', {
            status: 503,
            headers: { 'Content-Type': 'text/plain' },
          });
        })
    );
    return;
  }

  // 6. Default strategy: Cache-First, fallback to Network
  event.respondWith(
    caches.match(request).then((cached) => cached || fetch(request))
  );
});

// Skip waiting message listener for instant updates
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
