import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Anchor,
  Badge,
  Button,
  Grid,
  Group,
  Paper,
  SimpleGrid,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { IconCreditCard, IconExternalLink, IconInfoCircle } from '@tabler/icons-react'
import { ConfirmModal } from '@/components/feedback'
import {
  cancelHubraSubscription,
  getHubraBilling,
  getHubraBillingContact,
  saveHubraBillingContact,
  type HubraBillingContact,
  listHubraInvoices,
  openHubraPortal,
  refreshHubraBilling,
  resumeHubraSubscription,
  startHubraCheckout,
  type HubraBillingStatus,
} from '@/api/billing'
import { useToast } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { formatCHF, formatDate } from '@/format'
import { useT } from '@/locales/i18n'
import { AddonsCard, PlanCard } from './SubscriptionChoices'

const STATUS_COLOR: Record<HubraBillingStatus, string> = {
  none: 'gray',
  trialing: 'blue',
  active: 'green',
  past_due: 'orange',
  unpaid: 'red',
  canceled: 'gray',
  incomplete: 'orange',
  paused: 'gray',
}

const STATUS_DE: Record<HubraBillingStatus, string> = {
  none: 'Nicht verrechnet',
  trialing: 'Testphase',
  active: 'Aktiv',
  past_due: 'Zahlung überfällig',
  unpaid: 'Unbezahlt',
  canceled: 'Gekündigt',
  incomplete: 'Unvollständig',
  paused: 'Pausiert',
}

const chf = (amount: string | null | undefined) =>
  amount == null || amount === '' ? '–' : formatCHF(Number(amount))

function Row({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <Group justify="space-between" gap={8} wrap="nowrap">
      <Text size="sm" c={strong ? undefined : 'dimmed'} fw={strong ? 700 : undefined}>
        {label}
      </Text>
      <Text size="sm" fw={strong ? 700 : 600} ta="right">
        {value}
      </Text>
    </Group>
  )
}

type ContactForm = Omit<HubraBillingContact, 'own'>

const EMPTY_CONTACT: ContactForm = {
  email: '',
  street: '',
  houseNo: '',
  postalCode: '',
  city: '',
  country: 'CH',
}

/** Billing email and address: who Hubra's invoices are addressed to. */
function BillingContactCard() {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const { data } = useQuery({
    queryKey: qk.settings.subscriptionContact,
    queryFn: getHubraBillingContact,
  })
  // Only what the admin typed; the rest shows what the server has.
  const [edits, setEdits] = useState<Partial<ContactForm>>({})
  const [saving, setSaving] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})

  const form: ContactForm = Object.fromEntries(
    (Object.keys(EMPTY_CONTACT) as (keyof ContactForm)[]).map((k) => [
      k,
      edits[k] ?? data?.[k] ?? EMPTY_CONTACT[k],
    ]),
  ) as ContactForm

  const field = (name: keyof ContactForm) => ({
    value: form[name],
    error: errors[name],
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => {
      const value = e.currentTarget.value
      setEdits((f) => ({ ...f, [name]: value }))
    },
  })

  const save = async () => {
    setSaving(true)
    setErrors({})
    try {
      const saved = await saveHubraBillingContact(form)
      queryClient.setQueryData(qk.settings.subscriptionContact, saved)
      setEdits({})
      notify('success', t('subscription.contact.saved', 'Rechnungsangaben gespeichert'))
    } catch (err) {
      const fields = (err as { fields?: Record<string, string> } | null)?.fields
      if (fields) setErrors(fields)
      notify(
        'error',
        t('subscription.contact.failed', 'Rechnungsangaben nicht gespeichert'),
        err instanceof Error ? err.message : undefined,
      )
    } finally {
      setSaving(false)
    }
  }

  if (!data) return null

  return (
    <Paper withBorder p="lg">
      <Title order={4} mb={4}>
        {t('subscription.contact.title', 'Rechnungsangaben')}
      </Title>
      <Text size="sm" c="dimmed" mb={14}>
        {data.own
          ? t(
              'subscription.contact.hint',
              'An diese E-Mail und Adresse gehen die Rechnungen von Hubra. Änderungen gelten auch bei Stripe sofort.',
            )
          : t(
              'subscription.contact.hintDefault',
              'Vorgeschlagen aus der Finanz-E-Mail und der Adresse eurer QR-Rechnungen. Speichert sie, damit die Rechnungen von Hubra an den Verein gehen.',
            )}
      </Text>
      <Stack gap={10}>
        <TextInput
          type="email"
          required
          label={t('subscription.contact.email', 'E-Mail für Rechnungen')}
          {...field('email')}
        />
        <Grid gap="sm">
          <Grid.Col span={{ base: 12, sm: 9 }}>
            <TextInput label={t('subscription.contact.street', 'Strasse')} {...field('street')} />
          </Grid.Col>
          <Grid.Col span={{ base: 12, sm: 3 }}>
            <TextInput label={t('subscription.contact.houseNo', 'Nr.')} {...field('houseNo')} />
          </Grid.Col>
          <Grid.Col span={{ base: 12, sm: 3 }}>
            <TextInput
              label={t('subscription.contact.postalCode', 'PLZ')}
              {...field('postalCode')}
            />
          </Grid.Col>
          <Grid.Col span={{ base: 12, sm: 6 }}>
            <TextInput label={t('subscription.contact.city', 'Ort')} {...field('city')} />
          </Grid.Col>
          <Grid.Col span={{ base: 12, sm: 3 }}>
            <TextInput
              label={t('subscription.contact.country', 'Land')}
              maxLength={2}
              {...field('country')}
            />
          </Grid.Col>
        </Grid>
        <Group justify="flex-end">
          <Button loading={saving} onClick={save}>
            {t('subscription.contact.save', 'Speichern')}
          </Button>
        </Group>
      </Stack>
    </Paper>
  )
}

