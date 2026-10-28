import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Table, TextInput, Paper, Badge, Button, Group, Text, Chip } from '@mantine/core'
import { IconSearch, IconPlus } from '@tabler/icons-react'
import { formatDate } from '@/format'
import { listTenants, type Tenant } from '@/api/tenants'
import { Pagination } from '@/components/ui'
import { CreateTenantModal } from '@/screens/CreateTenantModal'
import { useAdmin } from '@/context/AdminContext'

const STATUS_COLORS: Record<string, string> = {
  active: 'green',
  suspended: 'orange',
  archived: 'gray',
}

const PLAN_FILTERS = ['all', 'starter', 'growth', 'enterprise'] as const
const STATUS_FILTERS = ['all', 'active', 'suspended', 'archived'] as const

export function TenantsTab() {
  const navigate = useNavigate()
  const { isSuperadmin } = useAdmin()
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
      <Group justify="space-between" mb={16}>
        <Group gap={10} wrap="wrap">
          <div style={{ position: 'relative', width: 260 }}>
            <IconSearch
              size={16}
              style={{
                position: 'absolute',
                left: 11,
                top: '50%',
                transform: 'translateY(-50%)',
                color: '#99a2ac',
              }}
            />
            <TextInput
              style={{ paddingLeft: 34 }}
              placeholder="Search tenants..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value)
                setPage(1)
              }}
            />
          </div>
          <Group gap={6}>
            {PLAN_FILTERS.map((p) => (
              <Chip
                key={p}
                size="sm"
                variant={planFilter === p ? 'filled' : 'light'}
                checked={planFilter === p}
                onClick={() => {
                  setPlanFilter(p)
                  setPage(1)
                }}
              >
                {p === 'all' ? 'All Plans' : p.charAt(0).toUpperCase() + p.slice(1)}
              </Chip>
            ))}
          </Group>
          <Group gap={6}>
            {STATUS_FILTERS.map((s) => (
              <Chip
                key={s}
                size="sm"
                variant={statusFilter === s ? 'filled' : 'light'}
                checked={statusFilter === s}
                onClick={() => {
                  setStatusFilter(s)
                  setPage(1)
                }}
              >
                {s === 'all' ? 'All Status' : s.charAt(0).toUpperCase() + s.slice(1)}
              </Chip>
            ))}
          </Group>
        </Group>
        <Group gap="xs">
          {isSuperadmin ? (
            <Button leftSection={<IconPlus size={16} />} onClick={() => setCreateOpen(true)}>
              Create Tenant
            </Button>
          ) : (
            <Button leftSection={<IconPlus size={16} />} onClick={() => navigate('/requests')}>
              Request Tenant
            </Button>
          )}
        </Group>
      </Group>

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
            Loading tenants...
          </Text>
        )}

        {!isLoading && tenants.length === 0 && (
          <Text p={40} ta="center" c="dimmed">
            No tenants found.
          </Text>
        )}

        {tenants.length > 0 && (
          <Table highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Name</Table.Th>
                <Table.Th>Slug</Table.Th>
                <Table.Th>Plan</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Created</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {tenants.map((t: Tenant) => (
                <Table.Tr
                  key={t.id}
                  onClick={() => navigate(`/tenants/${t.id}`)}
                  style={{ cursor: 'pointer' }}
                >
                  <Table.Td fw={600}>{t.name}</Table.Td>
                  <Table.Td style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 14 }}>
                    {t.slug}
                  </Table.Td>
                  <Table.Td>
                    <Badge variant="light" color="blue" size="sm">
                      {t.plan}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Badge variant="light" color={STATUS_COLORS[t.status] ?? 'gray'} size="sm">
                      {t.status}
                    </Badge>
                  </Table.Td>
                  <Table.Td style={{ color: '#6b7480', fontSize: 14 }}>
                    {t.created_at ? formatDate(t.created_at) : '-'}
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

      <CreateTenantModal opened={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  )
}
