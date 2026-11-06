import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Anchor, Badge, Group, Paper, SimpleGrid, Stack, Table, Text, Title } from '@mantine/core'
import { formatDate } from '@/format'
import { tr } from '@/lang'
import { getBillingOverview, type BillingStatus } from '@/api/tenants'
import { chf, STATUS, statusText } from '@/billing'

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <Paper withBorder p="sm">
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Text fw={700} size="lg">
        {value}
      </Text>
    </Paper>
  )
}

/**
 * What clubs pay Hubra through Stripe Billing: monthly and yearly revenue,
 * clubs per status and the clubs whose payment failed (docs/billing.md).
 */
export function BillingOverview() {
  const navigate = useNavigate()
  const { data } = useQuery({ queryKey: ['billing-overview'], queryFn: getBillingOverview })
  if (!data) return null

  const statuses = (Object.keys(data.perStatus) as BillingStatus[]).filter(
    (s) => (data.perStatus[s] ?? 0) > 0,
  )

  return (
    <Paper withBorder p="lg">
      <Group gap={8} mb={4}>
        <Title order={3}>{tr('Abrechnung', 'Billing')}</Title>
        <Badge variant="light" color={data.enabled ? 'green' : 'gray'}>
          {data.enabled ? tr('Über Stripe', 'Through Stripe') : tr('Ausgeschaltet', 'Off')}
        </Badge>
        {data.enabled && data.testMode && (
          <Badge variant="light" color="orange">
            {tr('Testmodus', 'Test mode')}
          </Badge>
        )}
      </Group>
      <Text size="xs" c="dimmed" mb={12}>
        {data.enabled
          ? tr(
              `Vereine bezahlen ${data.yearly ? 'jährlich' : 'monatlich'} über Stripe. Umsatz aus aktiven und überfälligen Abos, nach Rabatt und Sponsoring.`,
              `Clubs pay ${data.yearly ? 'yearly' : 'monthly'} through Stripe. Revenue from active and past-due subscriptions, after discount and sponsoring.`,
            )
          : tr(
              'Einschalten unter Zahlungen › Abrechnung der Vereine, mit dem Stripe-Schlüssel und dem Webhook-Secret.',
              'Turn it on under Payments › Club billing, with the Stripe key and the webhook secret.',
            )}
      </Text>
      <SimpleGrid cols={{ base: 2, sm: 3 }} spacing="sm" mb={12}>
        <Tile label={tr('Umsatz pro Monat', 'Revenue per month')} value={chf(data.mrrChf)} />
        <Tile label={tr('Umsatz pro Jahr', 'Revenue per year')} value={chf(data.arrChf)} />
        <Tile label={tr('Zahlende Vereine', 'Paying clubs')} value={String(data.payingClubs)} />
      </SimpleGrid>
      {statuses.length > 0 && (
        <Group gap={6} mb={12}>
          {statuses.map((s) => (
            <Badge key={s} variant="light" color={STATUS[s]?.color ?? 'gray'}>
              {STATUS[s] ? statusText(s) : s}: {data.perStatus[s]}
            </Badge>
          ))}
        </Group>
      )}
      {data.trouble.length > 0 && (
        <Stack gap={6}>
          <Text fw={600} size="sm">
            {tr('Zahlungsprobleme', 'Payment problems')}
          </Text>
          <Table striped withTableBorder>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{tr('Verein', 'Club')}</Table.Th>
                <Table.Th>{tr('Status', 'Status')}</Table.Th>
                <Table.Th>{tr('Fällig pro Monat', 'Due per month')}</Table.Th>
                <Table.Th>{tr('Fehlgeschlagen am', 'Failed on')}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.trouble.map((t) => (
                <Table.Tr key={t.id}>
                  <Table.Td>
                    <Anchor size="sm" onClick={() => navigate(`/app/tenants/${t.id}`)}>
                      {t.name}
                    </Anchor>
                  </Table.Td>
                  <Table.Td>
                    <Badge variant="light" color={STATUS[t.status]?.color ?? 'gray'}>
                      {STATUS[t.status] ? statusText(t.status) : t.status}
                    </Badge>
                  </Table.Td>
                  <Table.Td>{chf(t.dueChf)}</Table.Td>
                  <Table.Td>{t.paymentFailedAt ? formatDate(t.paymentFailedAt) : '–'}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Stack>
      )}
    </Paper>
  )
}
