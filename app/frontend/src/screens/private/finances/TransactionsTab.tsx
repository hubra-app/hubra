import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { TextInput, Button, Group, Badge, Select, ActionIcon } from '@mantine/core'
import { useT } from '@/locales/i18n'
import { IconExternalLink, IconPlus } from '@tabler/icons-react'
import { useToast, useNav, useAuth } from '@/context/AppContext'
import { useInvoices } from '@/data/lists'
import {
  Modal,
  Field,
  usePagination,
  ConfirmModal,
  ErrorBanner,
  DataTable,
  ActionButtons,
} from '@/components/ui'
import type { Transaction } from '@/types'
import {
  listTransactions,
  createTransaction,
  updateTransaction,
  deleteTransaction,
  listTxCategories,
} from '@/api/finance'
import { formatCHF } from '@/format'
import { qk } from '@/data/keys'

/* ── Transactions ────────────────────────────── */
export function TransactionsTab() {
  const { notify } = useToast()
  const { go, goInvoice } = useNav()
  const { invoices } = useInvoices()
  const { hasPermission } = useAuth()
  const { t } = useT()
  const queryClient = useQueryClient()
  const canCreate = hasPermission('transactions.transactions.create')
  const canUpdate = hasPermission('transactions.transactions.update')
  const canDelete = hasPermission('transactions.transactions.delete')
  const {
    data: transactions = [],
    isLoading: loading,
    error: fetchError,
    refetch,
  } = useQuery({
    queryKey: qk.transactions.all,
    queryFn: () => listTransactions(),
  })
  const { data: categories = [] } = useQuery({
    queryKey: qk.transactions.categories,
    queryFn: () => listTxCategories(),
    enabled: canCreate,
  })
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('All')
  const [statusFilter, setStatusFilter] = useState('All')
  const [deleteTarget, setDeleteTarget] = useState<Transaction | null>(null)
  const [editTarget, setEditTarget] = useState<Transaction | null>(null)
  const [editStatus, setEditStatus] = useState<'Pending' | 'Completed'>(
    'Completed',
  )
  const [addOpen, setAddOpen] = useState(false)
  const [addDesc, setAddDesc] = useState('')
  const [addAmount, setAddAmount] = useState('')
  const [addType, setAddType] = useState<'income' | 'expense'>('expense')
  const [addDate, setAddDate] = useState(new Date().toISOString().slice(0, 10))
  const [addMethod, setAddMethod] = useState('Cash')
  const [addCategory, setAddCategory] = useState<string | null>(null)
  const [addSaving, setAddSaving] = useState(false)

  const filtered = transactions.filter((t) => {
    const q = search.toLowerCase()
    const matchSearch =
      !q ||
      t.description.toLowerCase().includes(q) ||
      t.member.toLowerCase().includes(q) ||
      t.category.toLowerCase().includes(q)
    const matchType =
      typeFilter === 'All' ||
      (typeFilter === 'In' && t.type === 'income') ||
      (typeFilter === 'Out' && t.type === 'expense')
    const matchStatus = statusFilter === 'All' || t.status === statusFilter
    return matchSearch && matchType && matchStatus
  })
  const pg = usePagination(filtered, 25)

  const openEdit = (t: Transaction, e?: React.MouseEvent) => {
    e?.stopPropagation()
    setEditTarget(t)
    setEditStatus(t.status)
  }

  const handleEdit = async () => {
    if (!editTarget) return
    try {
      await updateTransaction(editTarget.id, {
        status: editStatus,
      })
      queryClient.invalidateQueries({ queryKey: qk.transactions.all })
      setEditTarget(null)
      notify(
        'success',
        t('finance.transaction.saved', 'Buchung gespeichert.'),
        t('finance.transaction.updatedMsg', 'Status auf «{{status}}» geändert.', {
          status: editStatus,
        }),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekannter Fehler'),
      )
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    try {
      await deleteTransaction(deleteTarget.id)
      queryClient.invalidateQueries({ queryKey: qk.transactions.all })
      notify(
        'info',
        t('finance.transaction.deleted', 'Buchung gelöscht.'),
        t('finance.transaction.deletedMsg', 'Die Buchung wurde gelöscht.'),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekannter Fehler'),
      )
    }
  }

  const goToInvoice = (invoiceId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    const inv = invoices.find((i) => i.id === invoiceId)
    if (inv) goInvoice(inv)
    else go('/app/finance/invoices')
  }

  const openAdd = () => {
    setAddDesc('')
    setAddAmount('')
    setAddType('expense')
    setAddDate(new Date().toISOString().slice(0, 10))
    setAddMethod('Cash')
    setAddCategory(categories.find((c) => c.isDefault)?.id ?? null)
    setAddOpen(true)
  }

  // The backend takes a positive amount; the type says whether it is in or out.
  const addAmountValue = Math.abs(Number(addAmount))
  const addValid =
    !!addDesc.trim() &&
    Number.isFinite(addAmountValue) &&
    addAmountValue > 0 &&
    !!addCategory

  const handleAdd = async () => {
    if (!addValid || !addCategory) return
    setAddSaving(true)
    try {
      await createTransaction({
        date: addDate,
        description: addDesc.trim(),
        categoryId: addCategory,
        amount: addAmountValue,
        method: addMethod,
        type: addType,
      })
      queryClient.invalidateQueries({ queryKey: qk.transactions.all })
      setAddOpen(false)
      notify(
        'success',
        t('finance.transaction.saved', 'Buchung gespeichert.'),
        t('finance.transaction.createdMsg', 'Buchung erfasst.'),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekannter Fehler'),
      )
    } finally {
      setAddSaving(false)
    }
  }

  const formatDate = (iso: string) => {
    if (!iso) return '—'
    try {
      return new Date(iso).toLocaleDateString('en-CH', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
      })
    } catch {
      return iso
    }
  }

  return (
    <div>
      {canCreate && (
        <Group justify="flex-end" mb={16} className="page-actions">
          <Button variant="filled" onClick={openAdd}>
            <IconPlus size={16} />
            {t('finance.addTransaction', 'Buchung erfassen')}
          </Button>
        </Group>
      )}
      {fetchError && (
        <ErrorBanner
          message={
            fetchError instanceof Error
              ? fetchError.message
              : t('finance.loadTransactionsFailed', 'Buchungen konnten nicht geladen werden')
          }
          onRetry={() => refetch()}
        />
      )}
      <DataTable
        breakpoint="xwide"
        columns={[
          {
            key: 'createdAt',
            header: t('finance.recorded', 'Erfasst'),
            render: (tx) => (
              <span
                className="num"
                style={{
                  color: '#8c86a0',
                  fontSize: 'var(--mantine-font-size-xs)',
                }}
              >
                {formatDate(tx.createdAt)}
              </span>
            ),
          },
          {
            key: 'date',
            header: t('common.date', 'Datum'),
            render: (tx) => (
              <span
                className="num"
                style={{
                  color: '#5e5873',
                  fontSize: 'var(--mantine-font-size-sm)',
                }}
              >
                {tx.date}
              </span>
            ),
          },
          {
            key: 'description',
            header: t('common.description', 'Beschreibung'),
            render: (tx) => (
              <div
                style={{
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  maxWidth: 200,
                }}
              >
                {tx.description}
              </div>
            ),
          },
          {
            key: 'category',
            header: t('finance.categoryLabel', 'Kategorie'),
            render: (tx) => <Badge variant="light">{tx.category}</Badge>,
          },
          {
            key: 'member',
            header: t('common.member', 'Mitglied'),
            render: (tx) => (
              <span style={{ color: '#5e5873' }}>{tx.member}</span>
            ),
          },
          {
            key: 'amount',
            header: t('finance.amount', 'Betrag'),
            render: (tx) => (
              <span
                className="num"
                style={{
                  fontWeight: 700,
                  color: tx.type === 'income' ? '#1f9d57' : '#ff4d3d',
                }}
              >
                {tx.type === 'income' ? '+' : '−'}CHF{' '}
                {formatCHF(Math.abs(tx.amount))}
              </span>
            ),
          },
          {
            key: 'method',
            header: t('common.method', 'Methode'),
            render: (tx) => (
              <span style={{ color: '#5e5873' }}>{tx.method}</span>
            ),
          },
          {
            key: 'status',
            header: t('common.status', 'Status'),
            render: (tx) => (
              <Badge
                variant="light"
                color={tx.status === 'Pending' ? 'yellow' : 'green'}
                radius="xl"
                style={{ fontSize: 'var(--mantine-font-size-xs)' }}
              >
                {tx.status}
              </Badge>
            ),
          },
          {
            key: 'actions',
            header: '',
            width: 100,
            render: (tx) => (
              <ActionButtons
                extra={
                  tx.invoiceId ? (
                    <ActionIcon
                      variant="subtle"
                      size="md"
                      onClick={(e) => goToInvoice(tx.invoiceId!, e)}
                      title={t('finance.viewInvoice', 'Rechnung ansehen')}
                    >
                      <IconExternalLink
                        size={18}
                        style={{ color: '#2596be' }}
                      />
                    </ActionIcon>
                  ) : undefined
                }
                onEdit={canUpdate ? () => openEdit(tx) : undefined}
                onDelete={canDelete ? () => setDeleteTarget(tx) : undefined}
              />
            ),
          },
        ]}
        data={pg.paged}
        loading={loading}
        emptyMessage={t('finance.noTransactions', 'Keine Buchungen gefunden.')}
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder={t(
          'finance.searchTransactions',
          'Buchungen suchen …',
        )}
        filters={['All', 'In', 'Out'].map((f) => ({
          label:
            f === 'All'
              ? t('common.all', 'Alle')
              : f === 'In'
                ? t('finance.in', 'Ein')
                : t('finance.out', 'Aus'),
          value: f.toLowerCase(),
          active: typeFilter === f,
          onClick: () => setTypeFilter(f),
        }))}
        page={pg.page}
        perPage={pg.perPage}
        total={pg.total}
        totalPages={pg.totalPages}
        onPageChange={pg.goPage}
        onPerPageChange={pg.setPerPage}
        getRowKey={(tx) => tx.id}
        toolbar={
          <Select
            size="sm"
            data={[
              { value: 'All', label: t('common.all', 'Alle') },
              { value: 'Pending', label: t('finance.pending', 'Offen') },
              {
                value: 'Completed',
                label: t('finance.completed', 'Abgeschlossen'),
              },
            ]}
            value={statusFilter}
            onChange={(v) => setStatusFilter(v ?? 'All')}
            style={{ width: 140 }}
          />
        }
      />

      <ConfirmModal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title={t('finance.deleteTransactionTitle', 'Buchung löschen?')}
        body={
          deleteTarget
            ? `"${deleteTarget.description}" (${
                deleteTarget.type === 'income' ? '+' : '−'
              }CHF ${Math.abs(deleteTarget.amount).toFixed(
                2,
              )}) wirde permanent entfernt.${
                deleteTarget.invoiceId
                  ? t(
                      'finance.linkedInvoiceAlsoDeleted',
                      'Die verknüpfte Rechnung wird ebenfalls gelöscht.',
                    )
                  : ''
              }`
            : ''
        }
        onConfirm={handleDelete}
      />

      {/* Edit status modal */}
      <Modal
        open={!!editTarget}
        onClose={() => setEditTarget(null)}
        title={t('finance.editTransaction', 'Buchung bearbeiten')}
        subtitle={editTarget?.description}
        footer={
          <>
            <Button variant="default" onClick={() => setEditTarget(null)}>
              {t('common.cancel')}
            </Button>
            <Button variant="filled" onClick={handleEdit}>
              {t('common.save')}
            </Button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Field label={t('common.status', 'Status')}>
            <Select
              data={[
                { value: 'Pending', label: t('finance.pending', 'Offen') },
                {
                  value: 'Completed',
                  label: t('finance.completed', 'Abgeschlossen'),
                },
              ]}
              value={editStatus}
              onChange={(v) =>
                setEditStatus((v ?? 'Pending') as 'Pending' | 'Completed')
              }
            />
          </Field>
          {editTarget && (
            <div
              style={{
                fontSize: 'var(--mantine-font-size-sm)',
                color: '#5e5873',
                background: '#f4f2f9',
                borderRadius: 8,
                padding: '10px 14px',
              }}
            >
              <div>
                {t('finance.amount', 'Betrag')}:{' '}
                <strong>CHF {formatCHF(Math.abs(editTarget.amount))}</strong>
              </div>
              <div>
                {t('common.date', 'Datum')}: <strong>{editTarget.date}</strong>
              </div>
              <div>
                {t('finance.recorded', 'Erfasst')}:{' '}
                <strong>{formatDate(editTarget.createdAt)}</strong>
              </div>
              {editTarget.invoiceId && (
                <div>
                  {t('finance.invoiceLabel', 'Rechnung')}:{' '}
                  <strong>#{editTarget.invoiceId}</strong>
                </div>
              )}
            </div>
          )}
        </div>
      </Modal>

      <Modal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title={t('finance.addTransaction', 'Buchung erfassen')}
        footer={
          <>
            <Button variant="default" onClick={() => setAddOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              variant="filled"
              onClick={handleAdd}
              disabled={addSaving || !addValid}
            >
              {addSaving ? t('common.saving', 'Wird gespeichert …') : t('common.save')}
            </Button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Field label={t('common.description', 'Beschreibung')}>
            <TextInput
              value={addDesc}
              onChange={(e) => setAddDesc(e.target.value)}
              placeholder={t(
                'finance.transactionDescription',
                'z. B. Spende Sommerfest',
              )}
            />
          </Field>
          <div style={{ display: 'flex', gap: 12 }}>
            <Field label={t('finance.amount', 'Betrag')}>
              <TextInput
                type="number"
                step="0.05"
                min="0"
                value={addAmount}
                onChange={(e) => setAddAmount(e.target.value)}
                placeholder="50.00"
              />
            </Field>
            <Field label={t('common.type', 'Typ')}>
              <Select
                data={[
                  { value: 'expense', label: t('finance.expense', 'Ausgabe') },
                  { value: 'income', label: t('finance.income', 'Einnahmen') },
                ]}
                value={addType}
                onChange={(v) =>
                  setAddType((v ?? 'expense') as 'income' | 'expense')
                }
              />
            </Field>
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
            <Field label={t('common.date', 'Datum')}>
              <TextInput
                type="date"
                value={addDate}
                onChange={(e) => setAddDate(e.target.value)}
              />
            </Field>
            <Field label={t('common.method', 'Methode')}>
              <Select
                data={[
                  { value: 'Cash', label: t('finance.methods.cash', 'Bar') },
                  { value: 'IBAN', label: t('finance.methods.bank', 'Bank') },
                  { value: 'Card', label: t('finance.methods.card', 'Karte') },
                  { value: 'Twint', label: 'TWINT' },
                ]}
                value={addMethod}
                onChange={(v) => setAddMethod(v ?? 'Cash')}
              />
            </Field>
          </div>
          <Field
            label={t('finance.categoryLabel', 'Kategorie')}
            hint={
              categories.length === 0
                ? t(
                    'finance.noCategoriesHint',
                    'Lege zuerst unter Finanzen → Kategorien eine Kategorie an.',
                  )
                : undefined
            }
          >
            <Select
              data={categories.map((c) => ({ value: c.id, label: c.name }))}
              value={addCategory}
              onChange={setAddCategory}
              placeholder={t('finance.selectCategory', 'Kategorie wählen …')}
              searchable
            />
          </Field>
        </div>
      </Modal>
    </div>
  )
}
