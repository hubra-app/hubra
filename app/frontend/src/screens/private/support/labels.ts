import type { TFunction } from 'i18next'
import type { CaseStatus } from '@/api/support'
import type { DeviceInfo } from './deviceInfo'

type T = TFunction | ((key: string, fallback?: string, opts?: Record<string, unknown>) => string)

export const STATUS_COLOR: Record<CaseStatus, string> = {
  open: 'blue',
  planned: 'violet',
  in_progress: 'orange',
  done: 'green',
  closed: 'gray',
}

export function statusLabel(t: T, status: CaseStatus): string {
  const fallback: Record<CaseStatus, string> = {
    open: 'Offen',
    planned: 'Geplant',
    in_progress: 'In Arbeit',
    done: 'Erledigt',
    closed: 'Geschlossen',
  }
  return (t as (k: string, d: string) => string)(`support.status.${status}`, fallback[status])
}

/** The device info as label / value rows, as the form shows them. */
export function deviceLines(info: DeviceInfo, t: T, page?: string | null): [string, string][] {
  const tt = t as (k: string, d: string) => string
  const rows: [string, string][] = []
  const join = (...parts: (string | number | undefined)[]) => parts.filter(Boolean).join(' ')
  if (info.browser) rows.push([tt('support.device.browser', 'Browser'), join(info.browser, info.browserVersion)])
  if (info.os) rows.push([tt('support.device.os', 'Betriebssystem'), join(info.os, info.osVersion)])
  if (info.deviceType)
    rows.push([
      tt('support.device.type', 'Gerät'),
      tt(`support.device.${info.deviceType}`, info.deviceType),
    ])
  if (info.screenWidth && info.screenHeight)
    rows.push([tt('support.device.screen', 'Bildschirm'), `${info.screenWidth} × ${info.screenHeight}`])
  if (info.viewportWidth && info.viewportHeight)
    rows.push([tt('support.device.window', 'Fenster'), `${info.viewportWidth} × ${info.viewportHeight}`])
  if (info.language) rows.push([tt('support.device.language', 'Sprache'), info.language])
  if (info.theme)
    rows.push([tt('support.device.theme', 'Darstellung'), tt(`support.device.theme_${info.theme}`, info.theme)])
  if (page) rows.push([tt('support.device.page', 'Seite'), page])
  return rows
}
