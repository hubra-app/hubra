// The user menu opens "Seitenleiste anpassen" but closes right away, so the
// dialog lives in the shell and listens here (like "Neuigkeiten").
let open = false
const listeners = new Set<() => void>()

export function setCustomizeSidebarOpen(value: boolean) {
  open = value
  listeners.forEach((l) => l())
}

export function subscribeCustomizeSidebar(l: () => void) {
  listeners.add(l)
  return () => {
    listeners.delete(l)
  }
}

export function customizeSidebarOpen() {
  return open
}
