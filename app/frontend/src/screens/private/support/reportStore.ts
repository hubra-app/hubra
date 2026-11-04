import type { Area, CaseKind } from '@/api/support'

// The account menu opens the report dialog and closes itself right away; the
// dialog lives in the shell and listens here.
export interface ReportRequest {
  kind: CaseKind
  /** Preselects the area, e.g. "modules" from Settings › Module. */
  area?: Area
}

let request: ReportRequest | null = null
const listeners = new Set<() => void>()

export function openReport(kind: CaseKind | null, options: { area?: Area } = {}) {
  request = kind ? { kind, ...options } : null
  listeners.forEach((l) => l())
}

export function subscribeReport(l: () => void) {
  listeners.add(l)
  return () => {
    listeners.delete(l)
  }
}

export function reportRequest() {
  return request
}
