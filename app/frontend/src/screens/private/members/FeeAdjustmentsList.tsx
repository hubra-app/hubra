import { Anchor, Paper, Table, Text } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { IconReceiptOff } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useAuth, useNav } from '@/context/AppContext'
import { formatDate } from '@/format'
import { listFeeAdjustments } from '@/api/feeAdjustments'
import { qk } from '@/data/keys'
import { FeeAdjustmentStatus } from './MemberFeeSection'
import { feeAdjustmentLabel } from './feeAdjustment'

/** Members with their own fee (exempt or reduced), ending soonest first,
 *  under the tiers. Set on each member's page. */
export function FeeAdjustmentsList() {
  const { t } = useT()
  const { go } = useNav()
  const { hasPermission } = useAuth()
  const canRead = hasPermission('tiers.fee_adjustments.read')
  const { data = [] } = useQuery({
    queryKey: qk.tiers.feeAdjustments,
    queryFn: listFeeAdjustments,
    enabled: canRead,
  })
  if (!canRead || data.length === 0) return null

  return (
    <Paper withBorder mt={24} data-testid="fee-adjustments">
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '12px 16px',
          borderBottom: '1px solid var(--hb-border)',
        }}
      >
        <IconReceiptOff size={16} style={{ color: 'var(--mantine-color-acc-7)' }} />
        <Text fw={700} size="sm" style={{ flex: 1 }}>
          {t('fees.listTitle', 'Eigene Beiträge')}
        </Text>
        <Text size="xs" c="dimmed">
          {t('fees.listHint', 'Befreiungen und Ermässigungen, auf der Seite des Mitglieds anpassen')}
        </Text>
      </div>
      <Table.ScrollContainer minWidth={520}>
        <Table highlightOnHover verticalSpacing="sm">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{t('common.name', 'Name')}</Table.Th>
              <Table.Th>{t('fees.own', 'Eigener Beitrag')}</Table.Th>
              <Table.Th>{t('fees.until', 'Gültig bis')}</Table.Th>
              <Table.Th>{t('common.status')}</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {data.map((adj) => (
              <Table.Tr key={adj.id}>
                <Table.Td>
                  <Anchor size="sm" fw={600} onClick={() => go(`/app/members/${adj.member_id}`)}>
                    {adj.member_name}
                  </Anchor>
                </Table.Td>
                <Table.Td>{feeAdjustmentLabel(adj, t)}</Table.Td>
                <Table.Td>{adj.valid_until ? formatDate(adj.valid_until) : t('fees.noEnd', 'Unbefristet')}</Table.Td>
                <Table.Td>
                  <FeeAdjustmentStatus adj={adj} />
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
    </Paper>
  )
}
