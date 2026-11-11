import { useEffect } from 'react'
import { Button, NumberInput, SimpleGrid, TextInput } from '@mantine/core'
import { DateField } from '@hubra/ui'
import { useForm } from '@mantine/form'
import { zod4Resolver } from 'mantine-form-zod-resolver'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import { Field, Modal } from '@/components/ui'
import { useNav, useToast } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { updateInvoice } from '@/api/finance'
import { useT, zmsg } from '@/locales/i18n'
import type { Invoice } from '@/types'

const schema = z
  .object({
    amount: z.number({ ...zmsg('finance.validation.amountRequired', 'Bitte gib einen Betrag ein') }).positive(
      zmsg('finance.validation.amountPositive', 'Der Betrag muss grösser als 0 sein'),
    ),
    due: z.string().min(1, zmsg('validation.dueRequired', 'Fälligkeitsdatum ist erforderlich')),
    issued: z.string(),
    description: z.string(),
  })
  .refine((v) => !v.issued || v.due >= v.issued, {
    path: ['due'],
    ...zmsg('finance.validation.dueBeforeIssued', 'Fällig liegt vor dem Rechnungsdatum'),
  })
type EditForm = z.infer<typeof schema>

/**
 * Change an open invoice: amount, due date and text. A paid invoice is
 * settled and has no edit; recipient and purpose stay as billed.
 */
export function EditInvoiceModal({
  invoice,
  onClose,
}: {
  invoice: Invoice | null
  onClose: () => void
}) {
  const { t } = useT()
  const { notify } = useToast()
  const { setSelectedInvoice } = useNav()
  const queryClient = useQueryClient()
  const form = useForm<EditForm>({
    validate: zod4Resolver(schema),
    initialValues: { amount: 0, due: '', issued: '', description: '' },
  })
  const { setValues, resetDirty } = form
  useEffect(() => {
    if (!invoice) return
    setValues({
      amount: invoice.amount,
      due: invoice.due.slice(0, 10),
      issued: invoice.issued.slice(0, 10),
      description: invoice.description ?? '',
    })
    resetDirty()
    // Only when another invoice is opened.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [invoice?.id])

  const save = useMutation({
    mutationFn: (v: EditForm) =>
      updateInvoice(invoice!.id, {
        amount: v.amount,
        due: v.due,
        description: v.description.trim() || null,
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData<Invoice[]>(qk.invoices.all, (old) =>
        old?.map((inv) => (inv.id === updated.id ? updated : inv)),
      )
      queryClient.setQueryData(qk.invoices.one(updated.id), updated)
      setSelectedInvoice((prev) => (prev?.id === updated.id ? updated : prev))
      void queryClient.invalidateQueries({ queryKey: qk.dashboard })
      notify(
        'success',
        t('finance.invoiceSaved', 'Rechnung gespeichert'),
        t('finance.invoiceSavedMsg', 'Rechnung {{id}} wurde geändert.', { id: updated.id }),
      )
      onClose()
    },
    onError: (err) =>
      notify(
        'error',
        t('common.error', 'Fehler'),
        err instanceof Error
          ? err.message
          : t('finance.invoiceUpdateFailed', 'Die Rechnung konnte nicht aktualisiert werden.'),
      ),
  })

  return (
    <Modal
      open={!!invoice}
      onClose={onClose}
      title={t('finance.editInvoice', 'Rechnung bearbeiten')}
      subtitle={invoice ? `${t('finance.invoice.no', 'Nr. {{n}}', { n: invoice.id })} · ${invoice.recipientName || invoice.member}` : undefined}
      onSubmit={form.onSubmit((v) => save.mutate(v))}
      footer={
        <>
          <Button variant="default" onClick={onClose}>
            {t('common.cancel', 'Abbrechen')}
          </Button>
          <Button type="submit" loading={save.isPending}>
            {t('common.save', 'Speichern')}
          </Button>
        </>
      }
    >
      <Field label={t('common.description', 'Beschreibung')}>
        <TextInput
          placeholder={t('common.descriptionPlaceholder', 'Kurze Beschreibung …')}
          {...form.getInputProps('description')}
        />
      </Field>
      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing={12}>
        <Field label={t('finance.amount', 'Betrag') + ' (CHF)'}>
          <NumberInput
            min={0}
            decimalScale={2}
            thousandSeparator="’"
            hideControls
            {...form.getInputProps('amount')}
          />
        </Field>
        <Field label={t('finance.invoice.due', 'Fällig')}>
          <DateField min={form.values.issued || undefined} {...form.getInputProps('due')} />
        </Field>
      </SimpleGrid>
    </Modal>
  )
}
