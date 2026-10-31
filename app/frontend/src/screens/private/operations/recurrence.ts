import type { Recurrence } from '@/types'

/** The repeat options of the event form; `on` false means a single date. */
export interface RepeatState extends Recurrence {
  on: boolean
}

const DAY = 86_400_000

const iso = (d: Date) => d.toISOString().slice(0, 10)
const parse = (s: string) => new Date(`${s}T00:00:00Z`)
/** Monday 0 … Sunday 6, as the server counts. */
const weekday = (d: Date) => (d.getUTCDay() + 6) % 7

/** The dates of a weekly rule, as the server makes them (without the
 * skipped ones when `withSkipped` is false). */
export function ruleDates(start: string, r: Recurrence, withSkipped = false): string[] {
  if (!start || !r.until || r.until < start) return []
  const from = parse(start)
  const until = parse(r.until)
  const week0 = from.getTime() - weekday(from) * DAY
  const days = new Set(r.weekdays.length ? r.weekdays : [weekday(from)])
  const skip = new Set(r.skipDates)
  const out: string[] = []
  for (let t = from.getTime(); t <= until.getTime() && out.length <= 400; t += DAY) {
    const d = new Date(t)
    const week = Math.floor((t - week0) / (7 * DAY))
    if (days.has(weekday(d)) && week % r.interval === 0 && (withSkipped || !skip.has(iso(d)))) {
      out.push(iso(d))
    }
  }
  return out
}

/** A fresh rule for a first date: that weekday, weekly, for three months. */
export function defaultRepeat(start: string, from?: Recurrence | null): RepeatState {
  if (from) return { on: true, ...from, skipDates: [...from.skipDates] }
  const d = start ? parse(start) : new Date()
  const until = new Date(d.getTime() + 13 * 7 * DAY)
  return { on: false, until: iso(until), interval: 1, weekdays: [weekday(d)], skipDates: [] }
}
