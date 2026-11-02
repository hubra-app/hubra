// The user menu opens "Neuigkeiten", but the menu closes right away; the
// dialog lives in the top bar and listens here.
let open = false
const listeners = new Set<() => void>()

export function setWhatsNewOpen(value: boolean) {
  open = value
  listeners.forEach((l) => l())
}

export function subscribeWhatsNew(l: () => void) {
  listeners.add(l)
  return () => {
    listeners.delete(l)
  }
}

export function whatsNewOpen() {
  return open
}

// The newest release notes this browser has opened (see latestReleaseKey),
// so the menu can mark "Neuigkeiten" until they are read.
const SEEN_KEY = 'hubra_whats_new_seen'
let seen: string | null = null
try {
  seen = localStorage.getItem(SEEN_KEY)
} catch {
  /* private mode: every visit starts unseen */
}

export function markWhatsNewSeen(key: string | null) {
  if (!key || key === seen) return
  seen = key
  try {
    localStorage.setItem(SEEN_KEY, key)
  } catch {
    /* keep it for this visit */
  }
  listeners.forEach((l) => l())
}

export function whatsNewSeen() {
  return seen
}
