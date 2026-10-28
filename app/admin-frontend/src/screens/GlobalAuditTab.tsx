import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Table, Paper, Text, Badge } from '@mantine/core'
import { listGlobalAudit, type GlobalAuditEntry } from '@/api/tenants'
import { Pagination } from '@/components/ui'
import { formatDateTime } from '@/format'

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
    <Paper withBorder shadow="sm" radius="lg">
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

      {isLoading && (
        <Text p={40} ta="center" c="dimmed">
          Loading audit log...
        </Text>
      )}

      {!isLoading && entries.length === 0 && (
        <Text p={40} ta="center" c="dimmed">
          No audit entries found.
        </Text>
      )}

      {entries.length > 0 && (
        <Table highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Time</Table.Th>
              <Table.Th>Action</Table.Th>
              <Table.Th>Tenant</Table.Th>
              <Table.Th>Actor</Table.Th>
              <Table.Th>Target</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {entries.map((entry: GlobalAuditEntry) => (
              <Table.Tr key={entry.id}>
                <Table.Td style={{ fontSize: 14, color: '#5e5873' }}>
                  {formatDateTime(entry.time)}
                </Table.Td>
                <Table.Td>
                  <Badge variant="light" color={actionColor(entry.action)} size="sm">
                    {entry.action}
                  </Badge>
                </Table.Td>
                <Table.Td className="num" style={{ fontSize: 14 }}>
                  {entry.tenant_id ?? '-'}
                </Table.Td>
                <Table.Td style={{ fontSize: 14 }}>
                  {entry.actor_id ?? 'system'}
                </Table.Td>
                <Table.Td style={{ fontSize: 14, color: '#5e5873' }}>
                  {entry.target_type ? `${entry.target_type}:${entry.target_id ?? ''}` : '-'}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
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
