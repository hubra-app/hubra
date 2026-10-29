import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import ReactDOM from 'react-dom'
import { IconX } from '@tabler/icons-react'
import { Select, ActionIcon, Badge } from '@mantine/core'
import { PageHead, Avatar, Tag, DataTable } from '@/components/ui'
import { listAuditLog, getAuditEntry } from '@/api/settings'
import { useT } from '@/locales/i18n'
import { formatDateTime } from '@/format'

/* -- Audit entry detail panel ------------------ */
function AuditEntryDetailPanel({
  entryId,
  onClose,
}: {
  entryId: string
  onClose: () => void
}) {
  const { t, i18n } = useT()
  const {
    data: detail,
    isLoading: loading,
    error: queryError,
  } = useQuery({
    queryKey: ['audit-entry', entryId],
    queryFn: () => getAuditEntry(entryId),
  })
  const error =
    queryError instanceof Error
      ? queryError.message
      : queryError
        ? t('audit.loadFailed', 'Eintrag konnte nicht geladen werden')
        : null

  const formatTime = (iso: string) => {
    try {
      return new Date(iso).toLocaleString(i18n.language, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        timeZoneName: 'short',
      })
    } catch {
      return iso
    }
  }

  return ReactDOM.createPortal(
    <>
      <div className="scrim" onClick={onClose} />
      <div className="notif-panel open" style={{ width: 420 }}>
        <div
          style={{
            padding: '20px 20px 14px',
            borderBottom: '1px solid #d6d2e3',
            display: 'flex',
            alignItems: 'center',
            gap: 12,
          }}
        >
          <div style={{ flex: 1 }}>
            <div
              style={{
                fontSize: 'var(--mantine-font-size-md)',
                fontWeight: 700,
                color: '#1a1625',
              }}
            >
              {t('audit.entryTitle', 'Eintrag #{{id}}', { id: entryId })}
            </div>
            <div
              style={{
                fontSize: 'var(--mantine-font-size-xs)',
                color: '#5e5873',
              }}
            >
              {t('audit.fullDetails', 'Alle Details zum Ereignis')}
            </div>
          </div>
          <ActionIcon variant="subtle" onClick={onClose}>
            <IconX size={16} />
          </ActionIcon>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '20px 20px' }}>
          {loading && (
            <div
              style={{
                color: '#8c86a0',
                fontSize: 'var(--mantine-font-size-sm)',
              }}
            >
              {t('common.loading', 'Wird geladen …')}
            </div>
          )}
          {error && (
            <div
              style={{
                color: '#c0392b',
                fontSize: 'var(--mantine-font-size-sm)',
              }}
            >
              {error}
            </div>
          )}
          {detail && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              {/* Action */}
              <div>
                <div
                  style={{
                    fontSize: 'var(--mantine-font-size-xs)',
                    fontWeight: 600,
                    color: '#8c86a0',
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    marginBottom: 6,
                  }}
                >
                  {t('audit.action', 'Aktion')}
                </div>
                <Badge
                  variant="light"
                  color="green"
                  radius="xl"
                  style={{
                    fontSize: 'var(--mantine-font-size-sm)',
                    padding: '4px 10px',
                  }}
                >
                  {detail.action.replace(/_/g, ' ')}
                </Badge>
              </div>

              {/* Timestamp */}
              <div>
                <div
                  style={{
                    fontSize: 'var(--mantine-font-size-xs)',
                    fontWeight: 600,
                    color: '#8c86a0',
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    marginBottom: 6,
                  }}
                >
                  {t('audit.timestamp', 'Zeitpunkt')}
                </div>
                <div
                  className="num"
                  style={{
                    fontSize: 'var(--mantine-font-size-sm)',
                    color: '#2e2940',
                  }}
                >
                  {formatTime(detail.time)}
                </div>
              </div>

              {/* Actor */}
              <div>
                <div
                  style={{
                    fontSize: 'var(--mantine-font-size-xs)',
                    fontWeight: 600,
                    color: '#8c86a0',
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    marginBottom: 8,
                  }}
                >
                  {t('audit.actor', 'Person')}
                </div>
                {detail.actorName ? (
                  <div
                    style={{ display: 'flex', alignItems: 'center', gap: 10 }}
                  >
                    <Avatar
                      name={detail.actorName}
                      color={detail.actorAvatarColor}
                      size={32}
                    />
                    <div>
                      <div
                        style={{
                          fontSize: 'var(--mantine-font-size-sm)',
                          fontWeight: 600,
                          color: '#1a1625',
                        }}
                      >
                        {detail.actorName}
                      </div>
                      {detail.actorId != null && (
                        <div
                          style={{
                            fontSize: 'var(--mantine-font-size-xs)',
                            color: '#8c86a0',
                          }}
                        >
                          {t('audit.memberId', 'Mitglied #{{id}}', { id: detail.actorId })}
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <div
                    style={{
                      fontSize: 'var(--mantine-font-size-sm)',
                      color: '#5e5873',
                      fontStyle: 'italic',
                    }}
                  >
                    System (no actor)
                  </div>
                )}
              </div>

              {/* Target */}
              {(detail.targetType || detail.targetLabel) && (
                <div>
                  <div
                    style={{
                      fontSize: 'var(--mantine-font-size-xs)',
                      fontWeight: 600,
                      color: '#8c86a0',
                      textTransform: 'uppercase',
                      letterSpacing: '0.06em',
                      marginBottom: 8,
                    }}
                  >
                    {t('audit.target', 'Ziel')}
                  </div>
                  <div
                    style={{
                      background: '#f4f2f9',
                      borderRadius: 9,
                      padding: '12px 14px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 6,
                    }}
                  >
                    {detail.targetType && (
                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                        }}
                      >
                        <span
                          style={{
                            fontSize: 'var(--mantine-font-size-xs)',
                            color: '#8c86a0',
                          }}
                        >
                          {t('common.type', 'Typ')}
                        </span>
                        <Tag>{detail.targetType}</Tag>
                      </div>
                    )}
                    {detail.targetLabel && (
                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                        }}
                      >
                        <span
                          style={{
                            fontSize: 'var(--mantine-font-size-xs)',
                            color: '#8c86a0',
                          }}
                        >
                          {t('audit.label', 'Bezeichnung')}
                        </span>
                        <span
                          style={{
                            fontSize: 'var(--mantine-font-size-sm)',
                            fontWeight: 600,
                            color: '#1a1625',
                          }}
                        >
                          {detail.targetLabel}
                        </span>
                      </div>
                    )}
                    {detail.targetId != null && (
                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                        }}
                      >
                        <span
                          style={{
                            fontSize: 'var(--mantine-font-size-xs)',
                            color: '#8c86a0',
                          }}
                        >
                          {t('audit.id', 'ID')}
                        </span>
                        <span
                          className="num"
                          style={{
                            fontSize: 'var(--mantine-font-size-xs)',
                            color: '#5e5873',
                          }}
                        >
                          {detail.targetId}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Entry ID */}
              <div style={{ borderTop: '1px solid #e6e3ef', paddingTop: 16 }}>
                <div
                  style={{
                    fontSize: 'var(--mantine-font-size-xs)',
                    fontWeight: 600,
                    color: '#8c86a0',
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    marginBottom: 4,
                  }}
                >
                  {t('audit.entryId', 'Eintrags-ID')}
                </div>
                <span
                  className="num"
                  style={{
                    fontSize: 'var(--mantine-font-size-xs)',
                    color: '#8c86a0',
                  }}
                >
                  #{detail.id}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>
    </>,
    document.body,
  )
}

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
]
const PAGE_SIZE = 25

