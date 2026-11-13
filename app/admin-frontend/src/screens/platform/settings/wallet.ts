import { tr } from '@/lang'
import { defineSettings } from './registry'

export default defineSettings({
  id: 'wallet',
  keys: [
    'wallet.google.issuer_id',
    'wallet.google.class_id',
    'wallet.google.service_account',
    'wallet.google.logo_url',
  ],
  title: () => tr('Google Wallet', 'Google Wallet'),
  desc: () =>
    tr(
      'Mit allen drei Angaben zeigt «Mein Konto» unter dem Mitgliederausweis den Knopf «Zu Google Wallet hinzufügen». Der Pass zeigt Name, Ausweisnummer mit QR-Code und die Vereine und wird bei Änderungen nachgeführt. Solange das Aussteller-Konto im Demo-Modus ist, können nur Testkonten aus der Console den Pass speichern.',
      'With all three set, My Account shows "Add to Google Wallet" under the member badge. The pass shows the name, badge number with QR code and the clubs, and follows changes. While the issuer account is in demo mode, only test accounts from the console can save it.',
    ),
  de: {
    'wallet.google.issuer_id': [
      'Aussteller-ID',
      'Die lange Nummer in der Google Pay & Wallet Console. Leer: kein Knopf «Zu Google Wallet hinzufügen»',
    ],
    'wallet.google.class_id': [
      'Klassen-ID',
      'Die ID der generischen Klasse aus der Console, mit oder ohne Aussteller-ID davor',
    ],
    'wallet.google.service_account': [
      'Schlüssel des Dienstkontos',
      'Der ganze JSON-Schlüssel eines Google-Cloud-Dienstkontos mit der Rolle Developer im Aussteller-Konto. Wird verschlüsselt gespeichert',
    ],
    'wallet.google.logo_url': [
      'Logo auf dem Pass',
      'Öffentliche https-Adresse eines quadratischen PNG (660 px empfohlen). Standard: das App-Symbol der Anmeldeseite',
    ],
  },
})
