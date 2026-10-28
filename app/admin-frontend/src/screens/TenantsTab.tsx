import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Table, TextInput, Paper, Badge, Button, Group, Text, Select } from '@mantine/core'
import { IconSearch, IconPlus } from '@tabler/icons-react'
import { formatDate } from '@/format'
import { listTenants, type Tenant } from '@/api/tenants'
import { Pagination } from '@/components/ui'
import { CreateTenantModal } from '@/screens/CreateTenantModal'
import { useAdmin } from '@/context/AdminContext'
import { useLang } from '@/lang'
import { planLabel, statusLabel } from '@/labels'

const STATUS_COLORS: Record<string, string> = {
  active: 'green',
  suspended: 'orange',
  archived: 'gray',
}

export function TenantsTab() {
  const navigate = useNavigate()
  const { isSuperadmin } = useAdmin()
  const { tr } = useLang()
  const [search, setSearch] = useState('')
  const [planFilter, setPlanFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(25)
  const [createOpen, setCreateOpen] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['tenants', search, planFilter, statusFilter, page, perPage],
    queryFn: () =>
      listTenants({
        search: search || undefined,
        plan: planFilter !== 'all' ? planFilter : undefined,
        status: statusFilter !== 'all' ? statusFilter : undefined,
        page,
        per_page: perPage,
      }),
  })

  const tenants = data?.tenants ?? []
  const total = data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / perPage))

  return (
    <div>
      <Group justify="space-between" mb="md" gap="sm" wrap="wrap">
        <Group gap="sm" wrap="wrap" style={{ flex: 1 }}>
          <TextInput
            leftSection={<IconSearch size={16} />}
            placeholder={tr('Vereine suchen …', 'Search clubs…')}
            value={search}
            onChange={(e) => {
              setSearch(e.target.value)
              setPage(1)
            }}
            style={{ flex: '1 1 220px', maxWidth: 320 }}
          />
          <Select
            aria-label={tr('Plan', 'Plan')}
            value={planFilter}
            onChange={(v) => {
              setPlanFilter(v ?? 'all')
              setPage(1)
            }}
            allowDeselect={false}
            data={[
              { value: 'all', label: tr('Alle Pläne', 'All plans') },
              ...['starter', 'growth', 'enterprise'].map((p) => ({ value: p, label: planLabel(p, tr) })),
            ]}
            w={160}
          />
          <Select
            aria-label={tr('Status', 'Status')}
            value={statusFilter}
            onChange={(v) => {
              setStatusFilter(v ?? 'all')
              setPage(1)
            }}
            allowDeselect={false}
            data={[
              { value: 'all', label: tr('Alle Status', 'All statuses') },
              ...['active', 'suspended', 'archived'].map((st) => ({ value: st, label: statusLabel(st, tr) })),
            ]}
            w={160}
          />
        </Group>
        {isSuperadmin ? (
          <Button leftSection={<IconPlus size={16} />} onClick={() => setCreateOpen(true)}>
            {tr('Verein erstellen', 'Create club')}
          </Button>
        ) : (
          <Button leftSection={<IconPlus size={16} />} onClick={() => navigate('/app/requests')}>
            {tr('Verein beantragen', 'Request a club')}
          </Button>
        )}
      </Group>

      <Paper withBorder style={{ overflow: 'hidden' }}>

        {isLoading && (
          <Text p={40} ta="center" c="dimmed">
            {tr('Vereine werden geladen …', 'Loading clubs…')}
          </Text>
        )}

        {!isLoading && tenants.length === 0 && (
          <Text p={40} ta="center" c="dimmed">
            {tr('Keine Vereine gefunden.', 'No clubs found.')}
          </Text>
        )}

        {tenants.length > 0 && (
          <Table.ScrollContainer minWidth={640}>
          <Table highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{tr('Name', 'Name')}</Table.Th>
                <Table.Th>{tr('Kürzel', 'Slug')}</Table.Th>
                <Table.Th>{tr('Plan', 'Plan')}</Table.Th>
                <Table.Th>{tr('Status', 'Status')}</Table.Th>
                <Table.Th>{tr('Erstellt', 'Created')}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {tenants.map((t: Tenant) => (
                <Table.Tr
                  key={t.id}
                  onClick={() => navigate(`/app/tenants/${t.id}`)}
                  style={{ cursor: 'pointer' }}
                >
                  <Table.Td fw={600}>{t.name}</Table.Td>
                  <Table.Td className="num" fz="sm" c="dimmed">
                    {t.slug}
                  </Table.Td>
                  <Table.Td>
                    <Badge variant="light" color="acc" size="sm">
                      {planLabel(t.plan, tr)}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Badge variant="light" color={STATUS_COLORS[t.status] ?? 'gray'} size="sm">
                      {statusLabel(t.status, tr)}
                    </Badge>
                  </Table.Td>
                  <Table.Td fz="sm" c="dimmed">
                    {t.created_at ? formatDate(t.created_at) : '–'}
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

      <CreateTenantModal opened={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  )
}
