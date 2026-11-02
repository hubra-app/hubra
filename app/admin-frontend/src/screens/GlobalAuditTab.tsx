import { Fragment, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Table, Paper, Text, Badge, Group, Anchor, Code } from '@mantine/core'
import { listGlobalAudit, type GlobalAuditEntry } from '@/api/tenants'
import { EmptyState, Pagination } from '@/components/ui'
import { formatDateTime } from '@/format'
import { tr } from '@/lang'
import { AuditSearch } from './AuditSearch'
import { actionColor, actionLabel } from './auditLabels'

/** Manage › Audit-Log: the search over every log, or one platform entry
 * (``?entry=<id>``, e.g. from a Discord audit post). */
export function GlobalAuditTab() {
  const [params] = useSearchParams()
  return /^\d+$/.test(params.get('entry') ?? '') ? <EntryView /> : <AuditSearch />
}

function EntryView() {
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(25)
  // ?entry=<id>: one entry with its details, e.g. from a Discord audit post.
  const [params, setParams] = useSearchParams()
  const raw = params.get('entry') ?? ''
  const entryId = /^\d+$/.test(raw) ? Number(raw) : undefined

  const { data, isLoading } = useQuery({
    queryKey: ['global-audit', page, perPage, entryId],
    queryFn: () =>
      listGlobalAudit(entryId ? { id: entryId } : { page, per_page: perPage }),
  })

  const entries = data?.entries ?? []
  const total = data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / perPage))

  return (
    <Paper withBorder style={{ overflow: 'hidden' }}>
      {entryId && (
        <Group justify="space-between" px="md" py="sm" style={{ borderBottom: '1px solid var(--mantine-color-default-border)' }}>
          <Text size="sm">
            {tr(`Eintrag #${entryId}`, `Entry #${entryId}`)}
          </Text>
          <Anchor
            component="button"
            type="button"
            size="sm"
            onClick={() => {
              params.delete('entry')
              setParams(params)
            }}
          >
            {tr('Alle Einträge anzeigen', 'Show all entries')}
          </Anchor>
        </Group>
      )}

      {isLoading && (
        <Text p={40} ta="center" c="dimmed">
          {tr('Audit-Log wird geladen …', 'Loading audit log…')}
        </Text>
      )}

      {!isLoading && entries.length === 0 && (
        <EmptyState title={tr('Keine Einträge gefunden.', 'No entries found.')} />
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
              <Fragment key={entry.id}>
              <Table.Tr>
                <Table.Td fz="sm" c="dimmed">
                  {formatDateTime(entry.time)}
                </Table.Td>
                <Table.Td>
                  <Badge variant="light" color={actionColor(entry.action)} size="sm">
                    {actionLabel(entry.action)}
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
              {entryId && (
                <Table.Tr>
                  <Table.Td colSpan={5}>
                    <Text size="xs" c="dimmed" mb={4}>
                      {tr('Details', 'Details')}
                      {entry.ip_address ? ` · IP ${entry.ip_address}` : ''}
                    </Text>
                    <Code block>{JSON.stringify(entry.details ?? {}, null, 2)}</Code>
                  </Table.Td>
                </Table.Tr>
              )}
              </Fragment>
            ))}
          </Table.Tbody>
        </Table>
        </Table.ScrollContainer>
      )}

      {!entryId && (
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
      )}
    </Paper>
  )
}
