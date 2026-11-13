import { tr } from '@/lang'
import { defineSettings } from './registry'

export default defineSettings({
  id: 'billing',
  keys: [
    'billing.enabled',
    'billing.yearly',
    'billing.stripe.secret_key',
    'billing.stripe.webhook_secret',
    'billing.stripe.sandbox_secret_key',
    'billing.stripe.sandbox_webhook_secret',
  ],
  title: () => tr('Abrechnung der Vereine (Stripe Billing)', 'Club billing (Stripe Billing)'),
  desc: () =>
    tr(
      'Hubra verrechnet den Vereinen ihren Tarif über ein eigenes Stripe-Konto (oder, ohne eigenen Schlüssel, das der Online-Zahlungen). Im Stripe-Dashboard einen Webhook auf /api/v1/global/billing/stripe/webhook anlegen (checkout.session.completed, customer.subscription.*, invoice.paid, invoice.payment_failed) und das Kundenportal einschalten. Siehe docs/billing.md.',
      "Hubra bills clubs for their plan through its own Stripe account (or, without its own key, the Online payments one). In the Stripe dashboard add a webhook to /api/v1/global/billing/stripe/webhook (checkout.session.completed, customer.subscription.*, invoice.paid, invoice.payment_failed) and turn on the customer portal. See docs/billing.md.",
    ),
  de: {
    'billing.enabled': [
      'Vereine über Stripe abrechnen',
      'on: Admins eines Vereins sehen Einstellungen › Hubra-Abo und bezahlen ihren Tarif über Stripe Checkout, mit dem Stripe-Schlüssel unten; der Stand wird stündlich bei Stripe gelesen. off: Konditionen werden nur festgehalten',
    ],
    'billing.yearly': [
      'Jährlich abrechnen',
      'on: neue Abos werden einmal im Jahr belastet (12 × der Monatspreis). off: monatlich. Laufende Abos wechseln beim nächsten Abgleich',
    ],
    'billing.stripe.secret_key': [
      'Live-Key der Abrechnung',
      'Live-Secret- oder Restricted-Key (sk_live_/rk_live_) des Stripe-Kontos, das den Vereinen Hubra verrechnet. Leer: der Live-Key der Online-Zahlungen. Wird verschlüsselt gespeichert',
    ],
    'billing.stripe.webhook_secret': [
      'Live-Webhook-Secret der Abrechnung',
      'Signing Secret (whsec_…) des Live-Webhooks auf /api/v1/global/billing/stripe/webhook. Ohne es folgt der Status Stripe nur über die stündliche Prüfung. Wird verschlüsselt gespeichert',
    ],
    'billing.stripe.sandbox_secret_key': [
      'Sandbox-Key der Abrechnung',
      'Sandbox-Key (sk_test_/rk_test_) des Abrechnungskontos, im Sandbox-Modus und immer für Sandbox-Vereine. Leer: der Sandbox-Key der Online-Zahlungen. Wird verschlüsselt gespeichert',
    ],
    'billing.stripe.sandbox_webhook_secret': [
      'Sandbox-Webhook-Secret der Abrechnung',
      'Signing Secret (whsec_…) desselben Webhooks in der Stripe-Sandbox. Wird verschlüsselt gespeichert',
    ],
  },
})
