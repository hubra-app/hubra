import { tr } from '@/lang'
import { defineSettings } from './registry'

export default defineSettings({
  id: 'payments',
  keys: [
    'stripe.mode',
    'payments.stripe.secret_key',
    'payments.stripe.sandbox_secret_key',
    'payments.fee_percent',
  ],
  title: () => tr('Online-Zahlungen (Stripe)', 'Online payments (Stripe)'),
  desc: () =>
    tr(
      'Mit dem Plugin «Online-Zahlungen» verbindet jeder Verein sein eigenes Stripe-Konto mit diesem Plattform-Konto (Stripe Connect). Mitglieder zahlen ihre Rechnungen dann mit Karte oder TWINT, das Geld geht direkt an den Verein. Im Stripe-Dashboard muss Connect eingeschaltet sein.',
      "With the «Online payments» plugin each club connects its own Stripe account to this platform account (Stripe Connect). Members then pay their invoices by card or TWINT and the money goes straight to the club. Connect must be turned on in the Stripe dashboard.",
    ),
  de: {
    'stripe.mode': [
      'Stripe-Modus',
      'Sandbox: alle Vereine nutzen die Sandbox-Schlüssel (sk_test_), es fliesst kein echtes Geld. Live: die Vereine nutzen die Live-Schlüssel; Sandbox-Vereine (Verein › Sandbox-Verein) bleiben immer auf den Sandbox-Schlüsseln. Gilt für Online-Zahlungen und die Abrechnung',
    ],
    'payments.stripe.secret_key': [
      'Stripe-Live-Key',
      'Der Live-Schlüssel des Plattform-Kontos (Connect, sk_live_). Wird verschlüsselt gespeichert',
    ],
    'payments.stripe.sandbox_secret_key': [
      'Stripe-Sandbox-Key',
      'Der Sandbox-Schlüssel des Plattform-Kontos (Connect, sk_test_), im Sandbox-Modus und immer für Sandbox-Vereine. Wird verschlüsselt gespeichert',
    ],
    'payments.fee_percent': [
      'Hubra-Gebühr',
      'Anteil jeder Online-Zahlung für Hubra (%), zusätzlich zu den Stripe-Gebühren. Der Verein trägt beide oder gibt sie als Zuschlag an die Mitglieder weiter. 0: keine',
    ],
  },
})
