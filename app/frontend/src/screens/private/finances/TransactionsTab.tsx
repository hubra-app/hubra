import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Group, Badge, Select, ActionIcon, Text } from '@mantine/core'
import { useT } from '@/locales/i18n'
import { IconExternalLink, IconPlus } from '@tabler/icons-react'
import { useToast, useNav, useAuth } from '@/context/AppContext'
import { useInvoices } from '@/data/lists'
import {
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
import { formatCHF, formatDate } from '@/format'
import { TransactionFormModal, type TransactionFormValues } from './TransactionFormModal'
import { methodLabel, statusLabel } from './transactionLabels'
import { qk } from '@/data/keys'

/* ── Transactions ────────────────────────────── */
export function TransactionsTab() {
  const { notify } = useToast()
  const { go, goInvoice } = useNav()
  const { invoices } = useInvoices()
  const { hasPermission } = useAuth()
  const { t } = useT()
  const queryClient = useQueryClient()
  const canCreate = hasPermission('finance.transactions.create')
  const canUpdate = hasPermission('finance.transactions.update')
  const canDelete = hasPermission('finance.transactions.delete')
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
    enabled: canCreate || canUpdate,
  })
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('All')
  const [statusFilter, setStatusFilter] = useState('All')
  const [deleteTarget, setDeleteTarget] = useState<Transaction | null>(null)
  // The form: closed (null), a new transaction ('new') or one to change.
  const [formTarget, setFormTarget] = useState<Transaction | 'new' | null>(null)
  const [saving, setSaving] = useState(false)

  // ?tx=<id> (e.g. from the finance overview) opens that transaction, or
  // finds it in the list for people who can't edit.
  const [params, setParams] = useSearchParams()
  const linkedId = params.get('tx')
  const [handledLink, setHandledLink] = useState<string | null>(null)
  if (linkedId && linkedId !== handledLink && !loading) {
    setHandledLink(linkedId)
    const tx = transactions.find((x) => x.id === linkedId)
    if (tx && canUpdate) setFormTarget(tx)
    else if (tx) setSearch(tx.description)
  }
  const closeForm = () => {
    setFormTarget(null)
    if (linkedId) {
      setParams(
        (p) => {
          p.delete('tx')
          return p
        },
        { replace: true },
      )
    }
  }

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

  const openEdit = (tx: Transaction, e?: React.MouseEvent) => {
    e?.stopPropagation()
    setFormTarget(tx)
  }

  const handleSave = async (values: TransactionFormValues) => {
    if (!formTarget) return
    setSaving(true)
    try {
      if (formTarget === 'new') {
        await createTransaction({
          date: values.date,
          description: values.description,
          categoryId: values.categoryId,
          amount: values.amount,
          method: values.method,
          type: values.type,
          payeeName: values.payeeName.trim() || undefined,
        })
      } else {
        const before = formTarget
        await updateTransaction(before.id, {
          date: values.date,
          description: values.description,
          categoryId: values.categoryId,
          amount: values.amount,
          method: values.method,
          type: values.type,
          status: values.status,
          // Only send the name when it changed: an empty one would unlink nothing
          // but blank out a name the bank import set.
          ...(values.payeeName.trim() !== (before.payeeName ?? '')
            ? { payeeName: values.payeeName.trim() }
            : {}),
        })
      }
      queryClient.invalidateQueries({ queryKey: qk.transactions.all })
      notify(
        'success',
        t('finance.transaction.saved', 'Buchung gespeichert.'),
        formTarget === 'new'
          ? t('finance.transaction.createdMsg', 'Buchung erfasst.')
          : t('finance.transaction.updatedMsg2', '«{{description}}» wurde gespeichert.', {
              description: values.description,
            }),
      )
      closeForm()
    } catch (err: unknown) {
      notify(
        'error',
        t('finance.transaction.saveFailed', 'Buchung nicht gespeichert'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekannter Fehler'),
      )
    } finally {
      setSaving(false)
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

  const isFiltered = !!search || typeFilter !== 'All' || statusFilter !== 'All'

  return (
    <div>
      {canCreate && (
        <Group justify="flex-end" mb={16} className="page-actions">
          <Button
            variant="filled"
            leftSection={<IconPlus size={16} />}
            onClick={() => setFormTarget('new')}
          >
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
            key: 'date',
            header: t('common.date', 'Datum'),
            render: (tx) => (
              <span
                className="num"
                style={{
                  color: 'var(--hb-text-2)',
                  fontSize: 'var(--mantine-font-size-sm)',
                  whiteSpace: 'nowrap',
                }}
              >
                {tx.date ? formatDate(tx.date) : '—'}
              </span>
            ),
          },
          {
            key: 'description',
            header: t('common.description', 'Beschreibung'),
            render: (tx) => (
              <div style={{ minWidth: 0, maxWidth: 280 }}>
                <Text size="sm" fw={600} truncate="end">
                  {tx.description}
                </Text>
                {tx.member && tx.member !== '—' && (
                  <Text size="xs" c="dimmed" truncate="end">
                    {tx.member}
                  </Text>
                )}
              </div>
            ),
          },
          {
            key: 'category',
            header: t('finance.categoryLabel', 'Kategorie'),
            render: (tx) => (
              <Badge variant="light" style={{ textTransform: 'none', maxWidth: 180 }}>
                {tx.category || '—'}
              </Badge>
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
                  whiteSpace: 'nowrap',
                  color: tx.type === 'income' ? '#1f9d57' : '#ff4d3d',
                }}
              >
                {tx.type === 'income' ? '+' : '−'}CHF{'\u00a0'}
                {formatCHF(Math.abs(tx.amount))}
              </span>
            ),
          },
          {
            key: 'method',
            header: t('finance.paymentMethod', 'Zahlungsart'),
            render: (tx) => (
              <span style={{ color: 'var(--hb-text-2)', whiteSpace: 'nowrap' }}>
                {methodLabel(t, tx.method)}
              </span>
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
                style={{ fontSize: 'var(--mantine-font-size-xs)', textTransform: 'none', overflow: 'visible' }}
              >
                {statusLabel(t, tx.status)}
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
        emptyMessage={
          isFiltered
            ? t('finance.noTransactions', 'Keine Buchungen gefunden.')
            : t('finance.noTransactionsYet', 'Noch keine Buchungen')
        }
        emptyDescription={
          isFiltered
            ? t('finance.noTransactionsFilterHint', 'Ändere die Suche oder die Filter.')
            : t(
                'finance.noTransactionsYetHint',
                'Hier erscheinen Einnahmen und Ausgaben des Vereins, auch bezahlte Rechnungen.',
              )
        }
        emptyAction={
          !isFiltered && canCreate
            ? { label: t('finance.addFirstTransaction', 'Erste Buchung erfassen'), onClick: () => setFormTarget('new') }
            : undefined
        }
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
            aria-label={t('common.status', 'Status')}
            data={[
              { value: 'All', label: t('finance.allStatuses', 'Alle Status') },
              { value: 'Pending', label: t('finance.pending', 'Offen') },
              {
                value: 'Completed',
                label: t('finance.completed', 'Abgeschlossen'),
              },
            ]}
            value={statusFilter}
            onChange={(v) => setStatusFilter(v ?? 'All')}
            allowDeselect={false}
            style={{ width: 160 }}
          />
        }
      />

      <ConfirmModal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title={t('finance.deleteTransactionTitle', 'Buchung löschen?')}
        body={
          deleteTarget
            ? t('finance.deleteTransactionBody', '«{{description}}» ({{amount}}) wird endgültig gelöscht.', {
                description: deleteTarget.description,
                amount: `${deleteTarget.type === 'income' ? '+' : '−'}CHF ${formatCHF(Math.abs(deleteTarget.amount))}`,
                interpolation: { escapeValue: false },
              }) +
              (deleteTarget.invoiceId
                ? ' ' +
                  t(
                    'finance.linkedInvoiceAlsoDeleted',
                    'Die verknüpfte Rechnung wird ebenfalls gelöscht.',
                  )
                : '')
            : ''
        }
        onConfirm={handleDelete}
      />

      {formTarget && (
        <TransactionFormModal
          key={formTarget === 'new' ? 'new' : formTarget.id}
          open
          transaction={formTarget === 'new' ? null : formTarget}
          categories={categories}
          saving={saving}
          onClose={closeForm}
          onSubmit={handleSave}
          onOpenCategories={() => {
            setFormTarget(null)
            go('/app/finance/categories')
          }}
        />
      )}
    </div>
  )
}
