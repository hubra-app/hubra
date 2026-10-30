import { describe, expect, it } from 'vitest'
import type { PermissionEntry } from '@/api/system'
import { currentLevel, levelKeys, offeredLevels, toAreas } from './levels'

const perm = (resource: string, action: string): PermissionEntry => ({
  method: 'GET',
  path: '/',
  key: `events.${resource}.${action}`,
  display_name: action,
  resource,
  action,
  blueprint: 'events',
})

const events = ['read', 'register', 'create', 'update', 'update.title', 'delete'].map((a) =>
  perm('events', a),
)

describe('role levels', () => {
  it('stacks each level on the one before', () => {
    expect(levelKeys(events, 'none')).toEqual([])
    expect(levelKeys(events, 'view')).toEqual(['events.events.read', 'events.events.register'])
    expect(levelKeys(events, 'edit')).toHaveLength(5)
    expect(levelKeys(events, 'all')).toHaveLength(6)
  })

  it('reads back the level a role matches, null for a mix', () => {
    expect(currentLevel(events, new Set())).toBe('none')
    expect(currentLevel(events, new Set(levelKeys(events, 'edit')))).toBe('edit')
    expect(currentLevel(events, new Set(['events.events.delete']))).toBeNull()
  })

  it('leaves out levels that give nothing more', () => {
    expect(offeredLevels([perm('audit', 'read')])).toEqual(['none', 'view'])
    expect(offeredLevels([perm('i18n', 'write')])).toEqual(['none', 'edit'])
    expect(offeredLevels(events)).toEqual(['none', 'view', 'edit', 'all'])
  })

  it('groups the catalog by resource without duplicates', () => {
    const areas = toAreas([...events, events[0], perm('polls', 'read')])
    expect(areas.map((a) => a.key)).toEqual(['events:events', 'events:polls'])
    expect(areas[0].perms).toHaveLength(6)
  })
})
