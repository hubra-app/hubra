/* Hubra service worker: shows browser notifications (Web Push).
 *
 * The server sends the text already in the member's language:
 * { title, body, club, url, tag }. A click opens (or focuses) the club app
 * on that page. Nothing is cached here; the app loads as usual.
 */

self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()))

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
