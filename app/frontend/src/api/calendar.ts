import { apiFetch } from '@hubra/api-client'

/** One dated thing in the club calendar: an event, a booking, a fixture … */
export interface CalendarItem {
  id: string
  title: string
  /** "event", "booking", …: the filter and the colour. */
  kind: string
  /** Local club time, "YYYY-MM-DDTHH:MM:SS". */
  start: string
  end: string | null
  all_day: boolean
  location: string | null
  /** Where the club app opens it (/app/…). */
  path: string | null
  group_id: number | null
  color: string | null
  cancelled: boolean
  /** The module it comes from. */
  source: string
}

export interface CalendarResponse {
  items: CalendarItem[]
  /** Modules that answered. */
  sources: string[]
  /** Modules that could not answer right now. */
  failed: string[]
}

/** Every module's items from *start* to *end* (YYYY-MM-DD, both included). */
export function getCalendar(start: string, end: string, signal?: AbortSignal): Promise<CalendarResponse> {
  const q = new URLSearchParams({ start, end })
  return apiFetch(`/app/calendar/?${q}`, { signal })
}
