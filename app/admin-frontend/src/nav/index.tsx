import { SECTIONS, type NavPage, type NavSection, type PageEntry, type PageTab, type SectionId } from './registry'

export type { NavPage, NavSection, PageTab } from './registry'

const entries: PageEntry[] = Object.values(
  import.meta.glob<PageEntry>('./pages/*.tsx', { eager: true, import: 'default' }),
)

/** Every section with its pages, in sidebar order; empty sections are left out. */
export function navSections(): NavSection[] {
  return (Object.keys(SECTIONS) as SectionId[])
    .map((id) => ({
      id,
      label: SECTIONS[id](),
      pages: entries
        .filter((e) => e.section === id)
        .map((e) => ({ order: e.order, page: e.page() }))
        .sort((a, b) => a.order - b.order || a.page.id.localeCompare(b.page.id))
        .map((e) => e.page),
    }))
    .filter((s) => s.pages.length > 0)
}

/**
 * Old URLs and where they live now. The query string is kept, so links like
 * …/diagnostics/outbound-mail?level=error still filter.
 */
export const LEGACY_REDIRECTS: Record<string, string> = {
  // Settings moved to the page each one configures.
  '/app/platform/settings': '/app/platform/mail/settings',
  '/app/platform/settings/mail': '/app/platform/mail/settings',
  '/app/platform/settings/sender': '/app/platform/mail/settings',
  '/app/platform/settings/backups': '/app/platform/backups/settings',
  '/app/platform/backups/storage': '/app/platform/backups/settings',
  '/app/platform/settings/discord': '/app/platform/discord/settings',
  '/app/platform/settings/alerts': '/app/platform/alerts/settings',
  '/app/platform/settings/limits': '/app/tenants/settings',
  // Each page's settings became its last tab, "Einstellungen" (2026-11).
  '/app/platform/mail/relay': '/app/platform/mail/settings',
  '/app/platform/mail/sender': '/app/platform/mail/settings',
  '/app/platform/discord/setup': '/app/platform/discord/settings',
  '/app/platform/discord/channels': '/app/platform/discord/settings',
  '/app/tenants/limits': '/app/tenants/plans',
  '/app/tenants/prices': '/app/tenants/plans',
  '/app/platform/settings/encryption': '/app/platform/encryption',
  '/app/platform/settings/translations': '/app/platform/translations',
  // Diagnostics kept health, performance and jobs.
  '/app/platform/diagnostics/health': '/app/platform/diagnostics',
  '/app/platform/diagnostics/outbound-mail': '/app/platform/mail',
  '/app/platform/diagnostics/mail-server': '/app/platform/mail/server',
  '/app/platform/diagnostics/discord': '/app/platform/discord',
  '/app/platform/diagnostics/permissions': '/app/roles/api',
  '/app/platform/diagnostics/events': '/app/platform/alerts/events',
  // Alerts: performance went to Diagnostics, maintenance got its own page.
  '/app/platform/alerts/overview': '/app/platform/alerts',
  '/app/platform/alerts/performance': '/app/platform/diagnostics/performance',
  '/app/whats-new/changelog': '/app/whats-new',
}

/** Every tab a person may open, in sidebar order. */
export function visibleTabs(page: NavPage, can: (perm: string) => boolean): PageTab[] {
  return page.tabs.filter((t) => {
    if (!t.perm) return true
    return (Array.isArray(t.perm) ? t.perm : [t.perm]).some(can)
  })
}
