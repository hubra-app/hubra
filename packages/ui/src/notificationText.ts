// The server stores notification texts in English. These find the known
// ones so each app can show them in the member's language: the club app
// through its translation keys (German default), sign-in through tr(de, en).
// Unknown texts (plugins, older ones) give null and are shown as they are.

export interface NotificationText {
  key: string
  de: string
  en: string
  vars?: Record<string, string>
}

const TITLES: Record<string, [string, string, string]> = {
  'New post': ['shell.notif.text.newPost', 'Neuer Beitrag', 'New post'],
  'New event': ['shell.notif.text.newEvent', 'Neuer Anlass', 'New event'],
  'New poll': ['shell.notif.text.newPoll', 'Neue Umfrage', 'New poll'],
  'Event changed': ['shell.notif.text.eventChanged', 'Anlass geändert', 'Event changed'],
  'Event reminder': ['shell.notif.text.eventReminder', 'Erinnerung an einen Anlass', 'Event reminder'],
  'Event cancelled': ['shell.notif.text.eventCancelled', 'Anlass abgesagt', 'Event cancelled'],
  'Sign-up to approve': [
    'shell.notif.text.signUpToApprove',
    'Anmeldung bestätigen',
    'Sign-up to approve',
  ],
  'Sign-up confirmed': ['shell.notif.text.signUpConfirmed', 'Anmeldung bestätigt', 'Sign-up confirmed'],
  'Sign-up confirmed, on the waitlist': [
    'shell.notif.text.signUpWaitlist',
    'Anmeldung bestätigt, auf der Warteliste',
    'Sign-up confirmed, on the waitlist',
  ],
  'Sign-up declined': ['shell.notif.text.signUpDeclined', 'Anmeldung abgelehnt', 'Sign-up declined'],
  'You got a place': ['shell.notif.text.gotAPlace', 'Du hast einen Platz bekommen', 'You got a place'],
  'Request to leave': ['shell.notif.text.requestToLeave', 'Austrittsgesuch', 'Request to leave'],
  'New application': [
    'shell.notif.text.newApplication',
    'Neuer Mitgliedschaftsantrag',
    'New application',
  ],
  'New device login': [
    'shell.notif.text.newDevice',
    'Anmeldung von einem neuen Gerät',
    'New device login',
  ],
}

const PREFIXES: [string, string, string, string][] = [
  ['New vote: ', 'shell.notif.text.newVote', 'Neue Stimme: {{subject}}', 'New vote: {{subject}}'],
  ['Reminder: ', 'shell.notif.text.reminder', 'Erinnerung: {{subject}}', 'Reminder: {{subject}}'],
  ['Proxy vote: ', 'shell.notif.text.proxyVote', 'Vertretung: {{subject}}', 'Proxy vote: {{subject}}'],
]

export function notificationTitleText(title: string): NotificationText | null {
  const fixed = TITLES[title]
  if (fixed) return { key: fixed[0], de: fixed[1], en: fixed[2] }
  for (const [prefix, key, de, en] of PREFIXES) {
    if (title.startsWith(prefix)) return { key, de, en, vars: { subject: title.slice(prefix.length) } }
  }
  return null
}

export function notificationMessageText(msg: string): NotificationText | null {
  let m = msg.match(/^Your account was accessed from a new device or location at (.+?)\. /)
  if (m) {
    return {
      key: 'shell.notif.text.newDeviceMsg',
      de: 'Dein Konto wurde am {{time}} von einem neuen Gerät oder Ort aus benutzt. Warst du das nicht, beende die Sitzung im Konto unter Sitzungen.',
      en: "Your account was used from a new device or location at {{time}}. If this wasn't you, end the session under Account › Sessions.",
      vars: { time: m[1] },
    }
  }
  if (msg === 'Please cast your vote before the poll closes.') {
    return {
      key: 'shell.notif.text.castVote',
      de: 'Bitte stimme ab, bevor die Umfrage schliesst.',
      en: 'Please cast your vote before the poll closes.',
    }
  }
  m = msg.match(/^(.+) voted for (.+)$/)
  if (m) {
    return {
      key: 'shell.notif.text.votedFor',
      de: '{{name}} hat für «{{option}}» gestimmt',
      en: '{{name}} voted for "{{option}}"',
      vars: { name: m[1], option: m[2] },
    }
  }
  m = msg.match(/^(.+) asked you to vote for them\.$/)
  if (m) {
    return {
      key: 'shell.notif.text.askedProxy',
      de: '{{name}} hat dir die Stimme übertragen.',
      en: '{{name}} asked you to vote for them.',
      vars: { name: m[1] },
    }
  }
  return null
}

/** Puts ``vars`` into a text's {{placeholders}}. */
export function fillNotificationText(text: string, vars: Record<string, string> = {}): string {
  return text.replace(/\{\{(\w+)\}\}/g, (all, name: string) => vars[name] ?? all)
}

/** Only paths inside the club app are followed. */
export function safeNotificationLink(link: string | null | undefined): string | null {
  return link && /^\/app\/[^/]/.test(link) ? link : null
}
