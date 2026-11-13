import { describe, expect, it } from 'vitest'
import { isOn, toggle } from './postChannels'

const ALL = ['app', 'discord', 'messengers']

describe('post channels', () => {
  it('null means every channel', () => {
    expect(isOn(null, 'discord')).toBe(true)
  })
  it('switching one off keeps the others in their order', () => {
    expect(toggle(null, 'discord', ALL)).toEqual(['app', 'messengers'])
  })
  it('every channel on again is null', () => {
    expect(toggle(['app', 'messengers'], 'discord', ALL)).toBeNull()
  })
  it('all off is an empty list (only in the feed)', () => {
    expect(toggle(['app'], 'app', ALL)).toEqual([])
  })
})
