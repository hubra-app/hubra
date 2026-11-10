import { describe, expect, it } from 'vitest'
import { templateExtras } from './templateExtras'

describe('templateExtras', () => {
  it('keeps the fields the form has no field for', () => {
    expect(
      templateExtras(
        { meeting_url: 'https://meet.example/x', category: 'training', color: '#ff0000', all_day: true },
        '2030-06-06',
      ),
    ).toEqual({ meetingUrl: 'https://meet.example/x', category: 'training', color: '#ff0000', allDay: true })
  })

  it('keeps the length of a multi-day event from the new date', () => {
    expect(templateExtras({ days: 2 }, '2030-12-31').endDate).toBe('2031-01-02')
  })

  it('adds nothing without a template', () => {
    expect(templateExtras(null, '2030-06-06')).toEqual({})
  })
})
