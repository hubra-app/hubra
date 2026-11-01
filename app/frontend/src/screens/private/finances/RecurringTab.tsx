import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Badge,
  Button,
  Group,
  NumberInput,
  Paper,
  SegmentedControl,
  Select,
  SimpleGrid,
  Switch,
  Table,
  Text,
  TextInput,
} from '@mantine/core'
import { IconPencil, IconPlus, IconTrash } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useAuth, useToast } from '@/context/AppContext'
import { ConfirmModal, Modal, useSubmitOnce } from '@/components/ui'
import {
  createRecurring,
  deleteRecurring,
  listRecurring,
  listTxCategories,
  updateRecurring,
  type RecurringInterval,
  type RecurringTransaction,
  type RecurringTransactionInput,
} from '@/api/finance'
import { formatCHF, formatDate } from '@/format'
import { qk } from '@/data/keys'
import { PAYMENT_METHODS, methodLabel } from './transactionLabels'

const INTERVALS: RecurringInterval[] = ['monthly', 'quarterly', 'half_yearly', 'yearly']

function emptyForm(): RecurringTransactionInput {
  return {
    description: '',
    type: 'expense',
    amount: 0,
    categoryId: null,
    payeeName: null,
    method: 'IBAN',
    interval: 'monthly',
    startDate: new Date().toISOString().slice(0, 10),
    endDate: null,
    bookCompleted: false,
    countsForFees: true,
    active: true,
  }
}

