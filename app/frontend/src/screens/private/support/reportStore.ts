import type { CaseKind } from '@/api/support'

// The account menu opens the report dialog and closes itself right away; the
// dialog lives in the shell and listens here.
let kind: CaseKind | null = null
const listeners = new Set<() => void>()

export function openReport(value: CaseKind | null) {
  kind = value
  listeners.forEach((l) => l())
}

export function subscribeReport(l: () => void) {
  listeners.add(l)
  return () => {
    listeners.delete(l)
  }
}

export function reportKind() {
  return kind
}
