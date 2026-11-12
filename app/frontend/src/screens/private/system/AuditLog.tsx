import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Badge } from '@mantine/core'
import { PageHead, DataTable } from '@/components/ui'
import { listAuditLog } from '@/api/settings'
import { useNav } from '@/context/AppContext'
import { useT } from '@/locales/i18n'
import { formatDateTime } from '@/format'
import { qk } from '@/data/keys'

/* -- Audit log --------------------------------- */
const AUDIT_ACTIONS: [string, string][] = [
  ['', 'Alle Aktionen'],
  ['invite_member', 'Mitglied eingeladen'],
  ['accept_invite', 'Einladung angenommen'],
  ['update_member', 'Mitglied geändert'],
  ['delete_member_permanent', 'Mitglied gelöscht'],
  ['soft_delete_member', 'Mitglied entfernt'],
  ['archive_member', 'Mitglied archiviert'],
  ['approve_application', 'Antrag angenommen'],
  ['decline_application', 'Antrag abgelehnt'],
  ['support_session_view', 'Support-Zugriff (ansehen)'],
  ['support_session_change', 'Support-Zugriff (mit Änderungen)'],
  ['support_session_end', 'Support-Zugriff beendet'],
  ['support_session_revoked', 'Support-Zugriff vorzeitig beendet'],
  ['support_access_request', 'Support bittet um Zugriff'],
  ['support_access_approve', 'Support-Zugriff freigegeben'],
  ['support_access_decline', 'Support-Zugriff abgelehnt'],
]
const PAGE_SIZE = 25

/** The audit log; `embedded` leaves out the heading, for a settings tab. */
export function AuditLogScreen({ embedded = false }: { embedded?: boolean }) {
  const { t } = useT()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(PAGE_SIZE)
  const [action, setAction] = useState('')
  const [search, setSearch] = useState('')
  const { go } = useNav()

  const { data, isLoading: loading } = useQuery({
    queryKey: qk.audit.log(page, action, pageSize),
    queryFn: () =>
      listAuditLog({ page, pageSize, action: action || undefined }),
  })

  const entries = data?.entries ?? []
  const total = data?.total ?? 0
  const totalPages = data?.totalPages ?? 1

  const filteredEntries = search.trim()
    ? entries.filter(
        (e) =>
          e.action.toLowerCase().includes(search.toLowerCase()) ||
          (e.actor ?? '').toLowerCase().includes(search.toLowerCase()) ||
          (e.target ?? '').toLowerCase().includes(search.toLowerCase()),
      )
    : entries

  const handleActionChange = (val: string) => {
    setAction(val)
    setPage(1)
  }

  return (
    <div>
      {!embedded && (
        <PageHead
          title={t('audit.title', 'Audit-Log')}
          desc={t('audit.entryCount', '{{count}} Einträge', { count: total })}
        />
      )}
      <DataTable
        columns={[
          {
            key: 'time',
            header: t('audit.time', 'Zeit'),
            render: (entry) => (
              <span
                className="num"
                style={{
                  fontSize: 'var(--mantine-font-size-xs)',
                  color: 'var(--hb-text-2)',
                }}
              >
                {formatDateTime(entry.time)}
              </span>
            ),
          },
          {
            key: 'actor',
            header: t('audit.actor', 'Person'),
            render: (entry) => (
              <span style={{ fontWeight: 500 }}>{entry.actor}</span>
            ),
          },
          {
            key: 'action',
            header: t('audit.action', 'Aktion'),
            render: (entry) => {
              const action = entry.action.toLowerCase()
              const color =
                action.includes('delete') ||
                action.includes('decline') ||
                action.includes('archive')
                  ? 'red'
                  : action.includes('update') || action.includes('rename')
                    ? 'acc'
                    : action.includes('login') || action.includes('logout')
                      ? 'gray'
                      : action.includes('create') || action.includes('approve')
                        ? 'green'
                        : 'gray'
              return (
                <Badge variant="light" color={color} radius="xl">
                  {t(`audit.actions.${entry.action.replace(/ /g, '_')}`, entry.action)}
                </Badge>
              )
            },
          },
          {
            key: 'target',
            header: t('audit.target', 'Ziel'),
            render: (entry) => (
              <span
                style={{
                  color: 'var(--hb-text-2)',
                  fontSize: 'var(--mantine-font-size-sm)',
                }}
              >
                {entry.target}
              </span>
            ),
          },
        ]}
        data={filteredEntries}
        loading={loading}
        emptyMessage={t('audit.empty', 'Keine Einträge.')}
        onRowClick={(entry) => go(`/app/audit-log/${entry.id}`)}
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder={t('audit.search', 'Audit-Log durchsuchen …')}
        page={page}
        perPage={pageSize}
        total={total}
        totalPages={totalPages}
        onPageChange={setPage}
        onPerPageChange={(n) => {
          setPageSize(n)
          setPage(1)
        }}
        getRowKey={(entry) => entry.id}
        filterGroups={[
          {
            key: 'action',
            label: t('audit.action', 'Aktion'),
            value: action,
            defaultValue: '',
            kind: 'select',
            options: AUDIT_ACTIONS.map(([value, label]) => ({
              value,
              label: t(`audit.actions.${value || 'all'}`, label),
            })),
            onChange: handleActionChange,
          },
        ]}
      />
    </div>
  )
}
