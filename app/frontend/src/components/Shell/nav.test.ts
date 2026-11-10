import { describe, expect, it } from 'vitest'
import type { ModuleInfo, ModuleNavItem } from '@/api/modules'
import {
  addNavCategory,
  buildNav,
  getParentPath,
  moveNavEntry,
  MORE_PATH,
  removeNavCategory,
  renameNavSection,
  toggleNavMore,
  type NavSection,
} from './nav'

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
    expect(paths(buildNav(counts, t, [members]).nav)).toEqual(['/app/members', MORE_PATH])
  })

  it('shows the parent to someone who may open only one of its tabs', () => {
    const only = (k: string) => k === 'tiers.tiers.read'
    expect(paths(buildNav(counts, t, [members], only).nav)).toEqual(['/app/members', MORE_PATH])
    expect(buildNav(counts, t, [members], () => false).nav).toEqual([])
  })

  it('lists every page in the sidebar by area, plugins in their own', () => {
    const { nav, more } = buildNav(counts, t, [members, codes, inbox])
    expect(nav.map((s) => s.section)).toEqual(['workspace', 'operations', 'plugins', 'all'])
    expect(paths(nav)).toEqual(['/app/members', '/app/operations/codes', '/app/inbox', MORE_PATH])
    // Nothing is out of the sidebar, and the Weitere row has no heading.
    expect(more).toEqual([])
    expect(nav[nav.length - 1].label).toBe('')
  })

  it('has a card only for the pages out of the sidebar', () => {
    const prefs = { pinned: ['/app/groups'], hidden: ['/app/inbox', '/app/members'] }
    const { nav, cards } = buildNav(counts, t, [members, groups, inbox, account], () => true, prefs)
    expect(paths(nav)).not.toContain('/app/inbox')
    // In the areas the pages came with; pages in the sidebar (pinned ones
    // too) and the personal pages have none.
    expect(cards.map((s) => s.section)).toEqual(['workspace', 'plugins'])
    expect(paths(cards)).toEqual(['/app/members', '/app/inbox'])
    expect(cards[0].items[0].module).toBe('members')
    // A card names the pages that sit on it as tabs.
    expect(cards[0].items[0].tabs).toEqual([{ label: '/app/members/tiers', perms: ['tiers.tiers.read'] }])
    // With everything in the sidebar, there are no cards.
    expect(buildNav(counts, t, [members, groups, inbox, account]).cards).toEqual([])
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
    expect(paths(nav)).toEqual(['/app/groups', MORE_PATH])
    expect(more).toEqual([])
  })

  it("follows the person's order within a section, new entries last", () => {
    const events = mod('events', [navItem('/app/events', [], { order: 30 })])
    const prefs = { pinned: [], hidden: [], order: ['/app/groups', '/app/members'] }
    const { nav } = buildNav(counts, t, [members, groups, events], () => true, prefs)
    expect(paths(nav)).toEqual(['/app/groups', '/app/members', '/app/events', MORE_PATH])
  })

  it('moves entries within their group of the customise dialog', () => {
    const prefs = { pinned: ['/app/operations/codes', '/app/groups'], hidden: [], order: [] }
    const { groups: dialog, homes } = buildNav(
      counts,
      t,
      [members, groups, codes],
      () => true,
      prefs,
    )
    expect(dialog.map((g) => g.section)).toEqual(['favourites', 'workspace'])
    const fav = moveNavEntry(prefs, dialog, homes, '/app/groups', -1)
    expect(fav.pinned).toEqual(['/app/groups', '/app/operations/codes'])
    // The first entry can't move further up, and favourites stay together.
    expect(moveNavEntry(prefs, dialog, homes, '/app/operations/codes', -1)).toBe(prefs)
    expect(moveNavEntry(prefs, dialog, homes, '/app/groups', 1)).toBe(prefs)

    const plain = { pinned: [], hidden: [], order: [] }
    const built = buildNav(counts, t, [members, groups], () => true, plain)
    const moved = moveNavEntry(plain, built.groups, built.homes, '/app/groups', -1)
    expect(moved.order).toEqual(['/app/groups', '/app/members'])
    expect(paths(buildNav(counts, t, [members, groups], () => true, moved).nav)).toEqual([
      '/app/groups',
      '/app/members',
      MORE_PATH,
    ])
  })

  it('keeps plugin pages in Kommunikation next to Mail, after Betrieb', () => {
    const mail = mod('mail', [navItem('/app/mail', [], { section: 'communication' })])
    const letters = mod('letters', [navItem('/app/letters', [], { section: 'communication' })], {
      plugin: { id: 'letters' } as ModuleInfo['plugin'],
    })
    const { nav } = buildNav(counts, t, [members, codes, letters, mail, inbox])
    expect(nav.map((s) => s.section)).toEqual([
      'workspace',
      'operations',
      'communication',
      'plugins',
      'all',
    ])
    expect(nav[2].items.map((i) => i.path).sort()).toEqual(['/app/letters', '/app/mail'])
  })

  it('moves entries across sections and in and out of Weitere', () => {
    const events = mod('events', [navItem('/app/events', [], { section: 'activities' })])
    const all = [members, groups, events, codes]
    const plain = { pinned: [], hidden: [], order: [], sections: {} }
    let built = buildNav(counts, t, all, () => true, plain)
    expect(built.groups.map((g) => g.section)).toEqual(['workspace', 'activities', 'operations'])

    // Down past the end of Verein: to the top of Vereinsleben.
    let prefs = moveNavEntry(plain, built.groups, built.homes, '/app/groups', 1)
    expect(prefs.sections).toEqual({ '/app/groups': 'activities' })
    built = buildNav(counts, t, all, () => true, prefs)
    expect(built.nav[1].items.map((i) => i.path)).toEqual(['/app/groups', '/app/events'])

    // Out of the sidebar: only Weitere shows it, and the Weitere row lights up.
    prefs = toggleNavMore(prefs, built.homes, '/app/operations/codes', false)
    built = buildNav(counts, t, all, () => true, prefs)
    expect(built.more.map((i) => i.path)).toEqual(['/app/operations/codes'])
    expect(paths(built.nav)).not.toContain('/app/operations/codes')
    expect(built.groups.map((g) => g.section)).toEqual(['workspace', 'activities', 'more'])

    // Down past the end of Vereinsleben: out of the sidebar too.
    prefs = moveNavEntry(prefs, built.groups, built.homes, '/app/events', 1)
    built = buildNav(counts, t, all, () => true, prefs)
    expect(built.more.map((i) => i.path)).toEqual(['/app/events', '/app/operations/codes'])

    // Back into the sidebar, to the area it came from.
    prefs = toggleNavMore(prefs, built.homes, '/app/operations/codes', true)
    expect(prefs.hidden).not.toContain('/app/operations/codes')
    built = buildNav(counts, t, all, () => true, prefs)
    expect(built.groups.find((g) => g.section === 'operations')?.items[0].path).toBe(
      '/app/operations/codes',
    )

    // Moving back into its own section drops the override.
    prefs = moveNavEntry(prefs, built.groups, built.homes, '/app/groups', -1)
    expect(prefs.sections?.['/app/groups']).toBeUndefined()
  })

  it('has categories of the person\'s own and renamed headings', () => {
    const all = [members, groups, codes]
    let prefs = addNavCategory({ pinned: [], hidden: [] }, ' Kasse ')
    const id = prefs.categories![0].id
    expect(prefs.categories).toEqual([{ id, label: 'Kasse' }])
    let built = buildNav(counts, t, all, () => true, prefs)
    // Empty: only in the customise dialog, after the built-in areas.
    expect(built.nav.map((s) => s.section)).toEqual(['workspace', 'operations', 'all'])
    expect(built.groups.map((g) => [g.section, g.custom ?? false])).toEqual([
      ['workspace', false],
      ['operations', false],
      [id, true],
    ])

    // Down past the end of Betrieb: into the new category.
    prefs = moveNavEntry(prefs, built.groups, built.homes, '/app/operations/codes', 1)
    expect(prefs.sections).toEqual({ '/app/operations/codes': id })
    built = buildNav(counts, t, all, () => true, prefs)
    expect(built.nav.map((s) => [s.section, s.label])).toEqual([
      ['workspace', 'shell.sections.workspace'],
      [id, 'Kasse'],
      ['all', ''],
    ])

    // Renamed: a built-in heading and the category.
    prefs = renameNavSection(prefs, 'workspace', 'Vorstand')
    prefs = renameNavSection(prefs, id, 'Codes & Co')
    built = buildNav(counts, t, all, () => true, prefs)
    expect(built.nav.map((s) => s.label)).toEqual(['Vorstand', 'Codes & Co', ''])
    // An empty name gives a built-in heading its own back.
    expect(renameNavSection(prefs, 'workspace', ' ').labels).toEqual({})

    // Removed: its pages go back to their own areas.
    prefs = removeNavCategory(prefs, id)
    expect(prefs.categories).toEqual([])
    expect(prefs.sections).toEqual({})
    built = buildNav(counts, t, all, () => true, prefs)
    expect(paths(built.nav)).toContain('/app/operations/codes')
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
    expect(getParentPath('/app/members/tiers', [...nav, '/app/members/tiers'])).toBe(
      '/app/members/tiers',
    )
    // Roles and the log are tabs of Einstellungen, groups of Mitglieder.
    expect(getParentPath('/app/audit-log/5', nav)).toBe('/app/settings')
    expect(getParentPath('/app/system/roles', nav)).toBe('/app/settings')
    expect(getParentPath('/app/groups/4', nav)).toBe('/app/members')
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
