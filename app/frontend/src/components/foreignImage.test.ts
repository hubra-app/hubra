import { describe, expect, it } from 'vitest'
import { foreignImageHost } from './foreignImage'

const here = 'https://app.hubra.club/club/app/posts'
const api = 'https://api.hubra.club/api/v1'

describe('foreignImageHost', () => {
  it('lets images of this site, data: and blob: load', () => {
    expect(foreignImageHost('/logo.png', here, api)).toBeNull()
    expect(foreignImageHost('https://app.hubra.club/x.png', here, api)).toBeNull()
    expect(foreignImageHost('data:image/png;base64,AAAA', here, api)).toBeNull()
    expect(foreignImageHost('blob:https://app.hubra.club/123', here, api)).toBeNull()
    expect(foreignImageHost(undefined, here, api)).toBeNull()
  })

  it('names the host of an image on another site', () => {
    expect(foreignImageHost('https://tracker.example/p.gif', here, api)).toBe('tracker.example')
    expect(foreignImageHost('//cdn.example.org/a.png', here, api)).toBe('cdn.example.org')
    expect(foreignImageHost('https://api.hubra.club/x.png', here, api)).toBeNull()
    expect(foreignImageHost('https://evil.hubra.club.example/x.png', here, api)).toBe('evil.hubra.club.example')
  })
})
