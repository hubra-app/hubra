import { useState } from 'react'
import {
  Button,
  NumberInput,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
} from '@mantine/core'
import { useT } from '@/locales/i18n'
import { Modal } from '@/components/ui'
import type { Transaction, TransactionCategory } from '@/types'
import type { TransactionCreate } from '@/api/finance'
import { formatDateTime } from '@/format'
import { PAYMENT_METHODS, methodLabel } from './transactionLabels'

export type TransactionFormValues = Required<
  Pick<TransactionCreate, 'date' | 'description' | 'amount' | 'method' | 'type'>
> & {
  categoryId: string
  payeeName: string
  status: 'Pending' | 'Completed'
}

function initialValues(
  tx: Transaction | null,
  categories: TransactionCategory[],
): TransactionFormValues {
  if (tx) {
    return {
      date: tx.date,
      description: tx.description,
      amount: Math.abs(tx.amount),
      method: tx.method,
      type: tx.type,
      categoryId: tx.categoryId ?? '',
      payeeName: tx.payeeName ?? '',
      status: tx.status,
    }
  }
  return {
    date: new Date().toISOString().slice(0, 10),
    description: '',
    amount: 0,
    method: 'Cash',
    type: 'expense',
    categoryId: categories.find((c) => c.isDefault)?.id ?? '',
    payeeName: '',
    status: 'Completed',
  }
}

/**
 * One form to record a transaction and to change it later. Mount it with a
 * `key` per transaction so it starts from that transaction's values.
 */
export function TransactionFormModal({
  open,
  transaction,
  categories,
  saving,
  onClose,
  onSubmit,
  onOpenCategories,
}: {
  open: boolean
  /** The transaction to change, or null to record a new one. */
  transaction: Transaction | null
  categories: TransactionCategory[]
  saving: boolean
  onClose: () => void
  onSubmit: (values: TransactionFormValues) => void
  onOpenCategories?: () => void
}) {
  const { t } = useT()
  const [values, setValues] = useState(() => initialValues(transaction, categories))
  const [touched, setTouched] = useState(false)
  const set = <K extends keyof TransactionFormValues>(key: K, value: TransactionFormValues[K]) =>
    setValues((v) => ({ ...v, [key]: value }))

  const errors = {
    description: !values.description.trim()
      ? t('finance.form.descriptionRequired', 'Beschreibe die Buchung kurz.')
      : null,
    amount:
      !Number.isFinite(values.amount) || values.amount <= 0
        ? t('finance.form.amountRequired', 'Gib einen Betrag über 0 ein.')
        : null,
    date: !values.date ? t('finance.form.dateRequired', 'Wähle ein Datum.') : null,
    categoryId: !values.categoryId
      ? t('finance.form.categoryRequired', 'Wähle eine Kategorie.')
      : null,
  }
  const valid = !Object.values(errors).some(Boolean)
  const show = (key: keyof typeof errors) => (touched ? errors[key] : null)

  const submit = () => {
    setTouched(true)
    if (valid && !saving) onSubmit({ ...values, description: values.description.trim() })
  }

  const editing = !!transaction
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={
        editing
          ? t('finance.editTransaction', 'Buchung bearbeiten')
          : t('finance.addTransaction', 'Buchung erfassen')
      }
      subtitle={
        editing && transaction.createdAt
          ? t('finance.recordedOn', 'Erfasst am {{date}}', {
              date: formatDateTime(transaction.createdAt),
            })
          : undefined
      }
      footer={
        <>
          <Button variant="default" onClick={onClose}>
            {t('common.cancel', 'Abbrechen')}
          </Button>
          <Button variant="filled" onClick={submit} loading={saving}>
            {editing
              ? t('common.saveChanges', 'Änderungen speichern')
              : t('finance.form.record', 'Buchung erfassen')}
          </Button>
        </>
      }
    >
      <Stack gap="md">
        <SegmentedControl
          fullWidth
          value={values.type}
          onChange={(v) => set('type', v as 'income' | 'expense')}
          data={[
            { value: 'expense', label: t('finance.form.expense', 'Ausgabe') },
            { value: 'income', label: t('finance.form.income', 'Einnahme') },
          ]}
          color={values.type === 'income' ? 'green' : 'red'}
        />
        <TextInput
          label={t('common.description', 'Beschreibung')}
          placeholder={t('finance.transactionDescription', 'z. B. Spende Sommerfest')}
          value={values.description}
          onChange={(e) => set('description', e.currentTarget.value)}
          error={show('description')}
          data-autofocus
        />
        <SimpleGrid cols={{ base: 1, xs: 2 }} spacing="sm">
          <NumberInput
            label={t('finance.amountChf', 'Betrag (CHF)')}
            value={values.amount || ''}
            onChange={(v) => set('amount', typeof v === 'number' ? v : Number(v) || 0)}
            min={0}
            step={5}
            decimalScale={2}
            decimalSeparator="."
            thousandSeparator="’"
            hideControls
            placeholder="50.00"
            error={show('amount')}
          />
          <TextInput
            type="date"
            label={t('common.date', 'Datum')}
            value={values.date}
            onChange={(e) => set('date', e.currentTarget.value)}
            error={show('date')}
          />
          <Select
            label={t('finance.categoryLabel', 'Kategorie')}
            data={categories.map((c) => ({ value: c.id, label: c.name }))}
            value={values.categoryId || null}
            onChange={(v) => set('categoryId', v ?? '')}
            placeholder={t('finance.selectCategory', 'Kategorie wählen …')}
            searchable
            error={show('categoryId')}
            nothingFoundMessage={t('finance.form.noCategory', 'Keine passende Kategorie')}
          />
          <Select
            label={t('finance.paymentMethod', 'Zahlungsart')}
            data={PAYMENT_METHODS.map((m) => ({ value: m, label: methodLabel(t, m) }))}
            value={values.method}
            onChange={(v) => set('method', v ?? 'Cash')}
            allowDeselect={false}
          />
        </SimpleGrid>
        {categories.length === 0 && (
          <Text size="sm" c="dimmed">
            {t(
              'finance.noCategoriesHint',
              'Lege zuerst unter Finanzen → Kategorien eine Kategorie an.',
            )}{' '}
            {onOpenCategories && (
              <Button variant="subtle" size="compact-sm" onClick={onOpenCategories}>
                {t('finance.form.openCategories', 'Zu den Kategorien')}
              </Button>
            )}
          </Text>
        )}
        <TextInput
          label={t('finance.form.payee', 'Von / an (optional)')}
          description={
            transaction?.memberName && !values.payeeName
              ? t('finance.form.linkedMember', 'Verknüpft mit {{name}}', {
                  name: transaction.memberName,
                })
              : undefined
          }
          placeholder={t('finance.form.payeePlaceholder', 'z. B. Baumarkt AG')}
          value={values.payeeName}
          onChange={(e) => set('payeeName', e.currentTarget.value)}
        />
        {editing && (
          <Select
            label={t('common.status', 'Status')}
            data={[
              { value: 'Completed', label: t('finance.completed', 'Abgeschlossen') },
              { value: 'Pending', label: t('finance.pending', 'Offen') },
            ]}
            value={values.status}
            onChange={(v) => set('status', (v ?? 'Completed') as 'Pending' | 'Completed')}
            allowDeselect={false}
          />
        )}
      </Stack>
    </Modal>
  )
}
