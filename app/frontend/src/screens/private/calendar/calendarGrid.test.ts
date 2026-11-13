import { describe, expect, it } from 'vitest'
import type { CalendarItem } from '@/api/calendar'
import { isoDay, itemsOn, monthWeeks, timeOf, weekDays } from './calendarGrid'

const item = (over: Partial<CalendarItem>): CalendarItem => ({
  id: 'x', title: 'X', kind: 'event', start: '2030-06-06T18:30:00', end: null, all_day: false,
  location: null, path: null, group_id: null, color: null, cancelled: false, source: 'events', ...over,
})

describe('calendar grid', () => {
  it('June 2030 starts on the Monday before and ends with the week of the 30th', () => {
    const weeks = monthWeeks(new Date(2030, 5, 15))
    expect(isoDay(weeks[0][0])).toBe('2030-05-27')
    expect(isoDay(weeks[weeks.length - 1][6])).toBe('2030-06-30')
    expect(weeks.every((w) => w.length === 7)).toBe(true)
  })
  it('a week runs Monday to Sunday', () => {
    const days = weekDays(new Date(2030, 5, 6))
    expect([isoDay(days[0]), isoDay(days[6])]).toEqual(['2030-06-03', '2030-06-09'])
  })
  it('all-day items span their days and come first', () => {
    const items = [
      item({ id: 'a', title: 'Training' }),
      item({ id: 'b', title: 'Lager', all_day: true, start: '2030-06-05T00:00:00', end: '2030-06-07T00:00:00' }),
    ]
    expect(itemsOn(items, '2030-06-06').map((i) => i.title)).toEqual(['Lager', 'Training'])
    expect(itemsOn(items, '2030-06-08')).toEqual([])
    expect(timeOf(items[0])).toBe('18:30')
    expect(timeOf(items[1])).toBe('')
  })
})