export function AuditLogScreen() {
  const { t } = useT()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(PAGE_SIZE)
  const [action, setAction] = useState('')
  const [search, setSearch] = useState('')
  const [selectedEntryId, setSelectedEntryId] = useState<string | null>(null)

  const { data, isLoading: loading } = useQuery({
    queryKey: ['audit-log', page, action, pageSize],
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
      <PageHead
        title={t('audit.title', 'Audit-Log')}
        desc={t('audit.entryCount', '{{count}} Einträge', { count: total })}
      />
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
                  color: '#5e5873',
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
                    ? 'cyan'
                    : action.includes('login') || action.includes('logout')
                      ? 'blue'
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
                  color: '#5e5873',
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
        onRowClick={(entry) => setSelectedEntryId(entry.id)}
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
        toolbar={
          <Select
            size="sm"
            data={AUDIT_ACTIONS.map(([value, label]) => ({
              value,
              label: t(`audit.actions.${value || 'all'}`, label),
            }))}
            value={action}
            onChange={(v) => handleActionChange(v ?? '')}
            style={{ width: 200 }}
          />
        }
      />
      {selectedEntryId && (
        <AuditEntryDetailPanel
          entryId={selectedEntryId}
          onClose={() => setSelectedEntryId(null)}
        />
      )}
    </div>
  )
}
