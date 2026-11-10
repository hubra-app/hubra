import { apiFetch } from '@hubra/api-client'

/** One thing the club search found, in a module that offers `<module>.search`. */
export interface SearchHit {
  id: string
  label: string
  sub: string | null
  /** A day that goes with it (YYYY-MM-DD), shown before `sub`. */
  date?: string | null
  /** Where the club app opens it (/app/…). */
  path: string
  /** "member", "event", "invoice", …: the badge in the result list. */
  kind: string
  /** The module it comes from. */
  source: string
}

/** Up to five hits per module the member may see. *q*: 2 to 100 characters. */
export function searchClub(q: string, signal?: AbortSignal): Promise<{ hits: SearchHit[]; failed: string[] }> {
  return apiFetch(`/app/search/?${new URLSearchParams({ q })}`, { signal })
}
