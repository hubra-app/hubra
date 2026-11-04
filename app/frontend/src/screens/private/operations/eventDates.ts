import type { ClubEvent } from '@/types'

/** Over: its last day (the end date, else the date) is before today. */
export function isPastEvent(ev: Pick<ClubEvent, 'date' | 'endDate'>): boolean {
  const today = new Date()
  const y = today.getFullYear()
  const m = String(today.getMonth() + 1).padStart(2, '0')
  const d = String(today.getDate()).padStart(2, '0')
  return (ev.endDate || ev.date) < `${y}-${m}-${d}`
}
