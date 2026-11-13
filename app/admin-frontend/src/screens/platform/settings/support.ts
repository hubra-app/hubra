import { tr } from '@/lang'
import { defineSettings } from './registry'

export default defineSettings({
  id: 'support',
  keys: [
    'support.url',
  ],
  title: () => tr('Support-Seite', 'Support site'),
  desc: () =>
    tr(
      'Wo die Support-Seite läuft. Antworten auf Meldungen und die Mail nach einer Passwortänderung verlinken dorthin.',
      'Where the support site runs. Answers to reports and the password-changed mail link there.',
    ),
  de: {
    'support.url': [
      'Adresse der Support-Seite',
      'Hilfe, Roadmap, Status und Meldungen (Image support-frontend), z. B. https://support.hubra.club. Mails an Meldende verlinken dorthin. Leer: auf die Meldungen in der Vereins-App',
    ],
  },
})
