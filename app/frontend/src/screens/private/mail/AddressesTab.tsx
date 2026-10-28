import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { IconRefresh } from '@tabler/icons-react'
import { Button } from '@mantine/core'
import { useAuth } from '@/context/AppContext'
import { useT } from '@/locales/i18n'
import { DataTable } from '@/components/ui'
import { useMailColumns } from '@/screens/private/mail/useMailColumns'
import { MailSettingsModal } from '@/screens/private/mail/MailSettingsModal'
import { listAddresses, listAllAddresses, type ManagedMailAddressInfo } from '@/api/mail'

type OwnerFilter = 'all' | 'member' | 'group' | 'function' | 'system' | 'mail_address'
type EnabledFilter = 'all' | 'true' | 'false'
type SyncFilter = 'all' | 'ok' | 'pending' | 'drift' | 'error'

const OWNER_LABELS: Record<string, [string, string]> = {
  member: ['mail.owner.member', 'Mitglied'],
  group: ['mail.owner.group', 'Gruppe'],
  function: ['mail.owner.function', 'Funktion'],
  mail_address: ['mail.owner.alias', 'Alias'],
  system: ['mail.owner.system', 'System'],
}

const OWNER_COLORS: Record<string, string> = {
  member: '#1f9d57',
  group: '#2596be',
  function: '#7c4dcc',
  mail_address: '#c2870f',
  system: '#e65100',
}

/**
 * Mail address table. ``owned`` lists addresses of members, groups and
 * functions; ``all`` also includes system addresses and aliases.
 */
export function AddressesTab({ scope }: { scope: 'owned' | 'all' }) {
  const { t } = useT()
  const ownerLabel = (type: string) => {
    const l = OWNER_LABELS[type]
    return l ? t(l[0], l[1]) : type
  }
  const isAll = scope === 'all'
  const queryKey = isAll ? 'mail-all-addresses' : 'mail-addresses'
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [ownerFilter, setOwnerFilter] = useState<OwnerFilter>('all')
  const [enabledFilter, setEnabledFilter] = useState<EnabledFilter>('all')
  const [syncFilter, setSyncFilter] = useState<SyncFilter>('all')
  const [editEntry, setEditEntry] = useState<ManagedMailAddressInfo | null>(null)

  const canManage =
    hasPermission('mail.aliases.update') ||
    hasPermission(isAll ? 'mail.aliases.delete' : 'mail.aliases.create')

  const {
    data,
    isLoading: loading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: [queryKey, ownerFilter, enabledFilter, syncFilter, search],
    queryFn: () =>
      (isAll ? listAllAddresses : listAddresses)({
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
    header: t('common.type', 'Typ'),
    render: (entry: ManagedMailAddressInfo) => {
      let label: string
      let color: string
      if (entry.isSystem) {
        label = ownerLabel('system')
        color = OWNER_COLORS.system
      } else if (entry.ownerType === 'mail_address') {
        label = ownerLabel('mail_address')
        color = OWNER_COLORS.mail_address
      } else if (entry.ownerType && OWNER_LABELS[entry.ownerType]) {
        label = ownerLabel(entry.ownerType)
        color = OWNER_COLORS[entry.ownerType] ?? '#5e5873'
      } else {
        label = entry.kind ?? t('mail.owner.other', 'Andere')
        color = '#5e5873'
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
      label: t('mail.sync.all', 'Alle'),
      value: 'all',
      active: syncFilter === 'all',
      onClick: () => setSyncFilter('all'),
    },
    {
      label: t('mail.sync.ok', 'OK'),
      value: 'ok',
      active: syncFilter === 'ok',
      onClick: () => setSyncFilter('ok'),
    },
    {
      label: t('mail.sync.pending', 'Ausstehend'),
      value: 'pending',
      active: syncFilter === 'pending',
      onClick: () => setSyncFilter('pending'),
    },
    {
      label: t('mail.sync.drift', 'Abweichung'),
      value: 'drift',
      active: syncFilter === 'drift',
      onClick: () => setSyncFilter('drift'),
    },
    {
      label: t('mail.sync.error', 'Fehler'),
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
        emptyMessage={t('mail.noAddresses', 'Keine Mail-Adressen gefunden.')}
        onRowClick={(entry) => setEditEntry(entry)}
        getRowKey={(entry) => entry.id}
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder={t('mail.searchAddress', 'Adresse suchen …')}
        filterSlots={[
          {
            label: t('common.type', 'Typ'),
            type: 'select',
            selectValue: ownerFilter,
            selectOptions: [
              { value: 'all', label: t('mail.allTypes', 'Alle Typen') },
              { value: 'member', label: ownerLabel('member') },
              { value: 'group', label: ownerLabel('group') },
              { value: 'function', label: ownerLabel('function') },
              ...(isAll
                ? [
                    { value: 'system', label: ownerLabel('system') },
                    { value: 'mail_address', label: ownerLabel('mail_address') },
                  ]
                : []),
            ],
            onSelectChange: (v) => setOwnerFilter(v as OwnerFilter),
          },
          {
            label: t('mail.state', 'Zustand'),
            type: 'select',
            selectValue: enabledFilter,
            selectOptions: [
              { value: 'all', label: t('mail.allStates', 'Alle') },
              { value: 'true', label: t('common.enabled', 'Aktiviert') },
              { value: 'false', label: t('common.disabled', 'Deaktiviert') },
            ],
            onSelectChange: (v) => setEnabledFilter(v as EnabledFilter),
          },
          {
            label: t('mail.syncLabel', 'Abgleich'),
            type: 'chips',
            filters: syncFilters,
          },
        ]}
        groupBy={{
          getGroup: (entry) => entry.ownerType ?? 'unknown',
          label: (g) => ownerLabel(g),
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
            queryClient.invalidateQueries({ queryKey: ['mail-all-addresses'] })
            setEditEntry(null)
          }}
          canManage={canManage}
        />
      )}
    </div>
  )
}
