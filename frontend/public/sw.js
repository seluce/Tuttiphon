// Tuttiphon as an app: always loads fresh from the server first (updates visible right away), offline the last
// loaded interface. Data (/api, images) always goes straight to the server.
// The files of older versions are removed from the cache as soon as a page of a new version is loaded.
// Notifications (Web Push, app/webpush.py): shows them; tapping one opens Tuttiphon at the matching place.
const CACHE = "tuttiphon-v3";
const BUILD = "/__build";   // cache entry: the files the last loaded app page (index.html) refers to
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(
  caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim())));

/** A page was loaded: if it refers to other files than the last one (new version), drop the old versions' files.
 *  Files loaded later by the new version (pages of their own, texts) are cached again when they are used. */
async function prune(html) {
  const files = [...new Set(html.match(/\/assets\/[^"'\s)]+/g) || [])].sort();
  if (!files.length) return;
  const cache = await caches.open(CACHE);
  const known = await cache.keys();   // right away: files the new version caches meanwhile stay
  const before = await cache.match(BUILD).then((r) => (r ? r.json() : null)).catch(() => null);
  if (before && before.every((f) => files.includes(f)) && files.every((f) => before.includes(f))) return;
  await cache.put(BUILD, new Response(JSON.stringify(files), { headers: { "Content-Type": "application/json" } }));
  if (!before) return;   // first time: nothing known to be old
  for (const req of known) {
    const path = new URL(req.url).pathname;
    if (path.startsWith("/assets/") && !files.includes(path)) await cache.delete(req);
  }
}

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin || /^\/(api|img|live|cover)\b/.test(url.pathname) || url.pathname === BUILD) return;
  e.respondWith(fetch(e.request).then((res) => {
    if (res.ok && res.type === "basic") {
      const copy = res.clone();
      e.waitUntil(caches.open(CACHE).then((c) => c.put(e.request, copy)));
      if (e.request.mode === "navigate" && /^\/(index\.html)?$/.test(url.pathname)) { const page = res.clone(); e.waitUntil(page.text().then(prune).catch(() => {})); }
    }
    return res;
  }).catch(() => caches.match(e.request).then((hit) => hit || caches.match("/"))));
});
self.addEventListener("push", (e) => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch { d = { body: e.data ? e.data.text() : "" }; }
  e.waitUntil(self.registration.showNotification(d.title || "Tuttiphon", {
    body: d.body || "", icon: "/icons/icon-192.png", badge: "/icons/icon-192.png", tag: d.tag || undefined,
    data: { url: d.url || "/" } }));
});
self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || "/";
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
    for (const c of list) {
      if ("focus" in c) { if ("navigate" in c) c.navigate(url).catch(() => {}); return c.focus(); }
    }
    return self.clients.openWindow(url);
  }));
});