/**
 * Settings › Hubra-Abo: what the club pays Hubra, paying through Stripe
 * Checkout, and Stripe's portal for card, invoices and cancelling
 * (docs/billing.md). Needs billing.billing.manage.
 */
export function SubscriptionTab() {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const [params, setParams] = useSearchParams()
  const [busy, setBusy] = useState<'pay' | 'portal' | 'cancel' | 'resume' | null>(null)
  const [confirmCancel, setConfirmCancel] = useState(false)
  const { data } = useQuery({ queryKey: qk.settings.subscription, queryFn: getHubraBilling })
  const { data: invoices } = useQuery({
    queryKey: qk.settings.subscriptionInvoices,
    queryFn: listHubraInvoices,
    enabled: Boolean(data?.stripe.hasCustomer),
  })

  // Back from Stripe Checkout: the webhook may not have arrived yet, so read
  // Stripe once and show the result.
  const checkout = params.get('checkout')
  const handled = useRef(false)
  useEffect(() => {
    if (!checkout || handled.current) return
    handled.current = true
    setParams({}, { replace: true })
    if (checkout === 'cancelled') {
      notify('info', t('subscription.cancelled', 'Zahlung abgebrochen, es wurde nichts belastet.'))
      return
    }
    void refreshHubraBilling()
      .catch(() => undefined)
      .finally(() => {
        void queryClient.invalidateQueries({ queryKey: qk.settings.subscription })
        notify('success', t('subscription.thanks', 'Danke! Das Hubra-Abo des Vereins läuft.'))
      })
  }, [checkout, notify, queryClient, setParams, t])

  const go = async (kind: 'pay' | 'portal') => {
    setBusy(kind)
    try {
      const { url } = kind === 'pay' ? await startHubraCheckout() : await openHubraPortal()
      window.location.assign(url)
    } catch (err) {
      setBusy(null)
      notify(
        'error',
        t('subscription.stripeFailed', 'Stripe ist gerade nicht erreichbar'),
        err instanceof Error ? err.message : undefined,
      )
    }
  }

  const changeSubscription = async (kind: 'cancel' | 'resume') => {
    setBusy(kind)
    try {
      const next =
        kind === 'cancel' ? await cancelHubraSubscription() : await resumeHubraSubscription()
      queryClient.setQueryData(qk.settings.subscription, next)
      notify(
        'success',
        kind === 'cancel'
          ? t('subscription.cancelDone', 'Das Abo ist gekündigt.')
          : t('subscription.resumeDone', 'Die Kündigung ist zurückgenommen.'),
      )
    } catch (err) {
      notify(
        'error',
        t('subscription.stripeFailed', 'Stripe ist gerade nicht erreichbar'),
        err instanceof Error ? err.message : undefined,
      )
    } finally {
      setBusy(null)
      setConfirmCancel(false)
    }
  }

  if (!data) return null

  const statusLabel = t(`subscription.status.${data.status}`, STATUS_DE[data.status])
  const per = data.yearly
    ? t('subscription.perYear', 'pro Jahr')
    : t('subscription.perMonth', 'pro Monat')
  const trouble = data.status === 'past_due' || data.status === 'unpaid'
  const lines = data.module_lines.filter((l) => !l.included)

  return (
    <Stack gap={20} maw={860}>
      <Paper withBorder p="lg">
        <Group justify="space-between" mb={4} gap={8}>
          <Group gap={8}>
            <Title order={3}>{t('subscription.title', 'Hubra-Abo')}</Title>
            <Badge variant="light" color={STATUS_COLOR[data.status]}>
              {statusLabel}
            </Badge>
            {data.testMode && data.enabled && (
              <Badge variant="light" color="orange">
                {t('subscription.testMode', 'Testmodus')}
              </Badge>
            )}
          </Group>
          <Group gap={8}>
            {data.stripe.hasCustomer && (
              <Button
                size="xs"
                variant="light"
                loading={busy === 'portal'}
                leftSection={<IconExternalLink size={16} />}
                onClick={() => go('portal')}
              >
                {t('subscription.manage', 'Zahlung verwalten')}
              </Button>
            )}
            {data.stripe.hasSubscription && !data.stripe.cancelAtPeriodEnd && (
              <Button
                size="xs"
                variant="subtle"
                color="red"
                loading={busy === 'cancel'}
                onClick={() => setConfirmCancel(true)}
              >
                {t('subscription.cancel', 'Abo kündigen')}
              </Button>
            )}
            {data.stripe.hasSubscription && data.stripe.cancelAtPeriodEnd && (
              <Button
                size="xs"
                variant="light"
                loading={busy === 'resume'}
                onClick={() => void changeSubscription('resume')}
              >
                {t('subscription.resume', 'Kündigung zurücknehmen')}
              </Button>
            )}
            {data.canPay && !data.stripe.hasSubscription && (
              <Button
                size="xs"
                loading={busy === 'pay'}
                leftSection={<IconCreditCard size={16} />}
                onClick={() => go('pay')}
              >
                {t('subscription.pay', 'Jetzt bezahlen')}
              </Button>
            )}
          </Group>
        </Group>
        <Text size="sm" c="dimmed" mb={16}>
          {data.enabled
            ? t(
                'subscription.hint',
                'Was der Verein für Hubra bezahlt. Bezahlt wird über Stripe, zum Beispiel mit Karte; Karte und Rechnungen verwaltet ihr im Stripe-Kundenportal.',
              )
            : t(
                'subscription.hintOff',
                'Was der Verein für Hubra bezahlt. Online bezahlen ist noch nicht eingerichtet; Hubra meldet sich bei euch.',
              )}
        </Text>

        {trouble && (
          <Alert color="red" variant="light" icon={<IconInfoCircle size={18} />} mb={16}>
            {t(
              'subscription.trouble',
              'Die letzte Zahlung hat nicht geklappt. Bitte prüft unter «Zahlung verwalten» die Karte oder das Konto, Stripe versucht es dann erneut.',
            )}
          </Alert>
        )}
        {data.stripe.cancelAtPeriodEnd && data.stripe.currentPeriodEnd && (
          <Alert color="orange" variant="light" icon={<IconInfoCircle size={18} />} mb={16}>
            {t('subscription.endsOn', 'Das Abo ist gekündigt und endet am {{date}}.', {
              date: formatDate(data.stripe.currentPeriodEnd),
            })}
          </Alert>
        )}
        {data.sponsorship_running && (
          <Alert color="grape" variant="light" icon={<IconInfoCircle size={18} />} mb={16}>
            {data.sponsored_until
              ? t('subscription.sponsoredUntil', '{{name}} bezahlt euer Abo bis am {{date}}.', {
                  name: data.sponsor_name,
                  date: formatDate(data.sponsored_until),
                })
              : t('subscription.sponsored', '{{name}} bezahlt euer Abo.', {
                  name: data.sponsor_name,
                })}
          </Alert>
        )}

        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="xl">
          <Stack gap={6}>
            <Row
              label={t('subscription.plan', 'Tarif {{plan}}', {
                plan: data.plan.charAt(0).toUpperCase() + data.plan.slice(1),
              })}
              value={chf(data.base_chf)}
            />
            {data.discount_percent > 0 && (
              <Row
                label={t('subscription.discount', 'Rabatt {{percent}} %', {
                  percent: data.discount_percent,
                })}
                value={`− ${chf(data.discount_chf)}`}
              />
            )}
            {lines.map((l) => (
              <Row
                key={`${l.source}-${l.code}`}
                label={`+ ${l.label || l.code}${
                  l.unit === 'member'
                    ? ` (${t('subscription.lineMembers', '{{n}} Mitglieder × {{price}}', { n: l.quantity, price: chf(l.unit_price_chf) })})`
                    : l.unit === 'license'
                      ? ` (${t('subscription.lineLicenses', '{{n}} Lizenzen × {{price}}', { n: l.quantity, price: chf(l.unit_price_chf) })})`
                      : l.quantity > 1
                        ? ` (${l.quantity}×)`
                        : ''
                }`}
                value={chf(l.total_chf)}
              />
            ))}
            {data.module_lines.some((l) => l.included) && (
              <Text size="xs" c="dimmed">
                {t('subscription.included', 'Im Tarif inklusive: {{list}}', {
                  list: data.module_lines
                    .filter((l) => l.included)
                    .map((l) => l.label || l.code)
                    .join(', '),
                })}
              </Text>
            )}
            <Row
              label={t('subscription.due', 'Fällig pro Monat')}
              value={chf(data.due_chf)}
              strong
            />
            {data.yearly && (
              <Text size="xs" c="dimmed">
                {t(
                  'subscription.yearlyNote',
                  'Verrechnet wird einmal im Jahr: {{amount}} {{per}}.',
                  {
                    amount: chf(String(Number(data.due_chf) * 12)),
                    per,
                  },
                )}
              </Text>
            )}
          </Stack>
          <Stack gap={6}>
            {data.status === 'trialing' && data.trial_ends && (
              <Row
                label={t('subscription.trialUntil', 'Testphase bis')}
                value={formatDate(data.trial_ends)}
              />
            )}
            {(data.stripe.currentPeriodEnd || data.period_end) && (
              <Row
                label={t('subscription.nextInvoice', 'Nächste Rechnung')}
                value={formatDate((data.stripe.currentPeriodEnd || data.period_end)!)}
              />
            )}
            {data.paymentsFeePercent != null && data.paymentsFeePercent > 0 && (
              <Row
                label={t('subscription.paymentsFee', 'Hubra-Gebühr auf Online-Zahlungen')}
                value={`${data.paymentsFeePercent} %`}
              />
            )}
            {data.status === 'trialing' && data.canPay && !data.stripe.hasSubscription && (
              <Text size="xs" c="dimmed">
                {t(
                  'subscription.trialPay',
                  'Ihr könnt jetzt schon eine Zahlungsart hinterlegen. Belastet wird erst nach der Testphase.',
                )}
              </Text>
            )}
          </Stack>
        </SimpleGrid>
      </Paper>

      <ConfirmModal
        open={confirmCancel}
        title={t('subscription.cancelTitle', 'Hubra-Abo kündigen?')}
        body={
          data.stripe.currentPeriodEnd
            ? t(
                'subscription.cancelBody',
                'Das Abo läuft bis am {{date}} weiter und endet dann. Es wird nichts mehr belastet. Bis dahin könnt ihr die Kündigung zurücknehmen.',
                { date: formatDate(data.stripe.currentPeriodEnd) },
              )
            : t(
                'subscription.cancelBodyNoDate',
                'Das Abo läuft bis zum Ende der bezahlten Periode weiter und endet dann. Es wird nichts mehr belastet.',
              )
        }
        confirmLabel={t('subscription.cancel', 'Abo kündigen')}
        onConfirm={() => void changeSubscription('cancel')}
        onClose={() => setConfirmCancel(false)}
      />

      <PlanCard />
      <AddonsCard />

      {data.enabled && <BillingContactCard />}

      {invoices && invoices.items.length > 0 && (
        <Paper withBorder p="lg">
          <Title order={4} mb={10}>
            {t('subscription.invoices', 'Rechnungen von Hubra')}
          </Title>
          <Table striped>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('subscription.invoiceDate', 'Datum')}</Table.Th>
                <Table.Th>{t('subscription.invoiceNumber', 'Nummer')}</Table.Th>
                <Table.Th>{t('subscription.invoiceTotal', 'Betrag')}</Table.Th>
                <Table.Th>{t('subscription.invoiceStatus', 'Status')}</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {invoices.items.map((inv) => (
                <Table.Tr key={inv.id}>
                  <Table.Td>{inv.created ? formatDate(inv.created) : '–'}</Table.Td>
                  <Table.Td>{inv.number ?? '–'}</Table.Td>
                  <Table.Td>{chf(inv.totalChf)}</Table.Td>
                  <Table.Td>
                    <Badge variant="light" color={inv.paid ? 'green' : 'orange'}>
                      {inv.paid
                        ? t('subscription.paid', 'Bezahlt')
                        : t('subscription.open', 'Offen')}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    {(inv.pdf || inv.url) && (
                      <Anchor href={(inv.pdf || inv.url)!} target="_blank" size="sm">
                        {inv.pdf ? 'PDF' : t('subscription.view', 'Ansehen')}
                      </Anchor>
                    )}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Paper>
      )}
    </Stack>
  )
}
