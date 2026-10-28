import { useQuery } from '@tanstack/react-query'
import { Table, Paper, Group, Text, Button } from '@mantine/core'
import { useT } from '@/locales/i18n'
import { useParams } from 'react-router-dom'
import {
  IconArrowLeft,
  IconBell,
  IconCheck,
  IconExternalLink,
  IconFileDownload,
} from '@tabler/icons-react'
import { useNav, useData } from '@/context/AppContext'
import { PageHead, InvoicePill } from '@/components/ui'
import { getInvoice, downloadInvoicePdf } from '@/api/finance'
import { formatCHF } from '@/format'
import {
  useMarkInvoicePaid,
  useSendInvoiceReminder,
} from '@/screens/private/finances/useInvoiceActions'

/* -- Invoice Detail ---------------------------- */
export function InvoiceDetailScreen() {
  const { t } = useT()
  const { id } = useParams<{ id: string }>()
  const { go, selectedInvoice } = useNav()
  const { invoices } = useData()
  const markPaidMutation = useMarkInvoicePaid()
  const sendReminderMutation = useSendInvoiceReminder()
  const { data: fetchedInvoice } = useQuery({
    queryKey: ['invoice', id],
    queryFn: () => getInvoice(id!),
    enabled: !!id,
  })

  const inv =
    invoices.find((i) => i.id === selectedInvoice?.id) ??
    selectedInvoice ??
    fetchedInvoice
  if (!inv) {
    return (
      <div>
        <PageHead
          eyebrow={t('finance.title', 'Finanze')}
          title={t('finance.invoice.notFound', 'R?chnig n?d gfunde')}
          actions={
            <Button
              variant="subtle"
              onClick={() => go('/app/finance/invoices')}
            >
              <IconArrowLeft size={16} />
              {t('finance.backToInvoices', 'Zrugg zue R?chnige')}
            </Button>
          }
        />
      </div>
    )
  }

  const isPaid = inv.status === 'Paid'
  const reminders = inv.reminderSentAt ?? []

  const lineItemDesc =
    inv.description ||
    (inv.purpose === 'membership'
      ? t(
          'finance.monthlyMembershipFee',
          `Monatlichi Mitgliedschaft (${new Date(inv.issued).toLocaleString(
            'en',
            {
              month: 'long',
              year: 'numeric',
            },
          )})`,
        )
      : t('finance.invoice.defaultDescription', 'R?chnig'))

  return (
    <div>
      <PageHead
        eyebrow={t('finance.invoicesBreadcrumb', 'Finanze › R?chnige')}
        title={inv.id}
        actions={
          <div style={{ display: 'flex', gap: 8 }}>
            <Button
              variant="subtle"
              onClick={() => go('/app/finance/invoices')}
            >
              <IconArrowLeft size={16} />
              {t('finance.allInvoices', 'Alli R?chnige')}
            </Button>
            <Button variant="subtle" onClick={() => downloadInvoicePdf(inv.id)}>
              <IconFileDownload size={16} />
              {t('finance.downloadQrBill', 'QR-R?chnig')}
            </Button>
            {!isPaid && (
              <Button
                variant="subtle"
                onClick={() => sendReminderMutation.mutate(inv.id)}
              >
                <IconBell size={16} />
                {t('finance.sendReminder', 'Erinnerig sende')}
              </Button>
            )}
            {!isPaid && (
              <Button
                variant="filled"
                onClick={() => markPaidMutation.mutate(inv.id)}
              >
                <IconCheck size={16} />
                {t('finance.markPaid', 'Als bezahlt markiere')}
              </Button>
            )}
          </div>
        }
      />

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 340px',
          gap: 16,
          alignItems: 'start',
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Paper withBorder shadow="sm" radius="lg">
            <Group
              p="md"
              gap="sm"
              style={{ borderBottom: '1px solid var(--mantine-color-gray-3)' }}
            >
              <Text fw={700} fz="md">
                {t('finance.lineItems', 'Positions')}
              </Text>
            </Group>
            <div style={{ overflowX: 'auto' }}>
              <Table highlightOnHover className="responsive-table">
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>{t('common.description', 'Beschribig')}</Table.Th>
                    <Table.Th style={{ textAlign: 'right' }}>
                      {t('finance.amount', 'Betrag')}
                    </Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  <Table.Tr>
                    <Table.Td
                      data-label={t('common.description', 'Beschribig')}
                    >
                      {lineItemDesc}
                    </Table.Td>
                    <Table.Td
                      data-label={t('finance.amount', 'Betrag')}
                      style={{ textAlign: 'right' }}
                    >
                      <span className="num" style={{ fontWeight: 600 }}>
                        CHF {formatCHF(inv.amount)}
                      </span>
                    </Table.Td>
                  </Table.Tr>
                </Table.Tbody>
              </Table>
            </div>
            <div
              style={{
                padding: '12px 20px',
                borderTop: '2px solid #e3eae6',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <span
                style={{
                  fontWeight: 700,
                  fontSize: 'var(--mantine-font-size-sm)',
                  color: '#181818',
                }}
              >
                {t('common.total', 'Total')}
              </span>
              <span
                className="num"
                style={{
                  fontWeight: 700,
                  fontSize: 'var(--mantine-font-size-md)',
                  color: '#181818',
                }}
              >
                CHF {formatCHF(inv.amount)}
              </span>
            </div>
          </Paper>

          <Paper withBorder shadow="sm" radius="lg">
            <Group
              p="md"
              gap="sm"
              style={{ borderBottom: '1px solid var(--mantine-color-gray-3)' }}
            >
              <IconBell size={16} style={{ color: '#6b7480' }} />
              <Text fw={700} fz="md">
                {t('finance.reminder.history', 'Erinnerigs-Verlauf')}
              </Text>
              {!isPaid && (
                <Button
                  size="sm"
                  variant="subtle"
                  style={{ marginLeft: 'auto' }}
                  onClick={() => sendReminderMutation.mutate(inv.id)}
                >
                  {t('finance.sendReminder', 'Erinnerig sende')}
                </Button>
              )}
            </Group>
            {reminders.length === 0 ? (
              <div
                style={{
                  padding: '24px',
                  textAlign: 'center',
                  color: '#99a2ac',
                  fontSize: 'var(--mantine-font-size-sm)',
                }}
              >
                {t('finance.noReminders', 'No cheni Erinnerige gsendet.')}
              </div>
            ) : (
              <div>
                {reminders.map((ts) => (
                  <div
                    key={ts}
                    style={{
                      display: 'flex',
                      gap: 12,
                      padding: '12px 20px',
                      borderBottom: '1px solid #f0f4f1',
                      alignItems: 'center',
                    }}
                  >
                    <IconBell
                      size={16}
                      style={{ color: '#2596be', flexShrink: 0 }}
                    />
                    <div style={{ flex: 1 }}>
                      <div
                        style={{
                          fontSize: 'var(--mantine-font-size-sm)',
                          color: '#181818',
                        }}
                      >
                        {t(
                          'finance.reminder.emailSent',
                          'Erinnerigs-E-Mail gsendet',
                        )}
                      </div>
                      <div
                        style={{
                          fontSize: 'var(--mantine-font-size-xs)',
                          color: '#6b7480',
                        }}
                      >
                        {t('finance.to', 'A')}: {inv.member}
                      </div>
                    </div>
                    <span
                      className="num"
                      style={{
                        fontSize: 'var(--mantine-font-size-xs)',
                        color: '#99a2ac',
                      }}
                    >
                      {ts}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Paper>
        </div>

        <Paper
          withBorder
          shadow="sm"
          radius="lg"
          style={{ padding: '20px 24px' }}
        >
          <div style={{ marginBottom: 20 }}>
            <InvoicePill status={inv.status} />
          </div>
          {[
            {
              label: t('finance.recipient', 'Empfänger'),
              value: inv.member,
            },
            {
              label: t('finance.purpose', 'Zweck'),
              value:
                inv.purpose === 'membership'
                  ? t('finance.purpose.membership', 'Mitgliedschaft')
                  : t('finance.purpose.other', 'Anderers'),
            },
            {
              label: t('finance.invoice.number', 'R?chnigs-Nr.'),
              value: inv.id,
            },
            {
              label: t('finance.invoice.issued', 'Usgstellt'),
              value: inv.issued,
            },
            {
              label: t('finance.invoice.due', 'F?lligkeitsdatum'),
              value: inv.due,
            },
            {
              label: t('finance.amount', 'Betrag'),
              value: `CHF ${formatCHF(inv.amount)}`,
            },
            {
              label: t('common.created', 'Erstellt'),
              value: inv.createdAt
                ? new Date(inv.createdAt).toLocaleDateString('en-CH', {
                    day: '2-digit',
                    month: 'short',
                    year: 'numeric',
                  })
                : '?',
            },
            {
              label: t('finance.remindersSent', 'Erinnerige gsendet'),
              value: String(reminders.length),
            },
          ].map(({ label, value }) => (
            <div
              key={label}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                padding: '10px 0',
                borderBottom: '1px solid #f0f4f1',
              }}
            >
              <span
                style={{
                  fontSize: 'var(--mantine-font-size-sm)',
                  color: '#6b7480',
                }}
              >
                {label}
              </span>
              <span
                className="num"
                style={{
                  fontSize: 'var(--mantine-font-size-sm)',
                  fontWeight: 500,
                  color: '#181818',
                }}
              >
                {value}
              </span>
            </div>
          ))}
          {inv.transactionId && (
            <div style={{ marginTop: 16 }}>
              <Button
                variant="subtle"
                style={{
                  width: '100%',
                  justifyContent: 'center',
                  gap: 8,
                  fontSize: 'var(--mantine-font-size-sm)',
                }}
                onClick={() => go('/app/finance/transactions')}
              >
                <IconExternalLink size={16} />
                {t('finance.viewTransaction', 'Transaktion #{{id}} ahluege', {
                  id: inv.transactionId,
                })}
              </Button>
            </div>
          )}
        </Paper>
      </div>
    </div>
  )
}
