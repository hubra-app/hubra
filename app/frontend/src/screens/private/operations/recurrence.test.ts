import { describe, expect, it } from 'vitest'
import { ruleDates } from './recurrence'

describe('ruleDates', () => {
  it('makes the same dates as the server', () => {
    // As tests/events/test_event_series.py: Tuesdays and Thursdays, every
    // other week, without the 15th (2030-01-01 is a Tuesday).
    expect(
      ruleDates('2030-01-01', {
        until: '2030-01-31',
        interval: 2,
        weekdays: [1, 3],
        skipDates: ['2030-01-15'],
      }),
    ).toEqual(['2030-01-01', '2030-01-03', '2030-01-17', '2030-01-29', '2030-01-31'])
  })

  it('keeps skipped dates when asked, and defaults to the first weekday', () => {
    const rule = { until: '2030-01-15', interval: 1, weekdays: [], skipDates: ['2030-01-08'] }
    expect(ruleDates('2030-01-01', rule)).toEqual(['2030-01-01', '2030-01-15'])
    expect(ruleDates('2030-01-01', rule, true)).toEqual([
      '2030-01-01',
      '2030-01-08',
      '2030-01-15',
    ])
    // No weekdays given: the first date's weekday (a Thursday here).
    expect(ruleDates('2030-01-10', rule)).toEqual(['2030-01-10'])
  })
})
