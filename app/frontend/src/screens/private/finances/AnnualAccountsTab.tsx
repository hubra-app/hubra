import { useState } from 'react'
import { useMediaQuery } from '@mantine/hooks'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Badge,
  Button,
  Group,
  NumberInput,
  Paper,
  SegmentedControl,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { IconDownload, IconLock, IconLockOpen, IconPlus } from '@tabler/icons-react'
import { useT, getCurrentLanguage } from '@/locales/i18n'
import { useAuth, useToast } from '@/context/AppContext'
import { ConfirmModal, Modal, useSubmitOnce } from '@/components/ui'
import {
  closeFiscalYear,
  createAccount,
  downloadAnnualAccounts,
  getAnnualReport,
  getChart,
  listFiscalYears,
  mapCategoryAccount,
  reopenFiscalYear,
  setOpeningBalances,
  type AccountKind,
  type AnnualLine,
  type AnnualReport,
} from '@/api/finance'
import { formatCHF, formatDate } from '@/format'
import { qk } from '@/data/keys'

const right = { textAlign: 'right' as const }

/* ── Finanzen › Jahresrechnung: balance sheet and income statement per
   fiscal year, the year close, and the chart of accounts the categories
   count on ── */
export function AnnualAccountsTab() {
  const { t } = useT()
  const [view, setView] = useState<'report' | 'chart'>('report')
  return (
    <Stack gap="md">
      <SegmentedControl
        value={view}
        onChange={(v) => setView(v as 'report' | 'chart')}
        data={[
          { value: 'report', label: t('finance.annual.report', 'Jahresrechnung') },
          { value: 'chart', label: t('finance.annual.chart', 'Kontenplan') },
        ]}
        style={{ alignSelf: 'flex-start' }}
      />
      {view === 'report' ? <Report onChart={() => setView('chart')} /> : <ChartView />}
    </Stack>
  )
}

