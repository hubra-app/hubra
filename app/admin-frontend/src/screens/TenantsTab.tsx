import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Table,
  TextInput,
  Paper,
  Badge,
  Button,
  Group,
  Text,
  Select,
  Tooltip,
  UnstyledButton,
} from '@mantine/core'
import {
  IconSearch,
  IconPlus,
  IconChevronDown,
  IconChevronUp,
  IconSelector,
} from '@tabler/icons-react'
import { formatAgo, formatBytes } from '@/format'
import {
  listTenantsHealth,
  type HealthLevel,
  type TenantHealth,
  type TenantWithHealth,
} from '@/api/tenants'
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

const LEVEL_COLOR: Record<HealthLevel, string> = {
  ok: 'green',
  idle: 'gray',
  warning: 'orange',
  error: 'red',
}

type HealthFilter = 'all' | 'problems' | 'idle' | 'ok'

function levelText(level: HealthLevel, tr: (de: string, en: string) => string) {
  return {
    ok: tr('Alles in Ordnung', 'All good'),
    idle: tr('Seit Wochen nicht benutzt', 'Not used for weeks'),
    warning: tr('Warnungen in den letzten 24 Stunden', 'Warnings in the last 24 hours'),
    error: tr('Fehler in den letzten 24 Stunden', 'Errors in the last 24 hours'),
  }[level]
}

function HealthDot({ level }: { level: HealthLevel }) {
  const { tr } = useLang()
  return (
    <Tooltip label={levelText(level, tr)} withArrow>
      <span
        role="img"
        aria-label={levelText(level, tr)}
        style={{
          display: 'inline-block',
          flex: 'none',
          width: 10,
          height: 10,
          borderRadius: '50%',
          background: `var(--mantine-color-${LEVEL_COLOR[level]}-6)`,
        }}
      />
    </Tooltip>
  )
}

function SortHeader({
  field,
  sort,
  onSort,
  children,
  align,
}: {
  field: string
  sort: { by: string; dir: 'asc' | 'desc' }
  onSort: (field: string) => void
  children: React.ReactNode
  align?: 'right'
}) {
  const active = sort.by === field
  const Icon = !active ? IconSelector : sort.dir === 'asc' ? IconChevronUp : IconChevronDown
  return (
    <Table.Th style={{ textAlign: align, whiteSpace: 'nowrap' }}>
      <UnstyledButton
        onClick={() => onSort(field)}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 4,
          font: 'inherit',
          color: 'inherit',
          textTransform: 'inherit',
          letterSpacing: 'inherit',
        }}
        aria-sort={active ? (sort.dir === 'asc' ? 'ascending' : 'descending') : undefined}
      >
        {children}
        <Icon size={14} style={{ opacity: active ? 1 : 0.4 }} />
      </UnstyledButton>
    </Table.Th>
  )
}

function AlertsCell({ tenant, h }: { tenant: TenantWithHealth; h: TenantHealth }) {
  const navigate = useNavigate()
  const { tr } = useLang()
  if (!h.alerts.error && !h.alerts.warning)
    return (
      <Text c="dimmed" fz="sm" ta="right">
        –
      </Text>
    )
  return (
    <Group gap={4} wrap="nowrap" justify="flex-end">
      {(['error', 'warning'] as const)
        .filter((l) => h.alerts[l])
        .map((l) => (
          <Badge
            key={l}
            size="sm"
            variant="light"
            color={l === 'error' ? 'red' : 'orange'}
            style={{ cursor: 'pointer' }}
            title={tr('Ereignisse dieses Vereins ansehen', "Show this club's events")}
            onClick={(e) => {
              e.stopPropagation()
              navigate(
                `/app/platform/alerts/events?level=problems&club=${tenant.id}&name=${encodeURIComponent(tenant.name)}`,
              )
            }}
          >
            {h.alerts[l]} {l === 'error' ? tr('Fehler', 'errors') : tr('Warn.', 'warn.')}
          </Badge>
        ))}
    </Group>
  )
}

