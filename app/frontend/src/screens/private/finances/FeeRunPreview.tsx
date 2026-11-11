import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Alert,
  Badge,
  Button,
  Group,
  Paper,
  ScrollArea,
  SimpleGrid,
  Table,
  Text,
} from '@mantine/core'
import { DateField } from '@hubra/ui'
import { useT } from '@/locales/i18n'
import { qk } from '@/data/keys'
import { Modal, LoadingSpinner } from '@/components/ui'
import { getFeeRunPreview } from '@/api/finance'
import { formatCHF, formatDate } from '@/format'

function today(): string {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Paper withBorder p="sm">
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Text fw={700} size="lg">
        {value}
      </Text>
      {hint && (
        <Text size="xs" c="dimmed">
          {hint}
        </Text>
      )}
    </Paper>
  )
}

/** Finanzen › Rechnungen: what the daily invoice run would bill on a day,
 * before it does. Reads only. */
export function FeeRunPreviewModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useT()
  const [on, setOn] = useState(today())
  const valid = /^\d{4}-\d{2}-\d{2}$/.test(on)
  const { data, isLoading, isError } = useQuery({
    queryKey: qk.invoices.feeRun(on),
    queryFn: () => getFeeRunPreview(on),
    enabled: open && valid,
  })

  const reason = (key: string) =>
    ({
      not_joined_yet: t('finance.feeRun.skip.notJoinedYet', 'Noch nicht eingetreten'),
      invoice_exists_for_period: t(
        'finance.feeRun.skip.invoiceExists',
        'Rechnung für die Periode schon ausgestellt',
      ),
      amount_zero_or_negative: t('finance.feeRun.skip.amountZero', 'Betrag 0 (z. B. befreit)'),
      no_billable_tier: t('finance.feeRun.skip.noBillableTier', 'Stufe ohne Abrechnung'),
    })[key] ?? key

  const skipped = Object.entries(data?.skipped ?? {})

  return (
    <Modal
      open={open}
      onClose={onClose}
      wide
      title={t('finance.feeRun.title', 'Vorschau Beitragslauf')}
      subtitle={t(
        'finance.feeRun.subtitle',
        'Was der tägliche Rechnungslauf an diesem Tag ausstellen würde. Es wird nichts erstellt.',
      )}
      footer={
        <Button variant="default" onClick={onClose}>
          {t('common.close', 'Schliessen')}
        </Button>
      }
    >
      <DateField
        label={t('finance.feeRun.on', 'Lauf am')}
        value={on}
        onChange={(v) => setOn(v)}
        maw={220}
        data-testid="fee-run-date"
      />
      {isLoading && <LoadingSpinner />}
      {isError && (
        <Alert color="red">{t('finance.feeRun.failed', 'Die Vorschau konnte nicht geladen werden.')}</Alert>
      )}
      {data && (
        <>
          <SimpleGrid cols={{ base: 1, xs: 3 }} spacing="sm">
            <Stat
              label={t('finance.feeRun.invoices', 'Rechnungen')}
              value={String(data.count)}
              hint={
                data.mailed
                  ? t('finance.feeRun.mailed', 'Werden per E-Mail verschickt')
                  : t('finance.feeRun.notMailed', 'Werden nicht verschickt')
              }
            />
            <Stat
              label={t('finance.feeRun.total', 'Total')}
              value={formatCHF(data.total)}
              hint={t('finance.feeRun.due', 'Fällig am {{date}}', { date: formatDate(data.dueOn) })}
            />
            <Stat
              label={t('finance.feeRun.lastYear', 'Letzte 12 Monate')}
              value={formatCHF(data.lastTwelveMonths.total)}
              hint={t('finance.feeRun.lastYearCount', '{{count}} Beitragsrechnungen', {
                count: data.lastTwelveMonths.count,
              })}
            />
          </SimpleGrid>

          {data.count === 0 ? (
            <Text c="dimmed" size="sm">
              {t('finance.feeRun.nothing', 'An diesem Tag würde keine Rechnung ausgestellt.')}
            </Text>
          ) : (
            <>
              {(data.noEmail > 0 || data.prorated > 0 || data.ownCycle > 0) && (
                <Group gap="xs">
                  {data.noEmail > 0 && (
                    <Badge color="orange" variant="light">
                      {t('finance.feeRun.noEmail', '{{count}} ohne E-Mail-Adresse', {
                        count: data.noEmail,
                      })}
                    </Badge>
                  )}
                  {data.prorated > 0 && (
                    <Badge variant="light">
                      {t('finance.feeRun.proratedCount', '{{count}} anteilig (Eintritt)', {
                        count: data.prorated,
                      })}
                    </Badge>
                  )}
                  {data.ownCycle > 0 && (
                    <Badge variant="light">
                      {t('finance.feeRun.ownCycleCount', '{{count}} mit Zahlungsplan', {
                        count: data.ownCycle,
                      })}
                    </Badge>
                  )}
                </Group>
              )}

              <Table withTableBorder>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>{t('finance.feeRun.tier', 'Stufe')}</Table.Th>
                    <Table.Th ta="right">{t('finance.feeRun.invoices', 'Rechnungen')}</Table.Th>
                    <Table.Th ta="right">{t('finance.feeRun.total', 'Total')}</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {data.tiers.map((row) => (
                    <Table.Tr key={row.tierId}>
                      <Table.Td>{row.tier}</Table.Td>
                      <Table.Td ta="right">{row.count}</Table.Td>
                      <Table.Td ta="right">{formatCHF(row.total)}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>

              <ScrollArea.Autosize mah={320} type="auto">
                <Table striped data-testid="fee-run-lines">
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>{t('finance.feeRun.member', 'Mitglied')}</Table.Th>
                      <Table.Th>{t('finance.feeRun.period', 'Periode')}</Table.Th>
                      <Table.Th ta="right">{t('finance.amount', 'Betrag')}</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {data.lines.map((line) => (
                      <Table.Tr key={line.memberId}>
                        <Table.Td>
                          <Text size="sm">{line.name}</Text>
                          <Group gap={4}>
                            <Text size="xs" c="dimmed">
                              {line.tier}
                            </Text>
                            {line.prorated && (
                              <Badge size="xs" variant="light">
                                {t('finance.feeRun.prorated', 'anteilig')}
                              </Badge>
                            )}
                            {line.noEmail && (
                              <Badge size="xs" color="orange" variant="light">
                                {t('finance.feeRun.noEmailShort', 'keine E-Mail')}
                              </Badge>
                            )}
                          </Group>
                        </Table.Td>
                        <Table.Td>
                          <Text size="sm">
                            {formatDate(line.periodStart)} – {formatDate(line.periodEnd)}
                          </Text>
                        </Table.Td>
                        <Table.Td ta="right">{formatCHF(line.amount)}</Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </ScrollArea.Autosize>
              {data.truncated && (
                <Text size="xs" c="dimmed">
                  {t('finance.feeRun.truncated', 'Die ersten {{shown}} von {{count}} Rechnungen.', {
                    shown: data.lines.length,
                    count: data.count,
                  })}
                </Text>
              )}
            </>
          )}

          {skipped.length > 0 && (
            <div>
              <Text size="sm" fw={600}>
                {t('finance.feeRun.skippedTitle', 'Nicht verrechnet')}
              </Text>
              {skipped.map(([key, count]) => (
                <Text size="sm" c="dimmed" key={key}>
                  {reason(key)}: {count}
                </Text>
              ))}
            </div>
          )}
        </>
      )}
    </Modal>
  )
}
