import type { DeviceInfo } from '@hubra/ui'
import type { Area, CaseKind, CaseStatus, Severity } from '@/api/support'

type Tr = (de: string, en: string) => string

export const STATUS_COLOR: Record<CaseStatus, string> = {
  open: 'blue',
  planned: 'violet',
  in_progress: 'orange',
  done: 'green',
  closed: 'gray',
}

export function statusLabel(tr: Tr, s: CaseStatus): string {
  return {
    open: tr('Offen', 'Open'),
    planned: tr('Geplant', 'Planned'),
    in_progress: tr('In Arbeit', 'In progress'),
    done: tr('Erledigt', 'Done'),
    closed: tr('Geschlossen', 'Closed'),
  }[s]
}

export function kindLabel(tr: Tr, k: CaseKind): string {
  return { bug: tr('Problem', 'Problem'), feature: tr('Idee', 'Idea'), question: tr('Frage', 'Question') }[k]
}

export const KIND_COLOR: Record<CaseKind, string> = { bug: 'red', feature: 'orange', question: 'blue' }

export function areaLabel(tr: Tr, a: Area): string {
  return {
    members: tr('Mitglieder', 'Members'),
    finance: tr('Finanzen', 'Finance'),
    events: tr('Anlässe', 'Events'),
    posts: tr('Beiträge', 'Posts'),
    polls: tr('Umfragen', 'Polls'),
    groups: tr('Gruppen', 'Groups'),
    inventory: tr('Inventar', 'Inventory'),
    mail: tr('Mail', 'Mail'),
    settings: tr('Einstellungen', 'Settings'),
    account: tr('Konto und Anmeldung', 'Account and sign-in'),
    modules: tr('Modul', 'Module'),
    other: tr('Anderes', 'Other'),
  }[a]
}

export function severityLabel(tr: Tr, s: Severity): string {
  return {
    minor: tr('Kleinigkeit', 'Minor'),
    annoying: tr('Stört bei der Arbeit', 'Gets in the way'),
    blocking: tr('Ich komme nicht weiter', 'I am stuck'),
  }[s]
}

/** The device info as label / value rows, as the form shows them. */
export function deviceLines(info: DeviceInfo, tr: Tr): [string, string][] {
  const rows: [string, string][] = []
  const join = (...parts: (string | number | undefined)[]) => parts.filter(Boolean).join(' ')
  if (info.browser) rows.push(['Browser', join(info.browser, info.browserVersion)])
  if (info.os) rows.push([tr('Betriebssystem', 'Operating system'), join(info.os, info.osVersion)])
  if (info.deviceType)
    rows.push([
      tr('Gerät', 'Device'),
      { phone: tr('Handy', 'Phone'), tablet: 'Tablet', desktop: tr('Computer', 'Computer') }[info.deviceType],
    ])
  if (info.screenWidth && info.screenHeight)
    rows.push([tr('Bildschirm', 'Screen'), `${info.screenWidth} × ${info.screenHeight}`])
  if (info.viewportWidth && info.viewportHeight)
    rows.push([tr('Fenster', 'Window'), `${info.viewportWidth} × ${info.viewportHeight}`])
  if (info.language) rows.push([tr('Sprache', 'Language'), info.language])
  if (info.theme) rows.push([tr('Darstellung', 'Appearance'), info.theme === 'dark' ? tr('Dunkel', 'Dark') : tr('Hell', 'Light')])
  return rows
}

/** "/club/app/finance" from a pasted club app address, or null. */
export function pathOf(value: string): string | undefined {
  const v = value.trim()
  if (!v) return undefined
  if (v.startsWith('/')) return v
  try {
    return new URL(v).pathname
  } catch {
    return undefined
  }
}