export function TenantsTab() {
  const navigate = useNavigate()
  const { isSuperadmin } = useAdmin()
  const { tr } = useLang()
  const [search, setSearch] = useState('')
  const [planFilter, setPlanFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [healthFilter, setHealthFilter] = useState<HealthFilter>('all')
  const [sort, setSort] = useState<{ by: string; dir: 'asc' | 'desc' }>({
    by: 'level',
    dir: 'desc',
  })
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(25)
  const [createOpen, setCreateOpen] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: [
      'tenants-health',
      search,
      planFilter,
      statusFilter,
      healthFilter,
      sort,
      page,
      perPage,
    ],
    queryFn: () =>
      listTenantsHealth({
        search: search || undefined,
        plan: planFilter !== 'all' ? planFilter : undefined,
        status: statusFilter !== 'all' ? statusFilter : undefined,
        health: healthFilter !== 'all' ? healthFilter : undefined,
        sort_by: sort.by,
        sort_dir: sort.dir,
        page,
        per_page: perPage,
      }),
    refetchInterval: 60_000,
  })
  const counts = data?.counts
  const windows = data?.windows
  const onSort = (field: string) => {
    setSort((s) =>
      s.by === field
        ? { by: field, dir: s.dir === 'asc' ? 'desc' : 'asc' }
        : { by: field, dir: field === 'name' ? 'asc' : 'desc' },
    )
    setPage(1)
  }

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
              ...['starter', 'growth', 'enterprise'].map((p) => ({
                value: p,
                label: planLabel(p, tr),
              })),
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
              ...['active', 'suspended', 'archived'].map((st) => ({
                value: st,
                label: statusLabel(st, tr),
              })),
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

      <Group gap="xs" mb="sm" wrap="wrap">
        {(
          [
            [
              'all',
              tr('Alle', 'All'),
              counts ? counts.ok + counts.idle + counts.warning + counts.error : null,
              undefined,
            ],
            [
              'problems',
              tr('Mit Problemen', 'With problems'),
              counts ? counts.warning + counts.error : null,
              'orange',
            ],
            ['idle', tr('Unbenutzt', 'Unused'), counts?.idle ?? null, 'gray'],
            ['ok', tr('In Ordnung', 'All good'), counts?.ok ?? null, 'green'],
          ] as const
        ).map(([value, label, n, color]) => (
          <Button
            key={value}
            size="xs"
            variant={healthFilter === value ? 'filled' : 'default'}
            color={healthFilter === value ? color : undefined}
            onClick={() => {
              setHealthFilter(value)
              setPage(1)
            }}
          >
            {label}
            {n != null ? ` · ${n}` : ''}
          </Button>
        ))}
        {windows && (
          <Text fz="xs" c="dimmed" ml="auto">
            {tr(
              `Mails: letzte ${windows.mail_days} Tage · Warnungen: letzte ${windows.alert_hours} Std. · unbenutzt: ${windows.idle_days} Tage ohne Anmeldung`,
              `Mail: last ${windows.mail_days} days · alerts: last ${windows.alert_hours} h · unused: no sign-in for ${windows.idle_days} days`,
            )}
          </Text>
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
          <Table.ScrollContainer minWidth={980}>
            <Table highlightOnHover style={{ whiteSpace: 'nowrap' }}>
              <Table.Thead>
                <Table.Tr>
                  <SortHeader field="name" sort={sort} onSort={onSort}>
                    {tr('Verein', 'Club')}
                  </SortHeader>
                  <Table.Th>{tr('Plan', 'Plan')}</Table.Th>
                  <Table.Th>{tr('Status', 'Status')}</Table.Th>
                  <SortHeader field="members" sort={sort} onSort={onSort} align="right">
                    {tr('Mitglieder', 'Members')}
                  </SortHeader>
                  <SortHeader field="last_activity" sort={sort} onSort={onSort}>
                    {tr('Zuletzt aktiv', 'Last active')}
                  </SortHeader>
                  <SortHeader field="storage" sort={sort} onSort={onSort} align="right">
                    {tr('Speicher', 'Storage')}
                  </SortHeader>
                  <SortHeader field="mail" sort={sort} onSort={onSort} align="right">
                    {tr('Mails', 'Mail')}
                  </SortHeader>
                  <SortHeader field="plugins" sort={sort} onSort={onSort} align="right">
                    {tr('Plugins', 'Plugins')}
                  </SortHeader>
                  <SortHeader field="alerts" sort={sort} onSort={onSort} align="right">
                    {tr('Warnungen', 'Alerts')}
                  </SortHeader>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {tenants.map((t: TenantWithHealth) => {
                  const h = t.health
                  return (
                    <Table.Tr
                      key={t.id}
                      onClick={() => navigate(`/app/tenants/${t.id}`)}
                      style={{ cursor: 'pointer' }}
                    >
                      <Table.Td>
                        <Group gap={10} wrap="nowrap">
                          <HealthDot level={h.level} />
                          <div style={{ minWidth: 0 }}>
                            <Text fw={600} fz="sm" truncate>
                              {t.name}
                            </Text>
                            <Text className="num" fz="xs" c="dimmed">
                              {t.slug}
                            </Text>
                          </div>
                        </Group>
                      </Table.Td>
                      <Table.Td>
                        <Badge variant="light" color="acc" size="sm" miw="max-content">
                          {planLabel(t.plan, tr)}
                        </Badge>
                      </Table.Td>
                      <Table.Td>
                        <Badge
                          variant="light"
                          color={STATUS_COLORS[t.status] ?? 'gray'}
                          size="sm"
                          miw="max-content"
                        >
                          {statusLabel(t.status, tr)}
                        </Badge>
                      </Table.Td>
                      <Table.Td className="num" fz="sm" ta="right">
                        <Tooltip
                          label={tr(
                            `${h.active_members} in den letzten 30 Tagen angemeldet`,
                            `${h.active_members} signed in during the last 30 days`,
                          )}
                          withArrow
                        >
                          <span>
                            {h.members}
                            <Text span fz="xs" c="dimmed">
                              {' '}
                              · {h.active_members} {tr('aktiv', 'active')}
                            </Text>
                          </span>
                        </Tooltip>
                      </Table.Td>
                      <Table.Td fz="sm" c={h.level === 'idle' ? 'dimmed' : undefined}>
                        {formatAgo(h.last_activity, tr)}
                      </Table.Td>
                      <Table.Td className="num" fz="sm" ta="right">
                        {formatBytes(h.storage_bytes)}
                      </Table.Td>
                      <Table.Td className="num" fz="sm" ta="right">
                        {h.mail.sent}
                        {h.mail.failed > 0 && (
                          <Text span fz="xs" c="red">
                            {' '}
                            · {h.mail.failed} {tr('fehlg.', 'failed')}
                          </Text>
                        )}
                      </Table.Td>
                      <Table.Td className="num" fz="sm" ta="right">
                        {h.plugins || '–'}
                      </Table.Td>
                      <Table.Td>
                        <AlertsCell tenant={t} h={h} />
                      </Table.Td>
                    </Table.Tr>
                  )
                })}
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
