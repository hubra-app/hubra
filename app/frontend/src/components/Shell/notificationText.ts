import type { Notification } from '@/types'

type T = (key: string, fallback: string, options?: Record<string, unknown>) => string

// The server stores notification texts in English; show them in the
// member's language. Unknown texts (plugins, older ones) stay as they are.
const TITLES: Record<string, [string, string]> = {
  'New post': ['shell.notif.text.newPost', 'Neuer Beitrag'],
  'New event': ['shell.notif.text.newEvent', 'Neuer Anlass'],
  'New poll': ['shell.notif.text.newPoll', 'Neue Umfrage'],
  'Event changed': ['shell.notif.text.eventChanged', 'Anlass geändert'],
  'Event cancelled': ['shell.notif.text.eventCancelled', 'Anlass abgesagt'],
  'Sign-up to approve': ['shell.notif.text.signUpToApprove', 'Anmeldung bestätigen'],
  'Sign-up confirmed': ['shell.notif.text.signUpConfirmed', 'Anmeldung bestätigt'],
  'Sign-up confirmed, on the waitlist': [
    'shell.notif.text.signUpWaitlist',
    'Anmeldung bestätigt, auf der Warteliste',
  ],
  'Sign-up declined': ['shell.notif.text.signUpDeclined', 'Anmeldung abgelehnt'],
  'You got a place': ['shell.notif.text.gotAPlace', 'Du hast einen Platz bekommen'],
  'Request to leave': ['shell.notif.text.requestToLeave', 'Austrittsgesuch'],
  'New application': ['shell.notif.text.newApplication', 'Neuer Mitgliedschaftsantrag'],
  'New device login': ['shell.notif.text.newDevice', 'Anmeldung von einem neuen Gerät'],
}

const PREFIXES: [string, string, string][] = [
  ['New vote: ', 'shell.notif.text.newVote', 'Neue Stimme: {{subject}}'],
  ['Reminder: ', 'shell.notif.text.reminder', 'Erinnerung: {{subject}}'],
  ['Proxy vote: ', 'shell.notif.text.proxyVote', 'Vertretung: {{subject}}'],
]

export function notificationTitle(n: Notification, t: T): string {
  const fixed = TITLES[n.title]
  if (fixed) return t(fixed[0], fixed[1])
  for (const [prefix, key, fallback] of PREFIXES) {
    if (n.title.startsWith(prefix)) {
      return t(key, fallback, { subject: n.title.slice(prefix.length) })
    }
  }
  return n.title
}

export function notificationMessage(n: Notification, t: T): string {
  let m = n.msg.match(/^Your account was accessed from a new device or location at (.+?)\. /)
  if (m) {
    return t(
      'shell.notif.text.newDeviceMsg',
      'Dein Konto wurde am {{time}} von einem neuen Gerät oder Ort aus benutzt. Warst du das nicht, beende die Sitzung im Konto unter Sitzungen.',
      { time: m[1] },
    )
  }
  if (n.msg === 'Please cast your vote before the poll closes.') {
    return t('shell.notif.text.castVote', 'Bitte stimme ab, bevor die Umfrage schliesst.')
  }
  m = n.msg.match(/^(.+) voted for (.+)$/)
  if (m) {
    return t('shell.notif.text.votedFor', '{{name}} hat für «{{option}}» gestimmt', {
      name: m[1],
      option: m[2],
    })
  }
  m = n.msg.match(/^(.+) asked you to vote for them\.$/)
  if (m) {
    return t('shell.notif.text.askedProxy', '{{name}} hat dir die Stimme übertragen.', {
      name: m[1] === 'A member' ? t('shell.notif.text.aMember', 'Ein Mitglied') : m[1],
    })
  }
  return n.msg
}

/** Only paths inside the club app are followed. */
export function safeLink(link: string | null | undefined): string | null {
  return link && /^\/app\/[^/]/.test(link) ? link : null
}
