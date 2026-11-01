import { apiFetch } from '@hubra/api-client'

/** Browser notifications (Web Push) for this device. */

export type PushState = 'unsupported' | 'needs-install' | 'denied' | 'off' | 'on'

const SW_URL = '/sw.js'

function supported(): boolean {
  return (
    typeof window !== 'undefined' &&
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    'Notification' in window
  )
}

/** iPhones and iPads only allow push for an app added to the home screen. */
function iosBrowserTab(): boolean {
  const ios = /iPad|iPhone|iPod/.test(navigator.userAgent) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
  const standalone =
    window.matchMedia?.('(display-mode: standalone)').matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true
  return ios && !standalone
}

function keyBytes(base64url: string): Uint8Array<ArrayBuffer> {
  const pad = '='.repeat((4 - (base64url.length % 4)) % 4)
  const raw = atob((base64url + pad).replace(/-/g, '+').replace(/_/g, '/'))
  const out = new Uint8Array(new ArrayBuffer(raw.length))
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i)
  return out
}

async function registration(): Promise<ServiceWorkerRegistration> {
  return (await navigator.serviceWorker.getRegistration(SW_URL)) ??
    navigator.serviceWorker.register(SW_URL, { scope: '/' })
}

interface PushSetup {
  public_key: string
  subscribed: boolean
}

export async function pushState(): Promise<PushState> {
  if (!supported()) return iosBrowserTab() ? 'needs-install' : 'unsupported'
  if (Notification.permission === 'denied') return 'denied'
  const reg = await navigator.serviceWorker.getRegistration(SW_URL)
  const sub = await reg?.pushManager.getSubscription()
  if (!sub) return 'off'
  const setup = await apiFetch<PushSetup>(
    `/account/push?endpoint=${encodeURIComponent(sub.endpoint)}`,
  )
  return setup.subscribed ? 'on' : 'off'
}

export async function enablePush(): Promise<PushState> {
  if (!supported()) return iosBrowserTab() ? 'needs-install' : 'unsupported'
  const permission = await Notification.requestPermission()
  if (permission !== 'granted') return permission === 'denied' ? 'denied' : 'off'
  const setup = await apiFetch<PushSetup>('/account/push')
  const reg = await registration()
  await navigator.serviceWorker.ready
  let sub = await reg.pushManager.getSubscription()
  // A subscription made with another server key cannot be used.
  const current = sub?.options.applicationServerKey
  if (sub && current) {
    const want = keyBytes(setup.public_key)
    const have = new Uint8Array(current)
    if (have.length !== want.length || have.some((b, i) => b !== want[i])) {
      await sub.unsubscribe()
      sub = null
    }
  }
  sub ??= await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: keyBytes(setup.public_key),
  })
  await apiFetch('/account/push', { method: 'POST', body: JSON.stringify(sub.toJSON()) })
  return 'on'
}

export async function disablePush(): Promise<PushState> {
  const reg = supported() ? await navigator.serviceWorker.getRegistration(SW_URL) : undefined
  const sub = await reg?.pushManager.getSubscription()
  if (sub) {
    await apiFetch('/account/push', {
      method: 'DELETE',
      body: JSON.stringify({ endpoint: sub.endpoint }),
    })
    await sub.unsubscribe()
  }
  return 'off'
}
