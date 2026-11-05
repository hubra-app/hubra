/* Hubra service worker: the installed app's offline page and browser
 * notifications (Web Push).
 *
 * Only /offline.html is cached. Every page still loads from the network as
 * usual; when the network is gone, a page load shows the offline page
 * instead of the browser's error. API calls, assets and other requests are
 * not touched.
 *
 * Push: the server sends the text already in the member's language:
 * { title, body, club, url, tag }. A click opens (or focuses) the club app
 * on that page.
 */

const CACHE = 'hubra-offline-v1'
const OFFLINE_URL = '/offline.html'
// The offline page's script and icon, so it works without the network.
const OFFLINE_FILES = [OFFLINE_URL, '/offline.js', '/icon-192.png']

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll(OFFLINE_FILES.map((u) => new Request(u, { cache: 'reload' }))))
      .catch(() => undefined)
      .then(() => self.skipWaiting()),
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k.startsWith('hubra-') && k !== CACHE).map((k) => caches.delete(k))),
      )
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', (event) => {
  const req = event.request
  if (req.method !== 'GET') return
  const url = new URL(req.url)
  // The offline page's own files: the network first, the cached copy offline.
  if (url.origin === self.location.origin && OFFLINE_FILES.includes(url.pathname) && req.mode !== 'navigate') {
    event.respondWith(fetch(req).catch(() => caches.match(url.pathname).then((res) => res || Response.error())))
    return
  }
  if (req.mode !== 'navigate') return
  event.respondWith(
    fetch(req).catch(() =>
      caches.match(OFFLINE_URL).then((res) => res || Response.error()),
    ),
  )
})

self.addEventListener('push', (event) => {
  let data = {}
  try {
    data = event.data ? event.data.json() : {}
  } catch {
    data = { body: event.data ? event.data.text() : '' }
  }
  const title = data.club ? `${data.club}: ${data.title || ''}` : data.title || 'Hubra'
  event.waitUntil(
    self.registration.showNotification(title, {
      body: data.body || '',
      icon: '/icon-192.png',
      badge: '/favicon-32.png',
      tag: data.tag,
      data: { url: data.url || '/' },
    }),
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  // Only pages of this site.
  const url = new URL(event.notification.data?.url || '/', self.location.origin)
  if (url.origin !== self.location.origin) return
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windows) => {
      for (const win of windows) {
        if ('focus' in win && new URL(win.url).origin === url.origin) {
          return win.navigate(url.href).then((w) => (w || win).focus())
        }
      }
      return self.clients.openWindow(url.href)
    }),
  )
})
