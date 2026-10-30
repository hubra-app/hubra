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
