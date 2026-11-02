import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ActionIcon,
  Alert,
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
import { IconInfoCircle, IconPencil, IconPlus, IconTrash } from '@tabler/icons-react'
import { useAdmin } from '@/context/AdminContext'
import { formatDate } from '@/format'
import { tr } from '@/lang'
import { planLabel } from '@/labels'
import {
  getTenantBilling,
  getTenantModules,
  setTenantBilling,
  type BillingAddon,
  type BillingStatus,
  type BillingTerms,
  type TenantBilling as Billing,
} from '@/api/tenants'

const STATUS: Record<BillingStatus, { de: string; en: string; color: string }> = {
  none: { de: 'Nicht verrechnet', en: 'Not billed', color: 'gray' },
  trialing: { de: 'Testphase', en: 'Trial', color: 'blue' },
  active: { de: 'Aktiv', en: 'Active', color: 'green' },
  past_due: { de: 'Zahlung überfällig', en: 'Past due', color: 'orange' },
  unpaid: { de: 'Unbezahlt', en: 'Unpaid', color: 'red' },
  canceled: { de: 'Gekündigt', en: 'Canceled', color: 'gray' },
  incomplete: { de: 'Unvollständig', en: 'Incomplete', color: 'orange' },
  paused: { de: 'Pausiert', en: 'Paused', color: 'gray' },
}

const statusText = (s: BillingStatus) => tr(STATUS[s].de, STATUS[s].en)

const chf = (amount: string | number | null | undefined) =>
  amount == null || amount === ''
    ? '–'
    : `CHF ${Number(amount).toLocaleString('de-CH', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}`

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
 * sponsor and paid add-ons. Kept here until Hubra charges through Stripe;
 * nothing is charged or sent to anyone yet.
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
        {tr(
          'Nur festgehalten: Es wird noch nichts verrechnet. Der Status folgt später dem Stripe-Abo des Vereins.',
          'Recorded only: nothing is charged yet. Later the status follows the club’s Stripe subscription.',
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
          {data.addons.map((a) => (
            <Row key={a.code} label={`+ ${a.label || a.code}`} value={chf(a.price_chf)} />
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
                'Kein Preis für diesen Tarif: Alle Vereine › Preise pro Tarif.',
                'No price for this plan: All clubs › Plan prices.',
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

      {editing && (
        <BillingModal
          tenantId={tenantId}
          data={data}
          onClose={() => setEditing(false)}
          onSave={async (values) => {
            try {
              const fresh = await setTenantBilling(tenantId, values)
              queryClient.setQueryData(['tenant-billing', tenantId], fresh)
              notify('success', tr('Abrechnung gespeichert', 'Billing saved'))
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

function BillingModal({
  tenantId,
  data,
  onClose,
  onSave,
}: {
  tenantId: number
  data: Billing
  onClose: () => void
  onSave: (values: BillingTerms) => Promise<void>
}) {
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

  return (
    <Modal opened onClose={onClose} title={tr('Abrechnung bearbeiten', 'Edit billing')} size="xl">
      <Stack gap="md">
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
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
              data.plan_price_chf != null
                ? tr(
                    `Leer: Tarifpreis ${chf(data.plan_price_chf)}`,
                    `Empty: plan price ${chf(data.plan_price_chf)}`,
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

        <Paper withBorder p="md" radius="md">
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
              'Bezahlte Plugins oder Funktionen zusätzlich zum Tarif, je mit eigenem Preis.',
              'Paid plugins or features on top of the plan, each with its own price.',
            )}
          </Text>
          {t.addons.length > 0 && (
            <Table.ScrollContainer minWidth={420}>
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
                      <Table.Td w={160}>
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
                set('addons', [...t.addons, { code: m.code, label: m.name, price_chf: '0.00' }])
                setPick(null)
              }}
            >
              {tr('Hinzufügen', 'Add')}
            </Button>
          </Group>
        </Stack>

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
                await onSave(t)
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
