import { useState } from 'react'
import { Anchor, Badge, Button, Paper } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import {
  IconArrowDownLeft,
  IconArrowUpRight,
  IconCheck,
  IconFileInvoice,
  IconPencil,
  IconReceipt,
  IconTrash,
  IconUser,
} from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useAuth, useNav, useToast } from '@/context/AppContext'
import { formatCHF, formatDate, formatDateTime } from '@/format'
import {
  deleteTransaction,
  getTransaction,
  listTxCategories,
  updateTransaction,
} from '@/api/finance'
import { qk } from '@/data/keys'
import { ConfirmModal, LoadingSpinner } from '@/components/ui'
import {
  DetailBack,
  DetailEmpty,
  DetailFact,
  DetailHeader,
  DetailIcon,
  DetailNotFound,
  DetailRow,
  DetailSection,
  RecordActivity,
} from '@/components/detail'
import { TransactionFormModal, type TransactionFormValues } from './TransactionFormModal'
import { methodLabel, statusLabel } from './transactionLabels'
import { transactionUpdate } from './transactionSave'

/* ── One transaction, as its own page ─────────── */
export function TransactionDetailScreen() {
  const { t } = useT()
  const { id } = useParams<{ id: string }>()
  const { go } = useNav()
  const { notify } = useToast()
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const canUpdate = hasPermission('finance.transactions.update')
  const canDelete = hasPermission('finance.transactions.delete')
  const canAudit = hasPermission('audit.audit.read')
  const [editOpen, setEditOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [saving, setSaving] = useState(false)

  const { data: tx, isLoading, error } = useQuery({
    queryKey: qk.transactions.one(id),
    queryFn: () => getTransaction(id!),
    enabled: !!id,
  })
  const { data: categories = [] } = useQuery({
    queryKey: qk.transactions.categories,
    queryFn: () => listTxCategories(),
    enabled: canUpdate,
  })

  const back = '/app/finance/transactions'
  const backLabel = t('finance.backToTransactions', 'Zurück zu den Buchungen')
  if (isLoading) return <LoadingSpinner message={t('common.loading', 'Wird geladen …')} />
  if (error || !tx) {
    return (
      <DetailNotFound
        back={back}
        backLabel={backLabel}
        message={t('finance.transactionNotFound', 'Diese Buchung gibt es nicht (mehr).')}
      />
    )
  }

  const income = tx.type === 'income'
  const amount = `${income ? '+' : '−'}CHF\u00a0${formatCHF(Math.abs(tx.amount))}`
  const refresh = () => queryClient.invalidateQueries({ queryKey: qk.transactions.all })
  const fail = (err: unknown) =>
    notify(
      'error',
      t('finance.transaction.saveFailed', 'Buchung nicht gespeichert'),
      err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
    )

  const save = async (values: TransactionFormValues) => {
    setSaving(true)
    try {
      await updateTransaction(tx.id, transactionUpdate(tx, values))
      await refresh()
      notify(
        'success',
        t('finance.transaction.saved', 'Buchung gespeichert.'),
        t('finance.transaction.updatedMsg2', '«{{description}}» wurde gespeichert.', {
          description: values.description,
        }),
      )
      setEditOpen(false)
    } catch (err) {
      fail(err)
    } finally {
      setSaving(false)
    }
  }

  const markCompleted = async () => {
    try {
      await updateTransaction(tx.id, { status: 'Completed' })
      await refresh()
      notify('success', t('finance.transaction.saved', 'Buchung gespeichert.'))
    } catch (err) {
      fail(err)
    }
  }

  const remove = async () => {
    try {
      await deleteTransaction(tx.id)
      queryClient.removeQueries({ queryKey: qk.transactions.one(tx.id) })
      refresh()
      notify(
        'info',
        t('finance.transaction.deleted', 'Buchung gelöscht.'),
        t('finance.transaction.deletedMsg', 'Die Buchung wurde gelöscht.'),
      )
      go(back)
    } catch (err) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    }
  }

  const who = tx.payeeName || tx.memberName

  return (
    <div>
      <DetailBack to={back} label={backLabel} />
      <DetailHeader
        media={
          <DetailIcon
            color={income ? 'var(--mantine-color-green-filled)' : 'var(--mantine-color-red-filled)'}
          >
            {income ? <IconArrowDownLeft size={30} /> : <IconArrowUpRight size={30} />}
          </DetailIcon>
        }
        title={tx.description}
        chip={t('finance.transactionNo', 'Buchung {{id}}', { id: tx.id })}
        badges={
          <>
            <Badge variant="light" color={income ? 'green' : 'red'} style={{ textTransform: 'none' }}>
              {income ? t('finance.income', 'Einnahme') : t('finance.expense', 'Ausgabe')}
            </Badge>
            <Badge
              variant="light"
              color={tx.status === 'Pending' ? 'orange' : 'green'}
              radius="xl"
              style={{ textTransform: 'none' }}
            >
              {statusLabel(t, tx.status)}
            </Badge>
            {tx.category && (
              <Badge variant="light" style={{ textTransform: 'none' }}>
                {tx.category}
              </Badge>
            )}
          </>
        }
        actions={
          <>
            {tx.invoiceId && (
              <Button
                variant="default"
                leftSection={<IconFileInvoice size={16} />}
                onClick={() => go(`/app/finance/invoices/${tx.invoiceId}`)}
              >
                {t('finance.viewInvoice', 'Rechnung ansehen')}
              </Button>
            )}
            {canUpdate && tx.status === 'Pending' && (
              <Button variant="default" leftSection={<IconCheck size={16} />} onClick={markCompleted}>
                {t('finance.markCompleted', 'Als abgeschlossen markieren')}
              </Button>
            )}
            {canUpdate && (
              <Button
                variant="default"
                leftSection={<IconPencil size={16} />}
                onClick={() => setEditOpen(true)}
              >
                {t('common.edit')}
              </Button>
            )}
            {canDelete && (
              <Button
                variant="default"
                leftSection={<IconTrash size={16} />}
                style={{ color: 'var(--mantine-color-red-text)' }}
                onClick={() => setDeleteOpen(true)}
              >
                {t('common.delete', 'Löschen')}
              </Button>
            )}
          </>
        }
        facts={
          <>
            <DetailFact label={t('finance.amount', 'Betrag')}>
              <span
                className="num"
                data-testid="transaction-amount"
                style={{ color: income ? 'var(--mantine-color-green-text)' : 'var(--mantine-color-red-text)' }}
              >
                {amount}
              </span>
            </DetailFact>
            <DetailFact label={t('common.date', 'Datum')}>
              <span className="num">{tx.date ? formatDate(tx.date) : '—'}</span>
            </DetailFact>
            <DetailFact label={t('finance.paymentMethod', 'Zahlungsart')}>
              {methodLabel(t, tx.method)}
            </DetailFact>
          </>
        }
      />

      <div className={canAudit ? 'detail-grid' : undefined}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <DetailSection icon={<IconReceipt size={16} />} title={t('finance.transaction.details', 'Buchung')}>
            <DetailRow label={t('common.date', 'Datum')} mono>
              {tx.date ? formatDate(tx.date) : <DetailEmpty />}
            </DetailRow>
            <DetailRow label={t('finance.categoryLabel', 'Kategorie')}>
              {tx.category || <DetailEmpty />}
            </DetailRow>
            <DetailRow label={t('finance.paymentMethod', 'Zahlungsart')}>
              {methodLabel(t, tx.method)}
            </DetailRow>
            <DetailRow label={t('common.status', 'Status')}>{statusLabel(t, tx.status)}</DetailRow>
            <DetailRow label={t('finance.invoiceLabel', 'Rechnung')}>
              {tx.invoiceId ? (
                <Anchor size="sm" onClick={() => go(`/app/finance/invoices/${tx.invoiceId}`)}>
                  {t('members.detail.invoiceNo', 'Rechnung {{id}}', { id: tx.invoiceId })}
                </Anchor>
              ) : (
                <DetailEmpty />
              )}
            </DetailRow>
            {tx.createdAt && (
              <DetailRow label={t('finance.transaction.recorded', 'Erfasst')} mono>
                {formatDateTime(tx.createdAt)}
              </DetailRow>
            )}
          </DetailSection>

          <DetailSection
            icon={<IconUser size={16} />}
            title={income ? t('finance.transaction.from', 'Von') : t('finance.transaction.to', 'An')}
          >
            <DetailRow label={t('common.name', 'Name')}>
              {tx.memberId && tx.memberName ? (
                <Anchor size="sm" onClick={() => go(`/app/members/${tx.memberId}`)}>
                  {who}
                </Anchor>
              ) : (
                who || <DetailEmpty />
              )}
            </DetailRow>
          </DetailSection>
        </div>

        {canAudit && (
          <Paper withBorder p={{ base: 16, sm: 20 }}>
            <div
              style={{
                fontSize: 'var(--mantine-font-size-sm)',
                fontWeight: 600,
                color: 'var(--hb-text-2)',
                marginBottom: 8,
              }}
            >
              {t('members.detail.activity')}
            </div>
            <RecordActivity type="Transaction" id={tx.id} testId="transaction-activity" />
          </Paper>
        )}
      </div>

      {editOpen && (
        <TransactionFormModal
          key={tx.id}
          open
          transaction={tx}
          categories={categories}
          saving={saving}
          onClose={() => setEditOpen(false)}
          onSubmit={save}
          onOpenCategories={() => go('/app/finance/categories')}
        />
      )}
      <ConfirmModal
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        title={t('finance.deleteTransactionTitle', 'Buchung löschen?')}
        body={
          t('finance.deleteTransactionBody', '«{{description}}» ({{amount}}) wird endgültig gelöscht.', {
            description: tx.description,
            amount: amount.replace('\u00a0', ' '),
            interpolation: { escapeValue: false },
          }) +
          (tx.invoiceId
            ? ' ' + t('finance.linkedInvoiceAlsoDeleted', 'Die verknüpfte Rechnung wird ebenfalls gelöscht.')
            : '')
        }
        onConfirm={remove}
      />
    </div>
  )
}