/* ── Recurring income and expenses ── */
export function RecurringTab() {
  const { t } = useT()
  const { notify } = useToast()
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const canCreate = hasPermission('finance.transactions.create')
  const canUpdate = hasPermission('finance.transactions.update')
  const canDelete = hasPermission('finance.transactions.delete')
  const { data: rules = [], isLoading } = useQuery({
    queryKey: qk.recurring,
    queryFn: () => listRecurring(),
  })
  const { data: categories = [] } = useQuery({
    queryKey: qk.transactions.categories,
    queryFn: () => listTxCategories(),
  })
  const [editing, setEditing] = useState<RecurringTransaction | null>(null)
  const [formOpen, setFormOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<RecurringTransaction | null>(null)
  const [form, setForm] = useState<RecurringTransactionInput>(emptyForm)
  const [error, setError] = useState<string | null>(null)

  const set = <K extends keyof RecurringTransactionInput>(
    key: K,
    value: RecurringTransactionInput[K],
  ) => setForm((f) => ({ ...f, [key]: value }))

  const intervalLabel = (interval: RecurringInterval) =>
    ({
      monthly: t('finance.recurring.monthly', 'Monatlich'),
      quarterly: t('finance.recurring.quarterly', 'Vierteljährlich'),
      half_yearly: t('finance.recurring.halfYearly', 'Halbjährlich'),
      yearly: t('finance.recurring.yearly', 'Jährlich'),
    })[interval]

  const openNew = () => {
    setEditing(null)
    setForm(emptyForm())
    setError(null)
    setFormOpen(true)
  }

  const openEdit = (rule: RecurringTransaction) => {
    setEditing(rule)
    setForm({
      description: rule.description,
      type: rule.type,
      amount: rule.amount,
      categoryId: rule.categoryId,
      payeeName: rule.payeeName,
      method: rule.method,
      interval: rule.interval,
      startDate: rule.startDate,
      endDate: rule.endDate,
      bookCompleted: rule.bookCompleted,
      countsForFees: rule.countsForFees,
      active: rule.active,
    })
    setError(null)
    setFormOpen(true)
  }

  const save = async () => {
    if (!form.description.trim() || !(form.amount > 0) || !form.startDate) {
      setError(
        t(
          'finance.recurring.required',
          'Beschreibung, Betrag und erstes Datum sind nötig.',
        ),
      )
      return
    }
    try {
      if (editing) await updateRecurring(editing.id, form)
      else await createRecurring(form)
      queryClient.invalidateQueries({ queryKey: qk.recurring })
      setFormOpen(false)
      notify(
        'success',
        t('finance.recurring.saved', 'Wiederkehrende Buchung gespeichert'),
        form.description,
      )
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t('common.error', 'Fehler'))
    }
  }
  const [submit, saving] = useSubmitOnce(save)

  const confirmDelete = async () => {
    if (!deleteTarget) return
    try {
      await deleteRecurring(deleteTarget.id)
      queryClient.invalidateQueries({ queryKey: qk.recurring })
      notify(
        'info',
        t('finance.recurring.deleted', 'Wiederkehrende Buchung gelöscht'),
        deleteTarget.description,
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error', 'Fehler'),
        err instanceof Error ? err.message : '',
      )
    }
  }

  const running = rules.filter((r) => r.active && r.nextDate)
  const yearlyExpenses = running
    .filter((r) => r.type === 'expense')
    .reduce((sum, r) => sum + r.yearlyAmount, 0)
  const yearlyIncome = running
    .filter((r) => r.type === 'income')
    .reduce((sum, r) => sum + r.yearlyAmount, 0)

  const emptyRow = (text: string) => (
    <Table.Tr>
      <Table.Td
        colSpan={5}
        style={{
          textAlign: 'center',
          color: 'var(--hb-text-3)',
          padding: 24,
          fontSize: 'var(--mantine-font-size-sm)',
        }}
      >
        {text}
      </Table.Td>
    </Table.Tr>
  )

  return (
    <div>
      <Group justify="space-between" mb={16} className="page-actions">
        <Text size="sm" c="dimmed" maw={560}>
          {t(
            'finance.recurring.intro',
            'Miete, Versicherungen, Verbandsbeiträge: einmal erfassen, Hubra bucht sie an jedem Fälligkeitsdatum.',
          )}
        </Text>
        {canCreate && (
          <Button variant="filled" onClick={openNew}>
            <IconPlus size={16} />
            {t('finance.recurring.new', 'Neue wiederkehrende Buchung')}
          </Button>
        )}
      </Group>
      <Paper withBorder shadow="sm" radius="lg">
        <div style={{ overflowX: 'auto' }}>
          <Table highlightOnHover className="responsive-table">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('common.description', 'Beschreibung')}</Table.Th>
                <Table.Th style={{ textAlign: 'right' }}>
                  {t('finance.amount', 'Betrag')}
                </Table.Th>
                <Table.Th>{t('finance.recurring.next', 'Nächste Buchung')}</Table.Th>
                <Table.Th style={{ textAlign: 'right' }}>
                  {t('finance.recurring.perYear', 'Pro Jahr')}
                </Table.Th>
                <Table.Th style={{ width: 80 }}></Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {isLoading
                ? emptyRow(t('finance.loading', 'Wird geladen …'))
                : rules.length === 0
                  ? emptyRow(
                      t('finance.recurring.none', 'Noch keine wiederkehrenden Buchungen.'),
                    )
                  : rules.map((r) => {
                      const stopped = !r.active || !r.nextDate
                      return (
                        <Table.Tr key={r.id} style={{ opacity: stopped ? 0.55 : 1 }}>
                          <Table.Td data-label={t('common.description', 'Beschreibung')}>
                            <div style={{ fontWeight: 500 }}>{r.description}</div>
                            <div
                              style={{
                                fontSize: 'var(--mantine-font-size-xs)',
                                color: 'var(--hb-text-3)',
                              }}
                            >
                              {[r.categoryName, r.payeeName].filter(Boolean).join(' · ')}
                            </div>
                          </Table.Td>
                          <Table.Td
                            data-label={t('finance.amount', 'Betrag')}
                            style={{ textAlign: 'right' }}
                          >
                            <span
                              className="num"
                              style={{
                                fontWeight: 700,
                                color: r.type === 'income' ? '#1f9d57' : '#ff4d3d',
                              }}
                            >
                              {r.type === 'income' ? '+' : '−'}
                              {formatCHF(r.amount)}
                            </span>
                            <div
                              style={{
                                fontSize: 'var(--mantine-font-size-xs)',
                                color: 'var(--hb-text-3)',
                              }}
                            >
                              {intervalLabel(r.interval)}
                            </div>
                          </Table.Td>
                          <Table.Td data-label={t('finance.recurring.next', 'Nächste Buchung')}>
                            {!r.active ? (
                              <Badge variant="light" color="gray">
                                {t('finance.recurring.paused', 'Pausiert')}
                              </Badge>
                            ) : r.nextDate ? (
                              <span className="num">{formatDate(r.nextDate)}</span>
                            ) : (
                              <Badge variant="light" color="gray">
                                {t('finance.recurring.ended', 'Beendet')}
                              </Badge>
                            )}
                          </Table.Td>
                          <Table.Td
                            data-label={t('finance.recurring.perYear', 'Pro Jahr')}
                            style={{ textAlign: 'right' }}
                          >
                            <span className="num">{formatCHF(r.yearlyAmount)}</span>
                          </Table.Td>
                          <Table.Td data-label="">
                            <div style={{ display: 'flex', gap: 4 }}>
                              {canUpdate && (
                                <Button
                                  size="sm"
                                  variant="subtle"
                                  aria-label={t('common.edit', 'Bearbeiten')}
                                  onClick={() => openEdit(r)}
                                >
                                  <IconPencil size={16} />
                                </Button>
                              )}
                              {canDelete && (
                                <Button
                                  size="sm"
                                  variant="subtle"
                                  style={{ color: '#ff4d3d' }}
                                  aria-label={t('common.delete', 'Löschen')}
                                  onClick={() => setDeleteTarget(r)}
                                >
                                  <IconTrash size={16} />
                                </Button>
                              )}
                            </div>
                          </Table.Td>
                        </Table.Tr>
                      )
                    })}
            </Table.Tbody>
            {running.length > 0 && (
              <Table.Tfoot>
                <Table.Tr>
                  <Table.Td colSpan={3} style={{ fontWeight: 700 }}>
                    {t('finance.recurring.totalPerYear', 'Total pro Jahr')}
                  </Table.Td>
                  <Table.Td style={{ textAlign: 'right' }}>
                    <div className="num" style={{ color: '#ff4d3d', fontWeight: 700 }}>
                      −{formatCHF(yearlyExpenses)}
                    </div>
                    {yearlyIncome > 0 && (
                      <div className="num" style={{ color: '#1f9d57', fontWeight: 700 }}>
                        +{formatCHF(yearlyIncome)}
                      </div>
                    )}
                  </Table.Td>
                  <Table.Td />
                </Table.Tr>
              </Table.Tfoot>
            )}
          </Table>
        </div>
      </Paper>

      <Modal
        wide
        open={formOpen}
        onClose={() => setFormOpen(false)}
        onSubmit={() => void submit()}
        title={
          editing
            ? t('finance.recurring.edit', 'Wiederkehrende Buchung bearbeiten')
            : t('finance.recurring.new', 'Neue wiederkehrende Buchung')
        }
        subtitle={editing?.description}
        footer={
          <>
            <Button variant="default" onClick={() => setFormOpen(false)}>
              {t('common.cancel', 'Abbrechen')}
            </Button>
            <Button type="submit" variant="filled" loading={saving}>
              {editing ? t('common.save', 'Speichern') : t('common.create', 'Erstellen')}
            </Button>
          </>
        }
      >
        <SegmentedControl
          fullWidth
          value={form.type}
          onChange={(v) => set('type', v as 'income' | 'expense')}
          data={[
            { value: 'expense', label: t('finance.form.expense', 'Ausgabe') },
            { value: 'income', label: t('finance.form.income', 'Einnahme') },
          ]}
          color={form.type === 'income' ? 'green' : 'red'}
        />
        <TextInput
          label={t('common.description', 'Beschreibung')}
          placeholder={t('finance.recurring.descriptionPlaceholder', 'z. B. Miete Vereinslokal')}
          value={form.description}
          onChange={(e) => set('description', e.currentTarget.value)}
          data-autofocus
        />
        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm">
          <NumberInput
            label={t('finance.amountChf', 'Betrag (CHF)')}
            value={form.amount || ''}
            onChange={(v) => set('amount', typeof v === 'number' ? v : Number(v) || 0)}
            min={0}
            decimalScale={2}
            decimalSeparator="."
            thousandSeparator="’"
            hideControls
            placeholder="100.00"
          />
          <Select
            label={t('finance.recurring.interval', 'Wiederholung')}
            data={INTERVALS.map((i) => ({ value: i, label: intervalLabel(i) }))}
            value={form.interval}
            onChange={(v) => set('interval', (v ?? 'monthly') as RecurringInterval)}
            allowDeselect={false}
          />
          <TextInput
            type="date"
            label={t('finance.recurring.start', 'Erstes Datum')}
            description={t(
              'finance.recurring.startHint',
              'Die Daten danach folgen im gewählten Abstand.',
            )}
            value={form.startDate}
            onChange={(e) => set('startDate', e.currentTarget.value)}
          />
          <TextInput
            type="date"
            label={t('finance.recurring.end', 'Letztes Datum (optional)')}
            value={form.endDate ?? ''}
            onChange={(e) => set('endDate', e.currentTarget.value || null)}
          />
          <Select
            label={t('finance.form.categoryOptional', 'Kategorie (optional)')}
            data={categories.map((c) => ({ value: c.id, label: c.name }))}
            value={form.categoryId != null ? String(form.categoryId) : null}
            onChange={(v) => set('categoryId', v ? Number(v) : null)}
            placeholder={t('finance.selectCategory', 'Kategorie wählen …')}
            searchable
            clearable
          />
          <Select
            label={t('finance.paymentMethod', 'Zahlungsart')}
            data={PAYMENT_METHODS.map((m) => ({ value: m, label: methodLabel(t, m) }))}
            value={form.method}
            onChange={(v) => set('method', v ?? 'IBAN')}
            allowDeselect={false}
          />
        </SimpleGrid>
        <TextInput
          label={t('finance.form.payee', 'Von / an (optional)')}
          placeholder={t('finance.form.payeePlaceholder', 'z. B. Baumarkt AG')}
          value={form.payeeName ?? ''}
          onChange={(e) => set('payeeName', e.currentTarget.value || null)}
        />
        <Switch
          label={t('finance.recurring.bookCompleted', 'Als bezahlt buchen (Dauerauftrag)')}
          description={t(
            'finance.recurring.bookCompletedHint',
            'Sonst wird die Buchung als offen erfasst und du bestätigst sie, wenn das Geld geflossen ist.',
          )}
          checked={form.bookCompleted}
          onChange={(e) => set('bookCompleted', e.currentTarget.checked)}
        />
        {form.type === 'expense' && (
          <Switch
            label={t(
              'finance.recurring.countsForFees',
              'Zählt zu den Jahresausgaben für die Mitgliederbeiträge',
            )}
            checked={form.countsForFees}
            onChange={(e) => set('countsForFees', e.currentTarget.checked)}
          />
        )}
        {editing && (
          <Switch
            label={t('finance.recurring.active', 'Aktiv')}
            checked={form.active}
            onChange={(e) => set('active', e.currentTarget.checked)}
          />
        )}
        {error && (
          <Text size="sm" c="red">
            {error}
          </Text>
        )}
      </Modal>
      <ConfirmModal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title={t('finance.recurring.deleteTitle', '«{{name}}» löschen?', {
          name: deleteTarget?.description ?? '',
        })}
        body={t(
          'finance.recurring.deleteBody',
          'Bereits gebuchte Einträge bleiben erhalten.',
        )}
        onConfirm={confirmDelete}
      />
    </div>
  )
}
