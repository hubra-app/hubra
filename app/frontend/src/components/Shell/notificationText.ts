import {
  notificationMessageText,
  notificationTitleText,
  safeNotificationLink,
  type NotificationText,
} from '@hubra/ui'
import type { Notification } from '@/types'

type T = (key: string, fallback: string, options?: Record<string, unknown>) => string

const show = (text: NotificationText | null, raw: string, t: T) =>
  text ? t(text.key, text.de, text.vars) : raw

/** The notification's title in the member's language. */
export function notificationTitle(n: Notification, t: T): string {
  return show(notificationTitleText(n.title), n.title, t)
}

/** The notification's message in the member's language. */
export function notificationMessage(n: Notification, t: T): string {
  const text = notificationMessageText(n.msg)
  if (text?.vars?.name === 'A member') {
    text.vars.name = t('shell.notif.text.aMember', 'Ein Mitglied')
  }
  return show(text, n.msg, t)
}

export const safeLink = safeNotificationLink
