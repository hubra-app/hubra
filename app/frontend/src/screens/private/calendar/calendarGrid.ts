import type { CalendarItem } from '@/api/calendar'

/** "YYYY-MM-DD" of a local date. */
export function isoDay(d: Date): string {
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${mm}-${dd}`
}

function addDays(d: Date, n: number): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() + n)
}

/** The Monday on or before *d*. */
export function mondayOf(d: Date): Date {
  return addDays(d, -((d.getDay() + 6) % 7))
}

/** The weeks (Monday to Sunday) that show the month of *d*. */
export function monthWeeks(d: Date): Date[][] {
  const first = new Date(d.getFullYear(), d.getMonth(), 1)
  const last = new Date(d.getFullYear(), d.getMonth() + 1, 0)
  const weeks: Date[][] = []
  for (let day = mondayOf(first); day <= last; day = addDays(day, 7)) {
    weeks.push(Array.from({ length: 7 }, (_, i) => addDays(day, i)))
  }
  return weeks
}

/** The week (Monday to Sunday) around *d*. */
export function weekDays(d: Date): Date[] {
  const monday = mondayOf(d)
  return Array.from({ length: 7 }, (_, i) => addDays(monday, i))
}

/** First and last day a view shows, as YYYY-MM-DD. */
export function viewRange(days: Date[]): { start: string; end: string } {
  return { start: isoDay(days[0]), end: isoDay(days[days.length - 1]) }
}

/** The items on *day*: those starting that day, and all-day items that
 * span it (an all-day end is the last day, included). Timed items first by
 * time, all-day ones on top. */
export function itemsOn(items: CalendarItem[], day: string): CalendarItem[] {
  return items
    .filter((i) => {
      const start = i.start.slice(0, 10)
      if (!i.all_day || !i.end) return start === day
      return start <= day && day <= i.end.slice(0, 10)
    })
    .sort((a, b) => Number(b.all_day) - Number(a.all_day) || a.start.localeCompare(b.start))
}

/** "18:30" of a timed item, "" for all-day ones. */
export function timeOf(item: CalendarItem): string {
  return item.all_day ? '' : item.start.slice(11, 16)
}
