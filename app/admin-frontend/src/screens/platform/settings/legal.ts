import { tr } from '@/lang'
import { defineSettings } from './registry'

export default defineSettings({
  id: 'legal',
  keys: [
    'legal.privacy_url',
    'legal.terms_url',
    'legal.imprint_url',
  ],
  builtIn: [
    'legal.privacy_url',
    'legal.terms_url',
    'legal.imprint_url',
  ],
  title: () => tr('Rechtliches', 'Legal pages'),
  desc: () =>
    tr(
      'Wo Hubras Datenschutzerklärung, Nutzungsbedingungen und Impressum stehen. Stripe fragt nach denselben Adressen: im Dashboard unter Einstellungen › Öffentliche Angaben und bei Connect › Plattformprofil.',
      "Where Hubra's privacy policy, terms of service and imprint are. Stripe asks for the same addresses: in the dashboard under Settings › Public details and in Connect › Platform profile.",
    ),
  de: {
    'legal.privacy_url': [
      'Datenschutzerklärung',
      'Hubras Datenschutzerklärung. Verlinkt bei der Registrierung, in den Fussleisten und im Stripe Checkout. Leer: kein Link',
    ],
    'legal.terms_url': [
      'Nutzungsbedingungen',
      'Hubras Nutzungsbedingungen. Verlinkt bei der Registrierung, in den Fussleisten und im Stripe Checkout. Leer: kein Link',
    ],
    'legal.imprint_url': ['Impressum', 'Hubras Impressum, verlinkt in den Fussleisten. Leer: kein Link'],
  },
})