function Report({ onChart }: { onChart: () => void }) {
  const { t } = useT()
  const { hasPermission } = useAuth()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const { data: years } = useQuery({ queryKey: qk.fiscalYears, queryFn: listFiscalYears })
  const [picked, setPicked] = useState<number | null>(null)
  const list = years?.years ?? []
  // The newest year that is over, else the running one.
  const fallback = list.find((y) => new Date(y.end) < new Date())?.year ?? list[0]?.year
  const year = picked ?? fallback
  const { data: r } = useQuery({
    queryKey: qk.annual(year ?? 0),
    queryFn: () => getAnnualReport(year!),
    enabled: !!year,
  })
  const [confirm, setConfirm] = useState<'close' | 'reopen' | null>(null)
  const [openingOpen, setOpeningOpen] = useState(false)

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: qk.fiscalYears })
    queryClient.invalidateQueries({ queryKey: qk.annualAll })
  }
  const run = async () => {
    if (!year || !confirm) return
    try {
      if (confirm === 'close') await closeFiscalYear(year)
      else await reopenFiscalYear(year)
      refresh()
      notify(
        'success',
        confirm === 'close'
          ? t('finance.annual.closed', 'Jahr {{year}} abgeschlossen', { year })
          : t('finance.annual.reopened', 'Jahr {{year}} wieder geöffnet', { year }),
      )
    } catch (err: unknown) {
      notify('error', t('common.error', 'Fehler'), err instanceof Error ? err.message : '')
    }
  }

  if (!year) return null
  const canClose = hasPermission('finance.accounts.close')
  const canEdit = hasPermission('finance.accounts.update')
  const isOver = r ? new Date(r.end) < new Date() : false

  return (
    <Stack gap="md">
      <Group justify="space-between" wrap="wrap" gap="sm">
        <Group gap="sm">
          <Select
            aria-label={t('finance.annual.year', 'Geschäftsjahr')}
            value={String(year)}
            onChange={(v) => v && setPicked(Number(v))}
            data={list.map((y) => ({
              value: String(y.year),
              label:
                y.start.endsWith('-01-01') ? String(y.year) : `${y.year}/${(y.year + 1) % 100}`,
            }))}
            w={120}
            allowDeselect={false}
          />
          {r && (
            <Badge color={r.closed ? 'green' : 'gray'} variant="light">
              {r.closed
                ? t('finance.annual.statusClosed', 'Abgeschlossen')
                : t('finance.annual.statusOpen', 'Provisorisch')}
            </Badge>
          )}
          {r && (
            <Text size="sm" c="dimmed">
              {formatDate(r.start)} – {formatDate(r.end)}
            </Text>
          )}
        </Group>
        <Group gap="xs">
          {r && !r.closed && r.openingSource === 'computed' && canEdit && (
            <Button variant="default" onClick={() => setOpeningOpen(true)}>
              {t('finance.annual.openingEdit', 'Eröffnungsbilanz')}
            </Button>
          )}
          <Button
            variant="default"
            leftSection={<IconDownload size={16} />}
            onClick={() => downloadAnnualAccounts(year, getCurrentLanguage())}
          >
            PDF
          </Button>
          {r && canClose && !r.closed && (
            <Button
              leftSection={<IconLock size={16} />}
              disabled={!isOver}
              title={isOver ? undefined : t('finance.annual.notOver', 'Das Jahr ist noch nicht vorbei')}
              onClick={() => setConfirm('close')}
            >
              {t('finance.annual.close', 'Jahr abschliessen')}
            </Button>
          )}
          {r && canClose && r.closed && (
            <Button
              variant="default"
              leftSection={<IconLockOpen size={16} />}
              onClick={() => setConfirm('reopen')}
            >
              {t('finance.annual.reopen', 'Wieder öffnen')}
            </Button>
          )}
        </Group>
      </Group>

      {r && r.notes.unmappedBookings > 0 && (
        <Alert color="yellow" variant="light">
          <Group justify="space-between" gap="sm">
            <Text size="sm">
              {t(
                'finance.annual.unmapped',
                '{{count}} Buchungen haben eine Kategorie ohne Konto und zählen als übriger Ertrag oder Aufwand.',
                { count: r.notes.unmappedBookings },
              )}
            </Text>
            <Button size="xs" variant="light" onClick={onChart}>
              {t('finance.annual.mapCategories', 'Kategorien zuordnen')}
            </Button>
          </Group>
        </Alert>
      )}

      {r && (
        <div style={{ display: 'grid', gap: 16, gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 320px), 1fr))' }}>
          <Paper withBorder p="md" radius="md">
            <Title order={3} size="h4" mb="sm">
              {t('finance.annual.balanceSheet', 'Bilanz')}
            </Title>
            <Lines
              title={t('finance.annual.assets', 'Aktiven')}
              rows={r.assets}
              previous={r.hasPrevious}
              total={r.totalAssets}
              totalLabel={t('finance.annual.totalAssets', 'Total Aktiven')}
            />
            <Lines
              title={t('finance.annual.liabilities', 'Passiven')}
              rows={[
                ...r.liabilities,
                {
                  number: r.capital.number,
                  name: r.capital.name,
                  amount: r.capital.closing,
                  previous: r.capital.previous,
                },
              ]}
              previous={r.hasPrevious}
              total={r.totalAssets}
              totalLabel={t('finance.annual.totalLiabilities', 'Total Passiven')}
            />
            <Text size="xs" c="dimmed" mt="xs">
              {t(
                'finance.annual.capitalLine',
                'Vereinsvermögen: Anfang {{opening}} + Ergebnis {{result}} = Ende {{closing}}',
                {
                  opening: formatCHF(r.capital.opening),
                  result: formatCHF(r.result),
                  closing: formatCHF(r.capital.closing),
                },
              )}
            </Text>
          </Paper>
          <Paper withBorder p="md" radius="md">
            <Title order={3} size="h4" mb="sm">
              {t('finance.annual.incomeStatement', 'Erfolgsrechnung')}
            </Title>
            <Lines
              title={t('finance.annual.income', 'Ertrag')}
              rows={r.income}
              previous={r.hasPrevious}
              total={r.totalIncome}
              totalLabel={t('finance.annual.totalIncome', 'Total Ertrag')}
            />
            <Lines
              title={t('finance.annual.expense', 'Aufwand')}
              rows={r.expense}
              previous={r.hasPrevious}
              total={r.totalExpense}
              totalLabel={t('finance.annual.totalExpense', 'Total Aufwand')}
            />
            <Group justify="space-between" mt="sm">
              <Text fw={700}>
                {r.result >= 0
                  ? t('finance.annual.profit', 'Gewinn')
                  : t('finance.annual.loss', 'Verlust')}
              </Text>
              <Text fw={700} className="num" c={r.result >= 0 ? 'green' : 'red'}>
                {formatCHF(r.result)}
              </Text>
            </Group>
          </Paper>
        </div>
      )}

      {r && (
        <Text size="xs" c="dimmed">
          {t(
            'finance.annual.cashNote',
            'Gezählt werden die abgeschlossenen Zahlungen des Jahres, über ihre Kategorie den Konten zugeordnet. Bar bezahlte Buchungen landen in der Kasse, alle anderen auf der Bank.',
          )}
          {r.notes.openInvoices.count > 0 &&
            ' ' +
              t(
                'finance.annual.openInvoices',
                'Offene Rechnungen am Jahresende: {{count}} ({{amount}}), nicht in der Bilanz.',
                {
                  count: r.notes.openInvoices.count,
                  amount: formatCHF(r.notes.openInvoices.amount),
                },
              )}
        </Text>
      )}

      <ConfirmModal
        open={!!confirm}
        onClose={() => setConfirm(null)}
        title={
          confirm === 'close'
            ? t('finance.annual.closeTitle', 'Jahr {{year}} abschliessen?', { year })
            : t('finance.annual.reopenTitle', 'Jahr {{year}} wieder öffnen?', { year })
        }
        body={
          confirm === 'close'
            ? t(
                'finance.annual.closeBody',
                'Die Schlussbilanz wird gespeichert und eröffnet das nächste Jahr. Danach lassen sich Buchungen in diesem Jahr nicht mehr erfassen, ändern oder löschen.',
              )
            : t(
                'finance.annual.reopenBody',
                'Buchungen in diesem Jahr lassen sich danach wieder ändern. Schliesse das Jahr danach erneut ab.',
              )
        }
        onConfirm={run}
      />
      {r && openingOpen && (
        <OpeningModal report={r} onClose={() => setOpeningOpen(false)} onSaved={refresh} />
      )}
    </Stack>
  )
}

