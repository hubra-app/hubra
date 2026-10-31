import { describe, expect, it } from 'vitest'
import type { ModuleInfo, ModuleNavItem } from '@/api/modules'
import { buildNav, getParentPath, MORE_PATH, type NavSection } from './nav'

const navItem = (
  path: string,
  perms: string[],
  extra: Partial<ModuleNavItem> = {},
): ModuleNavItem => ({
  path,
  labelKey: path,
  icon: 'users',
  section: 'workspace',
  order: 10,
  perms,
  group: null,
  ...extra,
})

const mod = (code: string, nav: ModuleNavItem[], extra: Partial<ModuleInfo> = {}) =>
  ({ code, enabled: true, nav, ...extra }) as ModuleInfo

describe('buildNav', () => {
  const members = mod('members', [
    navItem('/app/members', ['members.members.read']),
    navItem('/app/members/tiers', ['tiers.tiers.read'], { parent: '/app/members' }),
  ])
  const groups = mod('groups', [navItem('/app/groups', [], { order: 20 })])
  const codes = mod('codes', [navItem('/app/operations/codes', [], { section: 'more' })])
  const inbox = mod('inbox', [navItem('/app/inbox', [])], {
    plugin: { id: 'inbox' } as ModuleInfo['plugin'],
  })
  const account = mod('core', [navItem('/app/account/settings', [], { section: 'me' })])
  const counts = { members: 0, applications: 0, groups: 0, polls: 0, invoices: 0 }
  const t = (key: string) => key
  const paths = (nav: NavSection[]) => nav.flatMap((s) => s.items.map((i) => i.path))

  it('shows sub-pages as tabs, not sidebar rows', () => {
    expect(paths(buildNav(counts, t, [members]).nav)).toEqual(['/app/members'])
  })

  it('shows the parent to someone who may open only one of its tabs', () => {
    const only = (k: string) => k === 'tiers.tiers.read'
    expect(paths(buildNav(counts, t, [members], only).nav)).toEqual(['/app/members'])
    expect(buildNav(counts, t, [members], () => false).nav).toEqual([])
  })

  it('lists secondary and plugin pages under Weitere', () => {
    const { nav, more } = buildNav(counts, t, [members, codes, inbox])
    expect(paths(nav)).toEqual(['/app/members', MORE_PATH])
    expect(more.map((i) => i.path)).toEqual(['/app/operations/codes', '/app/inbox'])
  })

  it('has no Weitere entry when nothing is behind it', () => {
    expect(paths(buildNav(counts, t, [members, groups]).nav)).not.toContain(MORE_PATH)
  })

  it('moves hidden entries to Weitere and pinned ones to the top', () => {
    const prefs = {
      pinned: ['/app/groups', '/app/operations/codes', '/app/account/settings'],
      hidden: ['/app/members', '/app/account/settings'],
    }
    const { nav, more } = buildNav(counts, t, [members, groups, codes, account], () => true, prefs)
    expect(nav[0].label).toBe('shell.sections.favourites')
    expect(nav[0].items.map((i) => i.path)).toEqual(['/app/groups', '/app/operations/codes'])
    expect(more.map((i) => i.path)).toEqual(['/app/members'])
    // The personal section can't be pinned or hidden.
    expect(paths(nav)).toContain('/app/account/settings')
  })

  it('ignores pinned and hidden entries the person may not open', () => {
    const prefs = { pinned: ['/app/members'], hidden: [] }
    const { nav, more } = buildNav(counts, t, [members, groups], () => false, prefs)
    expect(paths(nav)).toEqual(['/app/groups'])
    expect(more).toEqual([])
  })
})

describe('getParentPath', () => {
  it('highlights a plugin entry on its own pages', () => {
    const nav = ['/app/dashboard', '/app/members', '/app/inbox']
    expect(getParentPath('/app/inbox', nav)).toBe('/app/inbox')
    expect(getParentPath('/app/inbox/42', nav)).toBe('/app/inbox')
  })

  it('prefers the longest matching sidebar path', () => {
    const nav = ['/app/inventory', '/app/inventory/keys']
    expect(getParentPath('/app/inventory/keys', nav)).toBe('/app/inventory/keys')
    expect(getParentPath('/app/inventory/7', nav)).toBe('/app/inventory')
  })

  it('keeps built-in sub-pages on their entry', () => {
    const nav = ['/app/operations/events', '/app/finance', '/app/account/settings']
    expect(getParentPath('/app/members/tiers', nav)).toBe('/app/members')
    expect(getParentPath('/app/audit-log', nav)).toBe('/app/settings')
    expect(getParentPath('/app/system/roles', nav)).toBe('/app/settings')
    // Polls have their own sidebar entry now.
    expect(getParentPath('/app/operations/polls', nav)).toBe('/app/operations/polls')
    expect(getParentPath('/app/dashboard/me', nav)).toBe('/app/dashboard')
    expect(getParentPath('/app/finance/invoices/3', nav)).toBe('/app/finance')
    expect(getParentPath('/app/account', nav)).toBe('/app/account/settings')
  })

  it('falls back to the dashboard for unknown pages', () => {
    expect(getParentPath('/app/inbox')).toBe('/app/dashboard')
    expect(getParentPath('/app/inboxes', ['/app/inbox'])).toBe('/app/dashboard')
  })
})
