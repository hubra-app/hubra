import { describe, expect, it } from 'vitest'
import { joinTime, splitTime } from './eventTime'

describe('splitTime', () => {
  it('reads a range', () => {
    expect(splitTime('14:00–18:00')).toEqual({ timeFrom: '14:00', timeTo: '18:00', timeText: '' })
    expect(splitTime('9.30 - 11.00 Uhr')).toEqual({ timeFrom: '09:30', timeTo: '11:00', timeText: '' })
    expect(splitTime('18:00 bis 20:00')).toEqual({ timeFrom: '18:00', timeTo: '20:00', timeText: '' })
  })

  it('reads a start time alone', () => {
    expect(splitTime('19:00')).toEqual({ timeFrom: '19:00', timeTo: '', timeText: '' })
  })

  it('keeps any other text', () => {
    expect(splitTime('ab Mittag')).toEqual({ timeFrom: '', timeTo: '', timeText: 'ab Mittag' })
    expect(splitTime('25:00')).toEqual({ timeFrom: '', timeTo: '', timeText: '25:00' })
    expect(splitTime(null)).toEqual({ timeFrom: '', timeTo: '', timeText: '' })
  })
})

describe('joinTime', () => {
  it('writes von–bis', () => {
    expect(joinTime({ timeFrom: '14:00', timeTo: '18:00', timeText: '' })).toBe('14:00–18:00')
    expect(joinTime({ timeFrom: '14:00', timeTo: '', timeText: '' })).toBe('14:00')
  })

  it('keeps the old text until a time is picked', () => {
    expect(joinTime({ timeFrom: '', timeTo: '', timeText: 'ab Mittag' })).toBe('ab Mittag')
    expect(joinTime({ timeFrom: '10:00', timeTo: '', timeText: 'ab Mittag' })).toBe('10:00')
  })
})
