/**
 * Installable app (PWA): the service worker, the browser's install prompt
 * and where the installed app opens.
 *
 * The manifest's start_url is `/?source=pwa`. The app on its own has no club
 * in that URL, so it opens the club this device used last (remembered on
 * every club page) and falls back to the sign-in.
 */
import { useSyncExternalStore } from 'react'

const SW_URL = '/sw.js'
const LAST_CLUB_KEY = 'hubra.lastClub'

interface InstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

let deferred: InstallPromptEvent | null = null
let installed = false
const listeners = new Set<() => void>()
const emit = () => listeners.forEach((l) => l())

/** Running as the installed app (home screen, dock, app window). */
export function isStandalone(): boolean {
  if (typeof window === 'undefined') return false
  return (
    window.matchMedia?.('(display-mode: standalone)').matches ||
    window.matchMedia?.('(display-mode: window-controls-overlay)').matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true
  )
}

/** iPhone and iPad: Safari has no install prompt, only Share › Add to Home Screen. */
export function isIos(): boolean {
  if (typeof navigator === 'undefined') return false
  return (
    /iPad|iPhone|iPod/.test(navigator.userAgent) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
  )
}

/** Register the service worker and listen for the install prompt. Call once at start. */
export function setupPwa(): void {
  if (typeof window === 'undefined') return
  window.addEventListener('beforeinstallprompt', (e) => {
    // Keep the prompt for the "Install" button instead of the browser's mini bar.
    e.preventDefault()
    deferred = e as InstallPromptEvent
    emit()
  })
  window.addEventListener('appinstalled', () => {
    deferred = null
    installed = true
    emit()
  })
  if ('serviceWorker' in navigator && import.meta.env.PROD) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register(SW_URL, { scope: '/' }).catch(() => {
        /* No offline page then; the app works as before. */
      })
    })
  }
}

export type InstallState = 'installed' | 'prompt' | 'ios' | 'unavailable'

function installState(): InstallState {
  if (installed || isStandalone()) return 'installed'
  if (deferred) return 'prompt'
  if (isIos()) return 'ios'
  return 'unavailable'
}

/** Whether this device can install Hubra right now, and how. */
export function useInstallState(): InstallState {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb)
      return () => listeners.delete(cb)
    },
    installState,
    () => 'unavailable' as InstallState,
  )
}

/** Show the browser's install dialog. True when the person installed it. */
export async function promptInstall(): Promise<boolean> {
  const e = deferred
  if (!e) return false
  await e.prompt()
  const { outcome } = await e.userChoice
  deferred = null
  if (outcome === 'accepted') installed = true
  emit()
  return outcome === 'accepted'
}

/** Remember the club this device uses, so the installed app opens it. */
export function rememberClub(club: string): void {
  try {
    localStorage.setItem(LAST_CLUB_KEY, club)
  } catch {
    /* private mode */
  }
}

/**
 * Where `/` should go when the installed app starts: the last club's page,
 * or null (then the usual sign-in). `to` is an in-app path from a manifest
 * shortcut and must stay below /app/.
 */
export function pwaStartPath(search: string): string | null {
  const params = new URLSearchParams(search)
  if (params.get('source') !== 'pwa') return null
  let club: string | null
  try {
    club = localStorage.getItem(LAST_CLUB_KEY)
  } catch {
    return null
  }
  if (!club || !/^[a-z0-9][a-z0-9-]{0,62}$/i.test(club)) return null
  const to = params.get('to') ?? ''
  const path = /^\/app\/[a-z0-9/_-]*$/i.test(to) && !to.includes('//') ? to : '/app/dashboard'
  return `/${encodeURIComponent(club)}${path}`
}
