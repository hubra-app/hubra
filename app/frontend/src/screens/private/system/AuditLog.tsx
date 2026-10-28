import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import ReactDOM from 'react-dom'
import { IconX } from '@tabler/icons-react'
import { Select, ActionIcon, Badge } from '@mantine/core'
import { PageHead, Avatar, Tag, DataTable } from '@/components/ui'
import { listAuditLog, getAuditEntry } from '@/api/settings'

/* -- Audit entry detail panel ------------------ */
function AuditEntryDetailPanel({
  entryId,
  onClose,
}: {
  entryId: string
  onClose: () => void
}) {
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
        ? 'Failed to load entry'
        : null

  const formatTime = (iso: string) => {
    try {
      return new Date(iso).toLocaleString(undefined, {
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
              Audit entry #{entryId}
            </div>
            <div
              style={{
                fontSize: 'var(--mantine-font-size-xs)',
                color: '#5e5873',
              }}
            >
              Full event details
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
              Loading…
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
                  Action
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
                  Timestamp
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
                  Actor
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
                          Member ID {detail.actorId}
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
                    Target
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
                          Type
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
                          Label
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
                          ID
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
                  Entry ID
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
const AUDIT_ACTIONS = [
  { value: '', label: 'All actions' },
  { value: 'create_member', label: 'Create member' },
  { value: 'update_member', label: 'Update member' },
  { value: 'delete_member_permanent', label: 'Delete member' },
  { value: 'archive_member', label: 'Archive member' },
  { value: 'approve_application', label: 'Approve application' },
  { value: 'decline_application', label: 'Decline application' },
]
const PAGE_SIZE = 25

export function AuditLogScreen() {
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
        title="Audit log"
        desc={`${total} entr${total === 1 ? 'y' : 'ies'}`}
      />
      <DataTable
        columns={[
          {
            key: 'time',
            header: 'Time',
            render: (entry) => (
              <span
                className="num"
                style={{
                  fontSize: 'var(--mantine-font-size-xs)',
                  color: '#5e5873',
                }}
              >
                {entry.time}
              </span>
            ),
          },
          {
            key: 'actor',
            header: 'Actor',
            render: (entry) => (
              <span style={{ fontWeight: 500 }}>{entry.actor}</span>
            ),
          },
          {
            key: 'action',
            header: 'Action',
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
                  {entry.action}
                </Badge>
              )
            },
          },
          {
            key: 'target',
            header: 'Target',
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
        emptyMessage="No entries."
        onRowClick={(entry) => setSelectedEntryId(entry.id)}
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder="Search audit log…"
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
            data={AUDIT_ACTIONS}
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