function Lines({
  title,
  rows,
  previous,
  total,
  totalLabel,
}: {
  title: string
  rows: AnnualLine[]
  previous: boolean
  total: number
  totalLabel: string
}) {
  const { t } = useT()
  // On a phone: no account numbers and no previous year, so it fits.
  const narrow = useMediaQuery('(max-width: 36em)') ?? false
  const showPrev = previous && !narrow
  return (
    <Table mb="md" verticalSpacing={6}>
      <Table.Thead>
        <Table.Tr>
          {!narrow && <Table.Th style={{ width: 56 }}>{t('finance.annual.number', 'Nr.')}</Table.Th>}
          <Table.Th>{title}</Table.Th>
          <Table.Th style={right}>{t('finance.annual.amount', 'Betrag')}</Table.Th>
          {showPrev && <Table.Th style={right}>{t('finance.annual.previous', 'Vorjahr')}</Table.Th>}
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {rows.length === 0 && (
          <Table.Tr>
            <Table.Td colSpan={(showPrev ? 3 : 2) + (narrow ? 0 : 1)}>
              <Text size="sm" c="dimmed">
                {t('finance.annual.none', 'Keine Beträge')}
              </Text>
            </Table.Td>
          </Table.Tr>
        )}
        {rows.map((l) => (
          <Table.Tr key={l.number}>
            {!narrow && (
              <Table.Td c="dimmed" className="num">
                {l.number}
              </Table.Td>
            )}
            <Table.Td>{l.name}</Table.Td>
            <Table.Td style={right} className="num">
              {formatCHF(l.amount)}
            </Table.Td>
            {showPrev && (
              <Table.Td style={right} className="num" c="dimmed">
                {formatCHF(l.previous ?? 0)}
              </Table.Td>
            )}
          </Table.Tr>
        ))}
      </Table.Tbody>
      <Table.Tfoot>
        <Table.Tr>
          {!narrow && <Table.Td />}
          <Table.Td fw={700}>{totalLabel}</Table.Td>
          <Table.Td style={right} fw={700} className="num">
            {formatCHF(total)}
          </Table.Td>
          {showPrev && <Table.Td />}
        </Table.Tr>
      </Table.Tfoot>
    </Table>
  )
}

