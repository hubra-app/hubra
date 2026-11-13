import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ActionIcon,
  Alert,
  Button,
  Group,
  NumberInput,
  Table,
  Text,
  TextInput,
} from '@mantine/core'
import { IconFileInvoice, IconPlus, IconTrash } from '@tabler/icons-react'
import { addOpenItem, billOpenItems, deleteOpenItem, listOpenItems } from '@/api/openItems'
import { MemberPicker } from '@/components/MemberPicker'
import { ErrorBanner, Field, Modal } from '@/components/ui'
import { useAuth, useToast } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { formatCHF, formatDate } from '@/format'
import { useT } from '@/locales/i18n'

/** Finanzen › Rechnungen › Offene Posten: what members owe that is not on an
 * invoice yet (drinks, booking fees, by hand), collected into one invoice
 * per member each month or quarter. */
export function OpenItemsTab() {
  const { t } = useT()
  const { notify } = useToast()
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const { data, error } = useQuery({
    queryKey: qk.openItems,
    queryFn: ({ signal }) => listOpenItems(signal),
  })
  const [adding, setAdding] = useState(false)
  const [memberId, setMemberId] = useState<string | null>(null)
  const [amount, setAmount] = useState<number | string>('')
  const [text, setText] = useState('')

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: qk.openItems })
    queryClient.invalidateQueries({ queryKey: qk.invoices.all })
  }
  const fail = (err: unknown) =>
    notify(
      'error',
      t('common.error'),
      err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
    )

  const add = useMutation({
    mutationFn: () => addOpenItem({ member_id: Number(memberId), amount: Number(amount), text }),
    onSuccess: () => {
      setAdding(false)
      setMemberId(null)
      setAmount('')
      setText('')
      refresh()
    },
    onError: fail,
  })
  const remove = useMutation({ mutationFn: deleteOpenItem, onSuccess: refresh, onError: fail })
  const bill = useMutation({
    mutationFn: billOpenItems,
    onSuccess: (out) => {
      refresh()
      notify(
        'success',
        t('openItems.billed', 'Abgerechnet'),
        t('openItems.billedMsg', '{{count}} Rechnungen erstellt.', { count: out.invoices.length }),
      )
    },
    onError: fail,
  })

  const items = data?.items ?? []
  const totals = new Map<string, number>()
  for (const i of items)
    totals.set(i.member_name ?? '?', (totals.get(i.member_name ?? '?') ?? 0) + i.amount)
  const cycleText = {
    off: t(
      'openItems.cycleOff',
      'Jeder Posten kommt sofort auf eine eigene Rechnung. Unter Einstellungen lassen sie sich sammeln.',
    ),
    monthly: t(
      'openItems.cycleMonthly',
      'Am 1. jedes Monats kommen die Posten jedes Mitglieds auf eine Rechnung.',
    ),
    quarterly: t(
      'openItems.cycleQuarterly',
      'Am 1. jedes Quartals kommen die Posten jedes Mitglieds auf eine Rechnung.',
    ),
  }[data?.cycle ?? 'off']

  return (
    <div>
      {error && <ErrorBanner message={error.message} />}
      <Alert variant="light" mb="md">
        {cycleText}
        {data && data.cycle !== 'off' && data.min_amount > 0 && (
          <>
            {' '}
            {t('openItems.minimum', 'Unter {{amount}} warten sie auf das nächste Mal.', {
              amount: `CHF ${formatCHF(data.min_amount)}`,
            })}
          </>
        )}
      </Alert>
      <Group justify="flex-end" mb="sm">
        {hasPermission('finance.invoices.create') && (
          <Button
            variant="default"
            leftSection={<IconPlus size={16} />}
            onClick={() => setAdding(true)}
          >
            {t('openItems.add', 'Posten erfassen')}
          </Button>
        )}
        {hasPermission('finance.invoices.bulk_create') && (
          <Button
            leftSection={<IconFileInvoice size={16} />}
            disabled={items.length === 0}
            loading={bill.isPending}
            onClick={() => bill.mutate()}
            data-testid="bill-open-items"
          >
            {t('openItems.billNow', 'Jetzt abrechnen')}
          </Button>
        )}
      </Group>
      {data && items.length === 0 ? (
        <Text c="dimmed" size="sm">
          {t('openItems.empty', 'Keine offenen Posten.')}
        </Text>
      ) : (
        <Table striped data-testid="open-items">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{t('common.member')}</Table.Th>
              <Table.Th>{t('openItems.day', 'Datum')}</Table.Th>
              <Table.Th>{t('openItems.text', 'Posten')}</Table.Th>
              <Table.Th>{t('openItems.source', 'Von')}</Table.Th>
              <Table.Th style={{ textAlign: 'right' }}>{t('openItems.amount', 'Betrag')}</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {items.map((i) => (
              <Table.Tr key={i.id}>
                <Table.Td>{i.member_name}</Table.Td>
                <Table.Td>{formatDate(i.day)}</Table.Td>
                <Table.Td>{i.text}</Table.Td>
                <Table.Td>{t(`modules.${i.source}.name`, i.source)}</Table.Td>
                <Table.Td style={{ textAlign: 'right' }}>CHF {formatCHF(i.amount)}</Table.Td>
                <Table.Td>
                  {hasPermission('finance.invoices.delete') && (
                    <ActionIcon
                      variant="subtle"
                      color="red"
                      aria-label={t('common.delete', 'Löschen')}
                      onClick={() => remove.mutate(i.id)}
                    >
                      <IconTrash size={16} />
                    </ActionIcon>
                  )}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
          {totals.size > 0 && (
            <Table.Tfoot>
              {[...totals].map(([name, total]) => (
                <Table.Tr key={name}>
                  <Table.Td colSpan={4}>
                    <Text size="sm" fw={600}>
                      {t('openItems.totalFor', 'Total {{name}}', { name })}
                    </Text>
                  </Table.Td>
                  <Table.Td style={{ textAlign: 'right' }}>
                    <Text size="sm" fw={600}>
                      CHF {formatCHF(total)}
                    </Text>
                  </Table.Td>
                  <Table.Td />
                </Table.Tr>
              ))}
            </Table.Tfoot>
          )}
        </Table>
      )}
      <Modal
        onSubmit={(e) => {
          e?.preventDefault()
          add.mutate()
        }}
        open={adding}
        onClose={() => setAdding(false)}
        title={t('openItems.add', 'Posten erfassen')}
        footer={
          <>
            <Button variant="default" onClick={() => setAdding(false)}>
              {t('common.cancel', 'Abbrechen')}
            </Button>
            <Button
              type="submit"
              loading={add.isPending}
              disabled={!memberId || !text.trim() || !Number(amount)}
            >
              {t('common.save', 'Speichern')}
            </Button>
          </>
        }
      >
        <Field label={t('common.member')}>
          <MemberPicker value={memberId} onChange={(id) => setMemberId(id)} />
        </Field>
        <Field label={t('openItems.text', 'Posten')}>
          <TextInput
            value={text}
            maxLength={200}
            onChange={(e) => setText(e.currentTarget.value)}
          />
        </Field>
        <Field
          label={t('openItems.amount', 'Betrag')}
          hint={t('openItems.amountHint', 'Negativ für eine Gutschrift.')}
        >
          <NumberInput value={amount} onChange={setAmount} decimalScale={2} prefix="CHF " />
        </Field>
      </Modal>
    </div>
  )
}
