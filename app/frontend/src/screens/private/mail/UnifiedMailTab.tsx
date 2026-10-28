import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { IconRefresh } from '@tabler/icons-react'
import { Button } from '@mantine/core'
import { useAuth } from '@/context/AppContext'
import { DataTable } from '@/components/ui'
import { useMailColumns } from '@/screens/private/mail/MailAddressRow'
import { MailSettingsModal } from '@/screens/private/mail/MailSettingsModal'
import { listAddresses, type ManagedMailAddressInfo } from '@/api/mail'

type OwnerFilter = 'all' | 'member' | 'group' | 'function'
type EnabledFilter = 'all' | 'true' | 'false'
type SyncFilter = 'all' | 'ok' | 'pending' | 'drift' | 'error'

const OWNER_LABELS: Record<string, string> = {
  member: 'Member',
  group: 'Group',
  function: 'Function',
  mail_address: 'Alias',
  system: 'System',
}

export function UnifiedMailTab() {
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [ownerFilter, setOwnerFilter] = useState<OwnerFilter>('all')
  const [enabledFilter, setEnabledFilter] = useState<EnabledFilter>('all')
  const [syncFilter, setSyncFilter] = useState<SyncFilter>('all')
  const [editEntry, setEditEntry] = useState<ManagedMailAddressInfo | null>(
    null,
  )

  const canManage =
    hasPermission('mail.aliases.update') || hasPermission('mail.aliases.create')

  const {
    data,
    isLoading: loading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: [
      'mail-addresses',
      ownerFilter,
      enabledFilter,
      syncFilter,
      search,
    ],
    queryFn: () =>
      listAddresses({
        ownerType: ownerFilter === 'all' ? undefined : ownerFilter,
        enabled: enabledFilter === 'all' ? undefined : enabledFilter === 'true',
        syncState: syncFilter === 'all' ? undefined : syncFilter,
        search: search || undefined,
      }),
  })
  const entries = data ?? []

  const baseColumns = useMailColumns((entry) => entry.ownerName)

  const ownerTypeColumn = {
    key: 'ownerType',
    header: 'Type',
    render: (entry: ManagedMailAddressInfo) => {
      const OWNER_COLORS: Record<string, string> = {
        member: '#1f9d57',
        group: '#2596be',
        function: '#7c4dcc',
        mail_address: '#c2870f',
        system: '#e65100',
      }
      let label: string
      let color: string
      if (entry.isSystem) {
        label = 'System'
        color = OWNER_COLORS.system
      } else if (entry.ownerType === 'mail_address') {
        label = 'Alias'
        color = OWNER_COLORS.mail_address
      } else if (entry.ownerType && OWNER_LABELS[entry.ownerType]) {
        label = OWNER_LABELS[entry.ownerType]
        color = OWNER_COLORS[entry.ownerType] ?? '#6b7480'
      } else {
        label = entry.kind ?? 'Other'
        color = '#6b7480'
      }
      return (
        <span
          style={{
            fontSize: 'var(--mantine-font-size-xs)',
            fontWeight: 600,
            color,
            background: color + '15',
            padding: '2px 8px',
            borderRadius: 10,
          }}
        >
          {label}
        </span>
      )
    },
  }

  const syncFilters = [
    {
      label: 'All sync',
      value: 'all',
      active: syncFilter === 'all',
      onClick: () => setSyncFilter('all'),
    },
    {
      label: 'OK',
      value: 'ok',
      active: syncFilter === 'ok',
      onClick: () => setSyncFilter('ok'),
    },
    {
      label: 'Pending',
      value: 'pending',
      active: syncFilter === 'pending',
      onClick: () => setSyncFilter('pending'),
    },
    {
      label: 'Drift',
      value: 'drift',
      active: syncFilter === 'drift',
      onClick: () => setSyncFilter('drift'),
    },
    {
      label: 'Error',
      value: 'error',
      active: syncFilter === 'error',
      onClick: () => setSyncFilter('error'),
    },
  ]

  return (
    <div>
      <DataTable
        breakpoint="xwide"
        columns={[ownerTypeColumn, ...baseColumns]}
        data={entries}
        loading={loading}
        emptyMessage="No mail addresses found."
        onRowClick={(entry) => setEditEntry(entry)}
        getRowKey={(entry) => entry.id}
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder="Search address…"
        filterSlots={[
          {
            label: 'Type',
            type: 'select',
            selectValue: ownerFilter,
            selectOptions: [
              { value: 'all', label: 'All types' },
              { value: 'member', label: 'Member' },
              { value: 'group', label: 'Group' },
              { value: 'function', label: 'Function' },
            ],
            onSelectChange: (v) => setOwnerFilter(v as OwnerFilter),
          },
          {
            label: 'State',
            type: 'select',
            selectValue: enabledFilter,
            selectOptions: [
              { value: 'all', label: 'All states' },
              { value: 'true', label: 'Enabled' },
              { value: 'false', label: 'Disabled' },
            ],
            onSelectChange: (v) => setEnabledFilter(v as EnabledFilter),
          },
          {
            label: 'Sync',
            type: 'chips',
            filters: syncFilters,
          },
        ]}
        groupBy={{
          getGroup: (entry) => entry.ownerType ?? 'unknown',
          label: (g) => OWNER_LABELS[g] ?? g,
        }}
        toolbar={
          <Button
            variant="subtle"
            onClick={() => refetch()}
            loading={isFetching}
            style={{ padding: '6px 8px' }}
          >
            <IconRefresh size={16} />
          </Button>
        }
      />

      {editEntry && (
        <MailSettingsModal
          entry={editEntry}
          category={
            editEntry.ownerType === 'member'
              ? 'member'
              : editEntry.ownerType === 'group'
                ? 'group'
                : editEntry.ownerType === 'function'
                  ? 'function'
                  : 'system'
          }
          open={editEntry !== null}
          onClose={() => setEditEntry(null)}
          onSaved={() => {
            queryClient.invalidateQueries({ queryKey: ['mail-addresses'] })
            setEditEntry(null)
          }}
          canManage={canManage}
        />
      )}
    </div>
  )
}