function OpeningModal({
  report,
  onClose,
  onSaved,
}: {
  report: AnnualReport
  onClose: () => void
  onSaved: () => void
}) {
  const { t } = useT()
  const { notify } = useToast()
  const { data: chart } = useQuery({ queryKey: qk.chart, queryFn: getChart })
  const [values, setValues] = useState<Record<string, number>>(() =>
    Object.fromEntries(report.opening.map((o) => [o.number, o.amount])),
  )
  const [save, saving] = useSubmitOnce(async () => {
    try {
      await setOpeningBalances(report.year, values)
      onSaved()
      onClose()
      notify('success', t('finance.annual.openingSaved', 'Eröffnungsbilanz gespeichert'))
    } catch (err: unknown) {
      notify('error', t('common.error', 'Fehler'), err instanceof Error ? err.message : '')
    }
  })
  const rows = (chart?.accounts ?? []).filter((a) => a.kind === 'asset' || a.kind === 'liability')
  return (
    <Modal
      open
      onClose={onClose}
      title={t('finance.annual.openingTitle', 'Eröffnungsbilanz {{year}}', { year: report.year })}
    >
      <Stack gap="sm">
        <Text size="sm" c="dimmed">
          {t(
            'finance.annual.openingHint',
            'Die Beträge am ersten Tag des Jahres. Kasse und Bank sind aus den früheren Buchungen vorgeschlagen; das Vereinsvermögen ergibt sich aus Aktiven minus Passiven.',
          )}
        </Text>
        {rows.map((a) => (
          <NumberInput
            key={a.number}
            label={`${a.number} ${a.name}`}
            value={values[a.number] ?? 0}
            onChange={(v) => setValues((s) => ({ ...s, [a.number]: Number(v) || 0 }))}
            decimalScale={2}
            thousandSeparator="’"
            prefix="CHF "
          />
        ))}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {t('common.cancel', 'Abbrechen')}
          </Button>
          <Button loading={saving} onClick={save}>
            {t('common.save', 'Speichern')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}

function ChartView() {
  const { t } = useT()
  const { hasPermission } = useAuth()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const { data: chart } = useQuery({ queryKey: qk.chart, queryFn: getChart })
  const canEdit = hasPermission('finance.accounts.update')
  const [number, setNumber] = useState('')
  const [name, setName] = useState('')
  const [kind, setKind] = useState<AccountKind>('expense')

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: qk.chart })
    queryClient.invalidateQueries({ queryKey: qk.annualAll })
  }
  const fail = (err: unknown) =>
    notify('error', t('common.error', 'Fehler'), err instanceof Error ? err.message : '')

  const [add, adding] = useSubmitOnce(async () => {
    try {
      await createAccount({ number: number.trim(), name: name.trim(), kind })
      setNumber('')
      setName('')
      refresh()
    } catch (err) {
      fail(err)
    }
  })

  if (!chart) return null
  const kindLabel: Record<AccountKind, string> = {
    asset: t('finance.annual.kindAsset', 'Aktiven'),
    liability: t('finance.annual.kindLiability', 'Passiven'),
    equity: t('finance.annual.kindEquity', 'Eigenkapital'),
    income: t('finance.annual.kindIncome', 'Ertrag'),
    expense: t('finance.annual.kindExpense', 'Aufwand'),
  }
  const options = chart.accounts
    .filter((a) => a.kind === 'income' || a.kind === 'expense')
    .map((a) => ({ value: String(a.id), label: `${a.number} ${a.name}` }))

  return (
    <div style={{ display: 'grid', gap: 16, gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 320px), 1fr))' }}>
      <Paper withBorder p="md" radius="md">
        <Title order={3} size="h4" mb={4}>
          {t('finance.annual.categoriesTitle', 'Kategorien und Konten')}
        </Title>
        <Text size="sm" c="dimmed" mb="sm">
          {t(
            'finance.annual.categoriesHint',
            'Jede Buchung zählt über ihre Kategorie auf ein Konto. Ohne Konto zählt sie als übriger Ertrag oder Aufwand.',
          )}
        </Text>
        <Stack gap="xs">
          {chart.categories.map((c) => (
            <Group key={c.id} justify="space-between" wrap="nowrap" gap="sm">
              <Text size="sm" style={{ flex: 1, minWidth: 0 }} truncate>
                {c.name}
              </Text>
              <Select
                aria-label={t('finance.annual.accountFor', 'Konto für {{name}}', { name: c.name })}
                placeholder={t('finance.annual.noAccount', 'Kein Konto')}
                value={c.accountId ? String(c.accountId) : null}
                data={options}
                searchable
                clearable
                disabled={!canEdit}
                w={240}
                onChange={async (v) => {
                  try {
                    await mapCategoryAccount(c.id, v ? Number(v) : null)
                    refresh()
                  } catch (err) {
                    fail(err)
                  }
                }}
              />
            </Group>
          ))}
        </Stack>
      </Paper>
      <Paper withBorder p="md" radius="md">
        <Title order={3} size="h4" mb={4}>
          {t('finance.annual.chart', 'Kontenplan')}
        </Title>
        <Text size="sm" c="dimmed" mb="sm">
          {t(
            'finance.annual.chartHint',
            'Der Kontenplan für Vereine nach dem Schweizer KMU-Kontenrahmen. Eigene Konten lassen sich ergänzen.',
          )}
        </Text>
        <Table verticalSpacing={4}>
          <Table.Tbody>
            {chart.accounts.map((a) => (
              <Table.Tr key={a.id}>
                <Table.Td c="dimmed" className="num" style={{ width: 56 }}>
                  {a.number}
                </Table.Td>
                <Table.Td>{a.name}</Table.Td>
                <Table.Td style={right}>
                  <Text size="xs" c="dimmed">
                    {kindLabel[a.kind]}
                  </Text>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
        {canEdit && (
          <Group mt="sm" gap="xs" align="flex-end" wrap="wrap">
            <TextInput
              label={t('finance.annual.number', 'Nr.')}
              value={number}
              onChange={(e) => setNumber(e.currentTarget.value)}
              w={80}
            />
            <TextInput
              label={t('finance.annual.accountName', 'Konto')}
              value={name}
              onChange={(e) => setName(e.currentTarget.value)}
              style={{ flex: 1, minWidth: 140 }}
            />
            <Select
              label={t('finance.annual.kind', 'Art')}
              value={kind}
              onChange={(v) => v && setKind(v as AccountKind)}
              data={(['asset', 'liability', 'income', 'expense'] as AccountKind[]).map((k) => ({
                value: k,
                label: kindLabel[k],
              }))}
              allowDeselect={false}
              w={130}
            />
            <Button
              leftSection={<IconPlus size={16} />}
              loading={adding}
              disabled={!number.trim() || !name.trim()}
              onClick={add}
            >
              {t('finance.annual.addAccount', 'Hinzufügen')}
            </Button>
          </Group>
        )}
      </Paper>
    </div>
  )
}
