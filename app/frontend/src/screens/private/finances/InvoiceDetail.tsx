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
import { useNav } from '@/context/AppContext'
import { useInvoices } from '@/data/lists'
import { PageHead, InvoicePill } from '@/components/ui'
import { getInvoice, downloadInvoicePdf } from '@/api/finance'
import { formatCHF, formatDate } from '@/format'
import {
  useMarkInvoicePaid,
  useSendInvoiceReminder,
} from '@/screens/private/finances/useInvoiceActions'
import { qk } from '@/data/keys'

/* -- Invoice Detail ---------------------------- */
export function InvoiceDetailScreen() {
  const { t, i18n } = useT()
  const { id } = useParams<{ id: string }>()
  const { go, selectedInvoice } = useNav()
  const { invoices } = useInvoices()
  const markPaidMutation = useMarkInvoicePaid()
  const sendReminderMutation = useSendInvoiceReminder()
  const { data: fetchedInvoice } = useQuery({
    queryKey: qk.invoices.one(id),
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
          title={t('finance.invoice.notFound', 'Rechnung nicht gefunden')}
          actions={
            <Button
              variant="subtle"
              onClick={() => go('/app/finance/invoices')}
            >
              <IconArrowLeft size={16} />
              {t('finance.backToInvoices', 'Zurück zu den Rechnungen')}
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
      ? t('finance.monthlyMembershipFee', 'Mitgliederbeitrag {{month}}', {
          month: new Date(inv.issued).toLocaleString(i18n.language, {
            month: 'long',
            year: 'numeric',
          }),
        })
      : t('finance.invoice.defaultDescription', 'Rechnung'))

  return (
    <div>
      <PageHead
        title={inv.id}
        actions={
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            <Button
              variant="subtle"
              onClick={() => go('/app/finance/invoices')}
            >
              <IconArrowLeft size={16} />
              {t('finance.allInvoices', 'Alle Rechnungen')}
            </Button>
            <Button variant="subtle" onClick={() => downloadInvoicePdf(inv.id)}>
              <IconFileDownload size={16} />
              {t('finance.downloadQrBill', 'QR-Rechnung herunterladen')}
            </Button>
            {!isPaid && (
              <Button
                variant="subtle"
                onClick={() => sendReminderMutation.mutate(inv.id)}
              >
                <IconBell size={16} />
                {t('finance.sendReminder', 'Erinnerung senden')}
              </Button>
            )}
            {!isPaid && (
              <Button
                variant="filled"
                onClick={() => markPaidMutation.mutate(inv.id)}
                loading={markPaidMutation.isPending}
              >
                <IconCheck size={16} />
                {t('finance.markPaid', 'Als bezahlt markieren')}
              </Button>
            )}
          </div>
        }
      />

      <div className="detail-grid-end">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Paper withBorder shadow="sm" radius="lg">
            <Group
              p="md"
              gap="sm"
              style={{ borderBottom: '1px solid var(--hb-border)' }}
            >
              <Text fw={700} fz="md">
                {t('finance.lineItems', 'Positionen')}
              </Text>
            </Group>
            <div style={{ overflowX: 'auto' }}>
              <Table highlightOnHover className="responsive-table">
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>{t('common.description', 'Beschreibung')}</Table.Th>
                    <Table.Th style={{ textAlign: 'right' }}>
                      {t('finance.amount', 'Betrag')}
                    </Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  <Table.Tr>
                    <Table.Td
                      data-label={t('common.description', 'Beschreibung')}
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
                borderTop: '2px solid var(--hb-border)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <span
                style={{
                  fontWeight: 700,
                  fontSize: 'var(--mantine-font-size-sm)',
                  color: 'var(--hb-text)',
                }}
              >
                {t('common.total', 'Total')}
              </span>
              <span
                className="num"
                style={{
                  fontWeight: 700,
                  fontSize: 'var(--mantine-font-size-md)',
                  color: 'var(--hb-text)',
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
              style={{ borderBottom: '1px solid var(--hb-border)' }}
            >
              <IconBell size={16} style={{ color: 'var(--hb-text-2)' }} />
              <Text fw={700} fz="md">
                {t('finance.reminder.history', 'Versendete Erinnerungen')}
              </Text>
              {!isPaid && (
                <Button
                  size="sm"
                  variant="subtle"
                  style={{ marginLeft: 'auto' }}
                  onClick={() => sendReminderMutation.mutate(inv.id)}
                >
                  {t('finance.sendReminder', 'Erinnerung senden')}
                </Button>
              )}
            </Group>
            {reminders.length === 0 ? (
              <div
                style={{
                  padding: '24px',
                  textAlign: 'center',
                  color: 'var(--hb-text-3)',
                  fontSize: 'var(--mantine-font-size-sm)',
                }}
              >
                {t('finance.noReminders', 'Noch keine Mahnungen versendet.')}
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
                      borderBottom: '1px solid #f1eff7',
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
                          color: 'var(--hb-text)',
                        }}
                      >
                        {t(
                          'finance.reminder.emailSent',
                          'Zahlungserinnerung per E-Mail gesendet',
                        )}
                      </div>
                      <div
                        style={{
                          fontSize: 'var(--mantine-font-size-xs)',
                          color: 'var(--hb-text-2)',
                        }}
                      >
                        {t('finance.to', 'An')}: {inv.member}
                      </div>
                    </div>
                    <span
                      className="num"
                      style={{
                        fontSize: 'var(--mantine-font-size-xs)',
                        color: 'var(--hb-text-3)',
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
              label: t('finance.purposeLabel', 'Zweck'),
              value:
                inv.purpose === 'membership'
                  ? t('finance.purpose.membership', 'Mitgliedschaft')
                  : t('finance.purpose.other', 'Anderes'),
            },
            {
              label: t('finance.invoice.number', 'Rechnungsnummer'),
              value: inv.id,
            },
            {
              label: t('finance.invoice.issued', 'Ausgestellt'),
              value: inv.issued ? formatDate(inv.issued) : '?',
            },
            {
              label: t('finance.invoice.due', 'Fällig'),
              value: inv.due ? formatDate(inv.due) : '?',
            },
            {
              label: t('finance.amount', 'Betrag'),
              value: `CHF ${formatCHF(inv.amount)}`,
            },
            {
              label: t('common.created', 'Erstellt'),
              value: inv.createdAt ? formatDate(inv.createdAt) : '?',
            },
            {
              label: t('finance.remindersSent', 'Erinnerungen gesendet'),
              value: String(reminders.length),
            },
          ].map(({ label, value }) => (
            <div
              key={label}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                padding: '10px 0',
                borderBottom: '1px solid #f1eff7',
              }}
            >
              <span
                style={{
                  fontSize: 'var(--mantine-font-size-sm)',
                  color: 'var(--hb-text-2)',
                }}
              >
                {label}
              </span>
              <span
                className="num"
                style={{
                  fontSize: 'var(--mantine-font-size-sm)',
                  fontWeight: 500,
                  color: 'var(--hb-text)',
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
                {t('finance.viewTransaction', 'Buchung #{{id}} ansehen', {
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
