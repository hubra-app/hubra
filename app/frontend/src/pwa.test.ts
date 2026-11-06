import { afterEach, describe, expect, it } from 'vitest'
import { lastClubPath, pwaStartPath, rememberClub } from './pwa'

describe('pwaStartPath', () => {
  afterEach(() => localStorage.clear())

  it('ignores a normal visit to /', () => {
    rememberClub('demo')
    expect(pwaStartPath('')).toBeNull()
  })

  it('opens the last club when the installed app starts', () => {
    rememberClub('demo')
    expect(pwaStartPath('?source=pwa')).toBe('/demo/app/dashboard')
  })

  it('follows a shortcut below /app/', () => {
    rememberClub('demo')
    expect(pwaStartPath('?source=pwa&to=%2Fapp%2Foperations%2Fevents')).toBe('/demo/app/operations/events')
  })

  it('refuses shortcut targets outside the app', () => {
    rememberClub('demo')
    expect(pwaStartPath('?source=pwa&to=https://evil.test')).toBe('/demo/app/dashboard')
    expect(pwaStartPath('?source=pwa&to=//evil.test/app/')).toBe('/demo/app/dashboard')
    expect(pwaStartPath('?source=pwa&to=%2Fapp%2F..%2F..%2Fx')).toBe('/demo/app/dashboard')
  })

  it('falls back to the sign-in without a remembered club', () => {
    expect(pwaStartPath('?source=pwa')).toBeNull()
    localStorage.setItem('hubra.lastClub', '../evil')
    expect(pwaStartPath('?source=pwa')).toBeNull()
  })
})

describe('lastClubPath', () => {
  afterEach(() => localStorage.clear())

  it('puts the club used last in front of an in-app path', () => {
    rememberClub('demo')
    expect(lastClubPath('/app/dashboard/me')).toBe('/demo/app/dashboard/me')
  })

  it('is null before a club was opened, or for a bad slug', () => {
    expect(lastClubPath('/app/dashboard/me')).toBeNull()
    localStorage.setItem('hubra.lastClub', '../evil')
    expect(lastClubPath('/app/dashboard/me')).toBeNull()
  })
})
