import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Table, Paper, Text, Badge } from '@mantine/core'
import { listGlobalAudit, type GlobalAuditEntry } from '@/api/tenants'
import { Pagination } from '@/components/ui'
import { formatDateTime } from '@/format'
import { tr } from '@/lang'

export function GlobalAuditTab() {
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(25)

  const { data, isLoading } = useQuery({
    queryKey: ['global-audit', page, perPage],
    queryFn: () => listGlobalAudit({ page, per_page: perPage }),
  })

  const entries = data?.entries ?? []
  const total = data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / perPage))

  const actionColor = (action: string): string => {
    if (action.includes('delete')) return 'red'
    if (action.includes('suspend') || action.includes('disable')) return 'orange'
    if (action.includes('provision')) return 'green'
    if (action.includes('impersonation')) return 'grape'
    return 'gray'
  }

  return (
    <Paper withBorder style={{ overflow: 'hidden' }}>

      {isLoading && (
        <Text p={40} ta="center" c="dimmed">
          {tr('Audit-Log wird geladen …', 'Loading audit log…')}
        </Text>
      )}

      {!isLoading && entries.length === 0 && (
        <Text p={40} ta="center" c="dimmed">
          {tr('Keine Einträge gefunden.', 'No entries found.')}
        </Text>
      )}

      {entries.length > 0 && (
        <Table.ScrollContainer minWidth={680}>
        <Table highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{tr('Zeit', 'Time')}</Table.Th>
              <Table.Th>{tr('Aktion', 'Action')}</Table.Th>
              <Table.Th>{tr('Verein', 'Club')}</Table.Th>
              <Table.Th>{tr('Person', 'Actor')}</Table.Th>
              <Table.Th>{tr('Ziel', 'Target')}</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {entries.map((entry: GlobalAuditEntry) => (
              <Table.Tr key={entry.id}>
                <Table.Td fz="sm" c="dimmed">
                  {formatDateTime(entry.time)}
                </Table.Td>
                <Table.Td>
                  <Badge variant="light" color={actionColor(entry.action)} size="sm">
                    {entry.action}
                  </Badge>
                </Table.Td>
                <Table.Td className="num" fz="sm">
                  {entry.tenant_id ?? '–'}
                </Table.Td>
                <Table.Td fz="sm">
                  {entry.actor_id ?? tr('System', 'System')}
                </Table.Td>
                <Table.Td fz="sm" c="dimmed">
                  {entry.target_type ? `${entry.target_type}:${entry.target_id ?? ''}` : '–'}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
        </Table.ScrollContainer>
      )}

      <Pagination
        page={page}
        perPage={perPage}
        total={total}
        totalPages={totalPages}
        goPage={setPage}
        setPerPage={(n) => {
          setPerPage(n)
          setPage(1)
        }}
      />
    </Paper>
  )
}
