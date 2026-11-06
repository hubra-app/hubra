import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ActionIcon,
  Alert,
  Anchor,
  Badge,
  Button,
  Group,
  Modal,
  NumberInput,
  Paper,
  Select,
  SimpleGrid,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  Textarea,
  Title,
} from '@mantine/core'
import {
  IconExternalLink,
  IconInfoCircle,
  IconPencil,
  IconPlus,
  IconRefresh,
  IconTrash,
} from '@tabler/icons-react'
import { useAdmin } from '@/context/AdminContext'
import { formatDate, formatDateTime } from '@/format'
import { tr } from '@/lang'
import { planLabel, priceUnitOptions, priceUnitSuffix } from '@/labels'
import { usePlanChoices } from '@/plans'
import {
  getTenantBilling,
  getTenantModules,
  setTenantBilling,
  setTenantPlan,
  syncTenantBilling,
  type BillingAddon,
  type BillingStatus,
  type BillingTerms,
  type TenantBilling as Billing,
} from '@/api/tenants'
import type { PriceUnit } from '@/api/platform'
import { chf, STATUS, statusText } from '@/billing'

function Row({
  label,
  value,
  strong,
}: {
  label: string
  value: React.ReactNode
  strong?: boolean
}) {
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

/**
 * What the club pays the platform: plan status, its own price, discount,
 * sponsor and paid add-ons, and its Stripe subscription (docs/billing.md).
 * Saving the terms pushes them to the club's Stripe subscription.
 */
export function TenantBilling({ tenantId }: { tenantId: number }) {
  const { notify } = useAdmin()
  const queryClient = useQueryClient()
  const { data } = useQuery({
    queryKey: ['tenant-billing', tenantId],
    queryFn: () => getTenantBilling(tenantId),
  })
  const [editing, setEditing] = useState(false)

  if (!data) return null
  const s = STATUS[data.status]

  return (
    <Paper withBorder p="lg" mb={20}>
      <Group justify="space-between" mb={4} gap={8}>
        <Group gap={8}>
          <Title order={3}>{tr('Abrechnung', 'Billing')}</Title>
          <Badge variant="light" color={s.color}>
            {statusText(data.status)}
          </Badge>
          {data.sponsorship_running && (
            <Badge variant="light" color="grape">
              {tr('Gesponsert', 'Sponsored')}
            </Badge>
          )}
        </Group>
        <Button
          size="xs"
          variant="light"
          leftSection={<IconPencil size={16} />}
          onClick={() => setEditing(true)}
        >
          {tr('Bearbeiten', 'Edit')}
        </Button>
      </Group>
      <Text size="sm" c="dimmed" mb={16}>
        {data.stripe.enabled
          ? tr(
              'Der Verein bezahlt über Stripe. Änderungen hier gehen beim Speichern an sein Stripe-Abo, ab der nächsten Rechnung.',
              'The club pays through Stripe. Changes here go to its Stripe subscription when saved, from the next invoice.',
            )
          : tr(
              'Nur festgehalten: Die Abrechnung über Stripe ist ausgeschaltet (Zahlungen › Abrechnung der Vereine).',
              'Recorded only: billing through Stripe is off (Payments › Club billing).',
            )}
      </Text>

      {data.sponsorship_ending_soon && (
        <Alert color="orange" variant="light" icon={<IconInfoCircle size={18} />} mb={16}>
          {tr(
            `Das Sponsoring durch ${data.sponsor_name} endet in ${data.sponsorship_days_left} Tagen (${formatDate(data.sponsored_until!)}).`,
            `The sponsorship by ${data.sponsor_name} ends in ${data.sponsorship_days_left} days (${formatDate(data.sponsored_until!)}).`,
          )}
        </Alert>
      )}
      {data.sponsorship_ended && (
        <Alert color="gray" variant="light" icon={<IconInfoCircle size={18} />} mb={16}>
          {tr(
            `Das Sponsoring durch ${data.sponsor_name} ist am ${formatDate(data.sponsored_until!)} abgelaufen.`,
            `The sponsorship by ${data.sponsor_name} ended on ${formatDate(data.sponsored_until!)}.`,
          )}
        </Alert>
      )}

      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="xl">
        <Stack gap={6}>
          <Row
            label={
              data.price_chf != null
                ? tr('Eigener Preis', 'Own price')
                : tr(`Tarif ${planLabel(data.plan, tr)}`, `${planLabel(data.plan, tr)} plan`)
            }
            value={data.price_chf != null || data.plan_price_chf != null ? chf(data.base_chf) : '–'}
          />
          {data.discount_percent > 0 && (
            <Row
              label={tr(`Rabatt ${data.discount_percent} %`, `Discount ${data.discount_percent} %`)}
              value={`− ${chf(data.discount_chf)}`}
            />
          )}
          {data.module_lines.some((l) => l.included) && (
            <Text size="xs" c="dimmed">
              {tr('Im Tarif inklusive: ', 'Included in the plan: ')}
              {data.module_lines
                .filter((l) => l.included)
                .map((l) => l.label || l.code)
                .join(', ')}
            </Text>
          )}
          {data.module_lines
            .filter((l) => !l.included)
            .map((l) => (
              <Stack key={`${l.source}-${l.code}`} gap={0}>
                <Row
                  label={`+ ${l.label || l.code}`}
                  value={l.included ? tr('inklusive', 'included') : chf(l.total_chf)}
                />
                {(l.source === 'plan' || l.unit !== 'flat') && (
                  <Text size="xs" c="dimmed">
                    {[
                      l.source === 'plan' ? tr('Im Tarif', 'In the plan') : null,
                      !l.included && l.unit !== 'flat'
                        ? `${l.quantity.toLocaleString('de-CH')} × ${chf(l.unit_price_chf)}${priceUnitSuffix(l.unit, tr)}`
                        : null,
                    ]
                      .filter(Boolean)
                      .join(' · ')}
                  </Text>
                )}
              </Stack>
            ))}
          <Row
            label={tr('Total pro Monat', 'Total per month')}
            value={chf(data.total_chf)}
            strong
          />
          <Row label={tr('Fällig pro Monat', 'Due per month')} value={chf(data.due_chf)} strong />
          {data.price_chf == null && data.plan_price_chf == null && (
            <Text size="xs" c="dimmed">
              {tr(
                'Kein Preis für diesen Tarif: Alle Vereine › Tarife & Preise.',
                'No price for this plan: All clubs › Plans & prices.',
              )}
            </Text>
          )}
        </Stack>
        <Stack gap={6}>
          {data.status === 'trialing' && data.trial_ends && (
            <Row
              label={tr('Testphase bis', 'Trial until')}
              value={`${formatDate(data.trial_ends)} (${tr(`${data.trial_days_left} Tage`, `${data.trial_days_left} days`)})`}
            />
          )}
          {data.period_end && (
            <Row label={tr('Periode bis', 'Period ends')} value={formatDate(data.period_end)} />
          )}
          {data.sponsored && (
            <>
              <Row label={tr('Sponsor', 'Sponsor')} value={data.sponsor_name} />
              <Row
                label={tr('Gesponsert bis', 'Sponsored until')}
                value={
                  data.sponsored_until
                    ? formatDate(data.sponsored_until)
                    : tr('offen', 'open-ended')
                }
              />
              {data.sponsor_note && (
                <Text size="xs" c="dimmed">
                  {data.sponsor_note}
                </Text>
              )}
            </>
          )}
          {data.note && (
            <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
              {data.note}
            </Text>
          )}
        </Stack>
      </SimpleGrid>

      {data.stripe.enabled && <StripeSection tenantId={tenantId} data={data} />}

      {editing && (
        <BillingModal
          tenantId={tenantId}
          data={data}
          onClose={() => setEditing(false)}
          onSave={async (values, plan) => {
            try {
              if (plan !== data.plan) {
                await setTenantPlan(tenantId, plan)
                for (const key of ['tenant', 'tenant-limits', 'tenants-health']) {
                  void queryClient.invalidateQueries({ queryKey: [key] })
                }
              }
              const fresh = await setTenantBilling(tenantId, values)
              queryClient.setQueryData(['tenant-billing', tenantId], fresh)
              if (fresh.stripe.error)
                notify(
                  'error',
                  tr(
                    'Gespeichert, aber Stripe hat die Änderung nicht übernommen',
                    'Saved, but Stripe did not take the change',
                  ),
                  fresh.stripe.error,
                )
              else notify('success', tr('Abrechnung gespeichert', 'Billing saved'))
              setEditing(false)
            } catch (err) {
              notify(
                'error',
                tr('Speichern fehlgeschlagen', 'Could not save'),
                err instanceof Error ? err.message : undefined,
              )
            }
          }}
        />
      )}
    </Paper>
  )
}

/** The club's Stripe customer and subscription, with links into Stripe. */
function StripeSection({ tenantId, data }: { tenantId: number; data: Billing }) {
  const { notify } = useAdmin()
  const queryClient = useQueryClient()
  const [busy, setBusy] = useState(false)
  const st = data.stripe
  const dash = `https://dashboard.stripe.com${st.testMode ? '/test' : ''}`
  const stripeStatus = st.status as BillingStatus | undefined

  const sync = async () => {
    setBusy(true)
    try {
      const fresh = await syncTenantBilling(tenantId)
      queryClient.setQueryData(['tenant-billing', tenantId], fresh)
      notify('success', tr('Mit Stripe abgeglichen', 'Synced with Stripe'))
    } catch (err) {
      notify(
        'error',
        tr('Abgleich fehlgeschlagen', 'Sync failed'),
        err instanceof Error ? err.message : undefined,
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <Paper withBorder p="md" mt={20} bg="var(--mantine-color-default-hover)">
      <Group justify="space-between" mb={8} gap={8}>
        <Group gap={8}>
          <Text fw={700}>Stripe</Text>
          {st.testMode && (
            <Badge variant="light" color="orange" size="sm">
              {tr('Testmodus', 'Test mode')}
            </Badge>
          )}
          {stripeStatus && (
            <Badge variant="light" size="sm" color={STATUS[stripeStatus]?.color ?? 'gray'}>
              {STATUS[stripeStatus] ? statusText(stripeStatus) : st.status}
            </Badge>
          )}
        </Group>
        {st.subscription_id && (
          <Button
            size="xs"
            variant="light"
            loading={busy}
            leftSection={<IconRefresh size={16} />}
            onClick={sync}
          >
            {tr('Mit Stripe abgleichen', 'Sync with Stripe')}
          </Button>
        )}
      </Group>
      {st.error && (
        <Alert color="red" variant="light" icon={<IconInfoCircle size={18} />} mb={10}>
          {st.error}
        </Alert>
      )}
      {st.payment_failed_at && (
        <Alert color="orange" variant="light" icon={<IconInfoCircle size={18} />} mb={10}>
          {tr(
            `Die letzte Zahlung ist am ${formatDateTime(st.payment_failed_at)} fehlgeschlagen. Stripe versucht es nach seinen Regeln erneut.`,
            `The last payment failed on ${formatDateTime(st.payment_failed_at)}. Stripe retries by its own rules.`,
          )}
        </Alert>
      )}
      {!st.customer_id ? (
        <Text size="sm" c="dimmed">
          {tr(
            'Der Verein hat noch nicht bezahlt. Er startet das Abo in der App unter Einstellungen › Hubra-Abo.',
            'The club has not paid yet. It starts the subscription in the app under Settings › Hubra subscription.',
          )}
        </Text>
      ) : (
        <Stack gap={6}>
          <Row
            label={tr('Kunde', 'Customer')}
            value={
              <Anchor href={`${dash}/customers/${st.customer_id}`} target="_blank" size="sm">
                {st.customer_id} <IconExternalLink size={12} />
              </Anchor>
            }
          />
          {st.subscription_id && (
            <Row
              label={tr('Abo', 'Subscription')}
              value={
                <Anchor
                  href={`${dash}/subscriptions/${st.subscription_id}`}
                  target="_blank"
                  size="sm"
                >
                  {st.subscription_id} <IconExternalLink size={12} />
                </Anchor>
              }
            />
          )}
          {st.current_period_end && (
            <Row
              label={tr('Nächste Rechnung', 'Next invoice')}
              value={
                st.cancel_at_period_end
                  ? tr(
                      `endet am ${formatDate(st.current_period_end)}`,
                      `ends on ${formatDate(st.current_period_end)}`,
                    )
                  : formatDate(st.current_period_end)
              }
            />
          )}
          {st.updated_at && (
            <Text size="xs" c="dimmed">
              {tr(
                `Zuletzt von Stripe gelesen: ${formatDateTime(st.updated_at)}`,
                `Last read from Stripe: ${formatDateTime(st.updated_at)}`,
              )}
            </Text>
          )}
        </Stack>
      )}
    </Paper>
  )
}

function BillingModal({
  tenantId,
  data,
  onClose,
  onSave,
}: {
  tenantId: number
  data: Billing
  onClose: () => void
  onSave: (values: BillingTerms, plan: string) => Promise<void>
}) {
  const { data: planChoices } = usePlanChoices()
  const [plan, setPlan] = useState(data.plan)
  const planPrice = (key: string) =>
    planChoices?.plans.find((p) => p.key === key)?.price_month_chf ?? null
  const listedAddon = (code: string) => planChoices?.addons.find((a) => a.code === code)
  const [t, setT] = useState<BillingTerms>(() => ({
    status: data.status,
    trial_ends: data.trial_ends,
    period_end: data.period_end,
    price_chf: data.price_chf,
    discount_percent: data.discount_percent,
    sponsored: data.sponsored,
    sponsor_name: data.sponsor_name,
    sponsored_until: data.sponsored_until,
    sponsor_note: data.sponsor_note,
    addons: data.addons,
    licenses: data.licenses ?? {},
    note: data.note,
  }))
  const [saving, setSaving] = useState(false)
  const set = <K extends keyof BillingTerms>(key: K, value: BillingTerms[K]) =>
    setT((cur) => ({ ...cur, [key]: value }))

  // Paid add-ons are modules or plugins this club may use.
  const { data: modules } = useQuery({
    queryKey: ['tenant-modules', tenantId],
    queryFn: () => getTenantModules(tenantId),
  })
  const taken = new Set(t.addons.map((a) => a.code))
  const choices = (modules ?? [])
    .filter((m) => !m.required && !taken.has(m.code))
    .map((m) => ({ value: m.code, label: m.plugin ? `${m.name} (Plugin)` : m.name }))
  const [pick, setPick] = useState<string | null>(null)

  const setAddon = (i: number, patch: Partial<BillingAddon>) =>
    set(
      'addons',
      t.addons.map((a, j) => (j === i ? { ...a, ...patch } : a)),
    )

  const invalid = t.sponsored && !t.sponsor_name.trim()
  const licences = (code: string) => t.licenses[code] ?? 1
  const setLicences = (code: string, n: number) => set('licenses', { ...t.licenses, [code]: n })
  const moduleName = (code: string) =>
    modules?.find((m) => m.code === code)?.name ?? listedAddon(code)?.name ?? code
  // Modules of the chosen plan priced per licence (and not replaced by an add-on).
  const planLicences = (planChoices?.plans.find((p) => p.key === plan)?.modules ?? []).filter(
    (m) => m.price_chf != null && m.unit === 'license' && !taken.has(m.code),
  )
  const planIncluded = (planChoices?.plans.find((p) => p.key === plan)?.modules ?? []).map(
    (m) => m.code,
  )

  return (
    <Modal opened onClose={onClose} title={tr('Abrechnung bearbeiten', 'Edit billing')} size="xl">
      <Stack gap="md">
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <Select
            label={tr('Tarif', 'Plan')}
            description={tr(
              'Tarife und Listenpreise: Einstellungen › Tarife & Preise',
              'Plans and list prices: Settings › Plans & prices',
            )}
            allowDeselect={false}
            value={plan}
            onChange={(v) => v && setPlan(v)}
            data={(planChoices?.plans ?? [{ key: data.plan, hidden: false }])
              .filter((p) => !p.hidden || p.key === data.plan)
              .map((p) => {
                const price = 'price_month_chf' in p ? p.price_month_chf : null
                return {
                  value: p.key,
                  label:
                    price != null
                      ? `${planLabel(p.key, tr)} · ${chf(price)}`
                      : planLabel(p.key, tr),
                }
              })}
          />
          <Select
            label={tr('Status', 'Status')}
            allowDeselect={false}
            value={t.status}
            onChange={(v) => v && set('status', v as BillingStatus)}
            data={(Object.keys(STATUS) as BillingStatus[]).map((k) => ({
              value: k,
              label: statusText(k),
            }))}
          />
          {t.status === 'trialing' ? (
            <TextInput
              type="date"
              label={tr('Testphase bis', 'Trial until')}
              value={t.trial_ends ?? ''}
              onChange={(e) => set('trial_ends', e.currentTarget.value || null)}
            />
          ) : (
            <TextInput
              type="date"
              label={tr('Periode bis', 'Period ends')}
              value={t.period_end ?? ''}
              onChange={(e) => set('period_end', e.currentTarget.value || null)}
            />
          )}
          <NumberInput
            label={tr('Eigener Preis pro Monat (CHF)', 'Own price per month (CHF)')}
            description={
              planPrice(plan) != null
                ? tr(
                    `Leer: Tarifpreis ${chf(planPrice(plan))}`,
                    `Empty: plan price ${chf(planPrice(plan))}`,
                  )
                : tr('Leer: Tarifpreis (keiner gesetzt)', 'Empty: plan price (none set)')
            }
            min={0}
            max={100000}
            decimalScale={2}
            allowNegative={false}
            thousandSeparator="'"
            value={t.price_chf ?? ''}
            onChange={(v) => set('price_chf', v === '' ? null : String(v))}
          />
          <NumberInput
            label={tr('Rabatt (%)', 'Discount (%)')}
            description={tr(
              'Auf den Preis, nicht auf Zusatzmodule',
              'On the price, not on add-ons',
            )}
            min={0}
            max={100}
            decimalScale={2}
            allowNegative={false}
            suffix=" %"
            value={t.discount_percent}
            onChange={(v) => set('discount_percent', typeof v === 'number' ? v : 0)}
          />
        </SimpleGrid>

        <Paper withBorder p="md">
          <Switch
            label={tr('Gesponsert', 'Sponsored')}
            description={tr(
              'Ein Sponsor übernimmt die Kosten; der Verein zahlt nichts, solange das Sponsoring läuft.',
              'A sponsor covers the cost; the club pays nothing while the sponsorship runs.',
            )}
            checked={t.sponsored}
            onChange={(e) => set('sponsored', e.currentTarget.checked)}
          />
          {t.sponsored && (
            <SimpleGrid cols={{ base: 1, sm: 2 }} mt="sm">
              <TextInput
                label={tr('Sponsor', 'Sponsor')}
                required
                maxLength={200}
                value={t.sponsor_name}
                error={
                  invalid
                    ? tr('Name des Sponsors fehlt', 'The sponsor’s name is missing')
                    : undefined
                }
                onChange={(e) => set('sponsor_name', e.currentTarget.value)}
              />
              <TextInput
                type="date"
                label={tr('Gesponsert bis', 'Sponsored until')}
                description={tr('Leer: offen', 'Empty: open-ended')}
                value={t.sponsored_until ?? ''}
                onChange={(e) => set('sponsored_until', e.currentTarget.value || null)}
              />
              <TextInput
                label={tr('Notiz zum Sponsoring', 'Sponsorship note')}
                maxLength={500}
                value={t.sponsor_note}
                onChange={(e) => set('sponsor_note', e.currentTarget.value)}
                style={{ gridColumn: '1 / -1' }}
              />
            </SimpleGrid>
          )}
        </Paper>

        <Stack gap={6}>
          <Text size="sm" fw={600}>
            {tr('Zusatzmodule (pro Monat)', 'Add-ons (per month)')}
          </Text>
          <Text size="xs" c="dimmed">
            {tr(
              'Bezahlte Plugins oder Funktionen zusätzlich zum Tarif, je mit eigenem Preis: pauschal, pro Mitglied oder pro Lizenz. Ein Modul, das der Tarif enthält, bekommt hier einen eigenen Preis für diesen Verein.',
              'Paid plugins or features on top of the plan, each with its own price: flat, per member or per licence. A module the plan includes gets its own price for this club here.',
            )}
          </Text>
          {t.addons.length > 0 && (
            <Table.ScrollContainer minWidth={700}>
              <Table verticalSpacing={4}>
                <Table.Tbody>
                  {t.addons.map((a, i) => (
                    <Table.Tr key={a.code}>
                      <Table.Td>
                        <TextInput
                          aria-label={tr('Bezeichnung', 'Label')}
                          placeholder={a.code}
                          maxLength={120}
                          value={a.label}
                          onChange={(e) => setAddon(i, { label: e.currentTarget.value })}
                        />
                      </Table.Td>
                      <Table.Td w={150}>
                        <NumberInput
                          aria-label={tr('Preis (CHF)', 'Price (CHF)')}
                          min={0}
                          decimalScale={2}
                          allowNegative={false}
                          prefix="CHF "
                          value={a.price_chf}
                          onChange={(v) => setAddon(i, { price_chf: String(v === '' ? 0 : v) })}
                        />
                      </Table.Td>
                      <Table.Td w={170}>
                        <Select
                          aria-label={tr('Preis gilt', 'Price applies')}
                          allowDeselect={false}
                          data={priceUnitOptions(tr)}
                          value={a.unit ?? 'flat'}
                          onChange={(v) => v && setAddon(i, { unit: v as PriceUnit })}
                        />
                      </Table.Td>
                      <Table.Td w={110}>
                        {a.unit === 'license' && (
                          <NumberInput
                            aria-label={tr('Lizenzen', 'Licences')}
                            min={0}
                            allowDecimal={false}
                            allowNegative={false}
                            suffix={tr(' Liz.', ' lic.')}
                            value={licences(a.code)}
                            onChange={(v) => setLicences(a.code, typeof v === 'number' ? v : 0)}
                          />
                        )}
                      </Table.Td>
                      <Table.Td w={40}>
                        <ActionIcon
                          variant="subtle"
                          color="red"
                          aria-label={tr('Entfernen', 'Remove')}
                          onClick={() =>
                            set(
                              'addons',
                              t.addons.filter((_, j) => j !== i),
                            )
                          }
                        >
                          <IconTrash size={16} />
                        </ActionIcon>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
          )}
          <Group gap={8} align="flex-end">
            <Select
              style={{ flex: 1 }}
              aria-label={tr('Modul oder Plugin', 'Module or plugin')}
              placeholder={tr('Modul oder Plugin wählen', 'Choose a module or plugin')}
              searchable
              data={choices}
              value={pick}
              onChange={setPick}
            />
            <Button
              variant="light"
              leftSection={<IconPlus size={16} />}
              disabled={!pick}
              onClick={() => {
                const m = modules?.find((x) => x.code === pick)
                if (!m) return
                const listed = listedAddon(m.code)
                set('addons', [
                  ...t.addons,
                  {
                    code: m.code,
                    label: m.name,
                    price_chf: listed?.price_month_chf ?? '0.00',
                    unit: listed?.price_unit ?? 'flat',
                  },
                ])
                setPick(null)
              }}
            >
              {tr('Hinzufügen', 'Add')}
            </Button>
          </Group>
        </Stack>

        {planIncluded.length > 0 && (
          <Text size="xs" c="dimmed">
            {tr(
              `Im Tarif ${planLabel(plan, tr)} enthalten: ${planIncluded.map(moduleName).join(', ')}`,
              `Included in the ${planLabel(plan, tr)} plan: ${planIncluded.map(moduleName).join(', ')}`,
            )}
          </Text>
        )}
        {planLicences.length > 0 && (
          <Stack gap={6}>
            <Text size="sm" fw={600}>
              {tr('Lizenzen für Module im Tarif', 'Licences for modules in the plan')}
            </Text>
            <SimpleGrid cols={{ base: 1, sm: 2 }}>
              {planLicences.map((m) => (
                <NumberInput
                  key={m.code}
                  label={moduleName(m.code)}
                  description={`${chf(m.price_chf)}${priceUnitSuffix('license', tr)}`}
                  min={0}
                  allowDecimal={false}
                  allowNegative={false}
                  value={licences(m.code)}
                  onChange={(v) => setLicences(m.code, typeof v === 'number' ? v : 0)}
                />
              ))}
            </SimpleGrid>
          </Stack>
        )}

        <Textarea
          label={tr('Interne Notiz', 'Internal note')}
          autosize
          minRows={2}
          maxLength={1000}
          value={t.note}
          onChange={(e) => set('note', e.currentTarget.value)}
        />

        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {tr('Abbrechen', 'Cancel')}
          </Button>
          <Button
            loading={saving}
            disabled={invalid}
            onClick={async () => {
              setSaving(true)
              try {
                await onSave(t, plan)
              } finally {
                setSaving(false)
              }
            }}
          >
            {tr('Speichern', 'Save')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}
