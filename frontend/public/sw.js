/* Saaed service worker — deliberately conservative so it can NEVER pin users to a
   stale app: network-first for pages/API, cache-first only for immutable hashed
   assets (Vite emits content-hashed files in /assets/). */
const CACHE = "saaed-v1";

self.addEventListener("install", () => self.skipWaiting());

self.addEventListener("activate", (e) => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)));
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (e) => {
  const { request } = e;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return; // never touch the API / cross-origin

  // Immutable build assets → cache-first (fast, safe: filenames change on deploy).
  if (url.pathname.startsWith("/assets/")) {
    e.respondWith((async () => {
      const hit = await caches.match(request);
      if (hit) return hit;
      const res = await fetch(request);
      if (res.ok) (await caches.open(CACHE)).put(request, res.clone());
      return res;
    })());
    return;
  }

  // Everything else (navigations) → network-first, cached index as offline fallback.
  e.respondWith((async () => {
    try {
      const res = await fetch(request);
      if (request.mode === "navigate") (await caches.open(CACHE)).put("/", res.clone());
      return res;
    } catch {
      return (await caches.match(request)) || (await caches.match("/")) || Response.error();
    }
  })());
});
