import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { TextInput, Button, Group, Badge, Select, ActionIcon } from '@mantine/core'
import { useT } from '@/locales/i18n'
import { IconExternalLink, IconPlus } from '@tabler/icons-react'
import { useToast, useNav, useData, useAuth } from '@/context/AppContext'
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
} from '@/api/finance'
import { formatCHF } from '@/format'

/* ── Transactions ────────────────────────────── */
export function TransactionsTab() {
  const { notify } = useToast()
  const { go, goInvoice } = useNav()
  const { invoices } = useData()
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
    queryKey: ['transactions'],
    queryFn: () => listTransactions(),
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
  const [addMethod, setAddMethod] = useState('cash')
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
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      setEditTarget(null)
      notify(
        'success',
        t('finance.transaction.saved', 'Transaktion gspeichert.'),
        t(
          'finance.transaction.updatedMsg',
          `Status zue ${editStatus} gändert.`,
        ),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekanni Fehler'),
      )
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    try {
      await deleteTransaction(deleteTarget.id)
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      notify(
        'info',
        t('finance.transaction.deleted', 'Transaktion glöscht.'),
        t('finance.transaction.deletedMsg', 'Datensatz entfernt.'),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekanni Fehler'),
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
    setAddMethod('cash')
    setAddOpen(true)
  }

  const handleAdd = async () => {
    if (!addDesc.trim() || !addAmount.trim()) return
    setAddSaving(true)
    try {
      await createTransaction({
        date: addDate,
        description: addDesc.trim(),
        amount:
          addType === 'expense'
            ? -Math.abs(Number(addAmount))
            : Math.abs(Number(addAmount)),
        method: addMethod,
        type: addType,
      })
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      setAddOpen(false)
      notify(
        'success',
        t('finance.transaction.saved', 'Transaktion erfasse'),
        t('finance.transaction.createdMsg', 'Transaktion erstellt.'),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekanni Fehler'),
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
        <Group justify="flex-end" mb={16}>
          <Button variant="filled" onClick={openAdd}>
            <IconPlus size={16} />
            {t('finance.addTransaction', 'Transaktion erfasse')}
          </Button>
        </Group>
      )}
      {fetchError && (
        <ErrorBanner
          message={
            fetchError instanceof Error
              ? fetchError.message
              : 'Failed to load transactions'
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
            header: t('common.description', 'Beschribig'),
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
            header: t('finance.category', 'Kategorie'),
            render: (tx) => <Badge variant="light">{tx.category}</Badge>,
          },
          {
            key: 'member',
            header: t('common.member', 'Mitglid'),
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
                      title={t('finance.viewInvoice', 'Rächnig ahluege')}
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
        emptyMessage={t('finance.noTransactions', 'Cheni Transaktione.')}
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder={t(
          'finance.searchTransactions',
          'Transaktione sueche…',
        )}
        filters={['All', 'In', 'Out'].map((f) => ({
          label:
            f === 'All'
              ? t('common.all', 'Alli')
              : f === 'In'
                ? t('finance.in', 'I')
                : t('finance.out', 'Us'),
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
              { value: 'All', label: t('common.all', 'Alli') },
              { value: 'Pending', label: t('finance.pending', 'Uständig') },
              {
                value: 'Completed',
                label: t('finance.completed', 'Abgschlosse'),
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
        title={t('finance.deleteTransactionTitle', 'Transaktion lösche?')}
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
                      ' Di verlinkti Rächnig wird au glöscht.',
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
        title={t('finance.editTransaction', 'Transaktion bearbeite')}
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
                { value: 'Pending', label: t('finance.pending', 'Uständig') },
                {
                  value: 'Completed',
                  label: t('finance.completed', 'Abgschlosse'),
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
                  {t('finance.invoice', 'Rächnig')}:{' '}
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
        title={t('finance.addTransaction', 'Transaktion erfasse')}
        footer={
          <>
            <Button variant="default" onClick={() => setAddOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              variant="filled"
              onClick={handleAdd}
              disabled={addSaving || !addDesc.trim() || !addAmount.trim()}
            >
              {addSaving ? t('common.saving', 'Speichere…') : t('common.save')}
            </Button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Field label={t('common.description', 'Beschribig')}>
            <TextInput
              value={addDesc}
              onChange={(e) => setAddDesc(e.target.value)}
              placeholder={t(
                'finance.transactionDescription',
                'z.B. Härzblutere Iizahlig',
              )}
            />
          </Field>
          <div style={{ display: 'flex', gap: 12 }}>
            <Field label={t('finance.amount', 'Betrag (CHF)')}>
              <TextInput
                type="number"
                step="0.05"
                value={addAmount}
                onChange={(e) => setAddAmount(e.target.value)}
                placeholder="50.00"
              />
            </Field>
            <Field label={t('common.type', 'Typ')}>
              <Select
                data={[
                  { value: 'expense', label: t('finance.expense', 'Usgab') },
                  { value: 'income', label: t('finance.income', 'Iiname') },
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
                  { value: 'cash', label: 'Cash' },
                  { value: 'bank', label: 'Bank' },
                  { value: 'card', label: 'Card' },
                  { value: 'twint', label: 'TWINT' },
                  { value: 'other', label: 'Other' },
                ]}
                value={addMethod}
                onChange={(v) => setAddMethod(v ?? 'cash')}
              />
            </Field>
          </div>
        </div>
      </Modal>
    </div>
  )
}
