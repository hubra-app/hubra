import { describe, expect, it } from 'vitest'
import { sharingBody, sharingOf, sharingValid } from './sharing'

describe('dashboard sharing', () => {
  it('reads private, club and groups from a dashboard', () => {
    expect(sharingOf({ shared: false, groups: [] })).toEqual({
      visibility: 'private',
      groupIds: [],
    })
    expect(sharingOf({ shared: true, groups: [] })).toEqual({ visibility: 'club', groupIds: [] })
    expect(sharingOf({ shared: true, groups: [{ id: 3, name: 'Trainer' }] })).toEqual({
      visibility: 'groups',
      groupIds: [3],
    })
  })

  it('sends groups only for "Gruppen" and needs one', () => {
    expect(sharingBody({ visibility: 'club', groupIds: [3] })).toEqual({
      shared: true,
      groupIds: [],
    })
    expect(sharingBody({ visibility: 'private', groupIds: [3] })).toEqual({
      shared: false,
      groupIds: [],
    })
    expect(sharingBody({ visibility: 'groups', groupIds: [3] })).toEqual({
      shared: true,
      groupIds: [3],
    })
    expect(sharingValid({ visibility: 'groups', groupIds: [] })).toBe(false)
    expect(sharingValid({ visibility: 'club', groupIds: [] })).toBe(true)
  })
})
