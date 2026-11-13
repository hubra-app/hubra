import type { ReactNode } from 'react'
import type { IconHome } from '@tabler/icons-react'
import { tr } from '@/lang'

// The manage navigation: sidebar sections, the pages in them and each page's
// tabs. A tab is its own URL; App.tsx makes a route for every tab and
// redirects the old URLs (see LEGACY_REDIRECTS) so bookmarks and links in
// alert mails, Discord posts and the event log still work.
//
// Each page is its own file in nav/pages/ (`export default definePage(...)`),
// so pull requests that add or change different pages don't edit the same
// file. The sidebar sorts a section's pages by their position number; leave
// gaps (10, 20, ...) so a new page fits in between.
//
// Rule of thumb: a page is one job an operator does, and its tabs are parts
// of that job. Settings live on the page they configure (the mail relay
// under Mail, the backup storage under Backups), not on a settings page,
// and always in that page's last tab, "Einstellungen" (path …/settings).
// A settings tab needs platform.settings.

export interface PageTab {
  id: string
  path: string
  label: string
  /** Any one of these global permissions shows the tab; none: everyone. */
  perm?: string | string[]
  /** Replaces the page description while this tab is open. */
  desc?: ReactNode
  render: () => ReactNode
}

export interface NavPage {
  id: string
  /** Sidebar label (short). */
  label: string
  /** Page title; the label when left out. */
  title?: string
  icon: ReactNode
  desc?: ReactNode
  /** The screen draws its own heading (it has buttons in it). */
  ownHead?: boolean
  tabs: PageTab[]
}

export interface NavSection {
  id: string
  label: string
  pages: NavPage[]
}

/** The sidebar's sections, in order. */
export const SECTIONS = {
  clubs: () => tr('Vereine', 'Clubs'),
  operations: () => tr('Betrieb', 'Operations'),
  services: () => tr('Dienste', 'Services'),
  access: () => tr('Zugriff & Sicherheit', 'Access & security'),
  hubra: () => 'Hubra',
} as const

export type SectionId = keyof typeof SECTIONS

export interface PageEntry {
  section: SectionId
  /** Position in the section, smallest first. */
  order: number
  /** Built on each call, so the labels follow the language. */
  page: () => NavPage
}

export function definePage(section: SectionId, order: number, page: () => NavPage): PageEntry {
  return { section, order, page }
}

export const icon = (I: typeof IconHome) => <I size={24} />
