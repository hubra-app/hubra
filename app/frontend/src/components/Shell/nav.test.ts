import { describe, expect, it } from 'vitest'
import type { ModuleInfo, ModuleNavItem } from '@/api/modules'
import { buildNav, filterNav, getParentPath } from './nav'

const navItem = (path: string, perms: string[], parent?: string): ModuleNavItem => ({
  path,
  labelKey: path,
  icon: 'users',
  section: 'workspace',
  order: 10,
  perms,
  group: null,
  parent,
})

describe('buildNav', () => {
  const members = {
    code: 'members',
    enabled: true,
    nav: [
      navItem('/app/members', ['members.members.read']),
      navItem('/app/members/tiers', ['tiers.tiers.read'], '/app/members'),
    ],
  } as ModuleInfo
  const counts = { members: 0, applications: 0, groups: 0, polls: 0, invoices: 0 }
  const t = (key: string) => key

  it('shows sub-pages as tabs, not sidebar rows', () => {
    const paths = buildNav(counts, t, [members]).flatMap((s) => s.items.map((i) => i.path))
    expect(paths).toEqual(['/app/members'])
  })

  it('shows the parent to someone who may open only one of its tabs', () => {
    const nav = filterNav(buildNav(counts, t, [members]), (k) => k === 'tiers.tiers.read')
    expect(nav.flatMap((s) => s.items.map((i) => i.path))).toEqual(['/app/members'])
    expect(filterNav(buildNav(counts, t, [members]), () => false)).toEqual([])
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
