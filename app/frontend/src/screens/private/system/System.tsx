import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useLocation, useNavigate } from 'react-router-dom'
import { IconSearch } from '@tabler/icons-react'
import { Table, TextInput, Paper } from '@mantine/core'
import { useT } from '@/locales/i18n'
import { getSystemPermissions } from '@/api/system'
import { PageHead, Tabs, Pagination, usePagination } from '@/components/ui'
import { RolesTab } from '@/screens/private/system/RolesTab'
import { HealthTab } from '@/screens/private/system/HealthTab'
import { useModules } from '@/modules/useModules'
import { BackupsTab } from '@/screens/private/system/BackupsTab'

const METHOD_STYLES: Record<string, string> = {
  GET: '#1f9d57',
  POST: '#2596be',
  PATCH: '#c2870f',
  PUT: '#c2870f',
  DELETE: '#c0392b',
}

const METHODS = ['All', 'GET', 'POST', 'PATCH', 'PUT', 'DELETE'] as const

function MethodBadge({ method }: { method: string }) {
  const bg = METHOD_STYLES[method.toUpperCase()] ?? '#6b7280'
  return (
    <span
      style={{
        background: bg,
        color: '#fff',
        fontSize: 'var(--mantine-font-size-xs)',
        fontWeight: 600,
        padding: '2px 8px',
        borderRadius: 5,
        letterSpacing: '0.03em',
        display: 'inline-block',
        fontFamily: "'JetBrains Mono', monospace",
      }}
    >
      {method.toUpperCase()}
    </span>
  )
}

export function SystemScreen() {
  const { t } = useT()
  const location = useLocation()
  const navigate = useNavigate()
  const tab =
    location.pathname.replace('/app/system', '').replace('/', '') ||
    'permissions'
  const [search, setSearch] = useState('')
  const [methodFilter, setMethodFilter] = useState<string>('All')

  const {
    data,
    isLoading: loading,
    error: queryError,
  } = useQuery({
    queryKey: ['system-permissions'],
    queryFn: () => getSystemPermissions(),
  })

  const entries = useMemo(() => {
    const raw = data ?? []
    return [...raw].sort((a, b) => {
      if (a.path < b.path) return -1
      if (a.path > b.path) return 1
      return a.method.localeCompare(b.method)
    })
  }, [data])

  const error = useMemo(() => {
    if (!queryError) return null
    const msg: string = queryError instanceof Error ? queryError.message : ''
    if (msg.includes('403') || msg.toLowerCase().includes('forbidden')) {
      return t(
        'system.accessDenied',
        'Kein Zugriff: Admin-Rolle nötig.',
      )
    }
    return t(
      'system.couldNotLoad',
      'Die Berechtigungen konnten nicht geladen werden.',
    )
  }, [queryError, t])

  const filtered = useMemo(() => {
    return entries.filter((e) => {
      if (methodFilter !== 'All' && e.method.toUpperCase() !== methodFilter)
        return false
      if (search) {
        const q = search.toLowerCase()
        if (
          !e.path.toLowerCase().includes(q) &&
          !e.key.toLowerCase().includes(q) &&
          !e.display_name.toLowerCase().includes(q)
        )
          return false
      }
      return true
    })
  }, [entries, methodFilter, search])

  const pg = usePagination(filtered, 25)
  const hasBackups = useModules().has('backups')

  return (
    <div style={{ padding: '0 0 2rem' }}>
      <PageHead title={t('system.title', 'System')} />

      <Tabs
        tabs={[
          { id: 'permissions', label: t('system.permissions', 'Berechtigungen') },
          { id: 'roles', label: t('system.roles', 'Rollen') },
          { id: 'health', label: t('system.healthLabel', 'Systemzustand') },
          ...(hasBackups
            ? [{ id: 'backups', label: t('system.backups', 'Backups') }]
            : []),
        ]}
        activeTab={tab}
        onTabChange={(id) =>
          navigate(`/app/system/${id === 'permissions' ? '' : id}`)
        }
      />

      {tab === 'permissions' && (
        <>
          {loading && (
            <div
              style={{
                marginTop: '1.5rem',
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                color: '#8c86a0',
                fontSize: 'var(--mantine-font-size-sm)',
              }}
            >
              <div
                className="lds-spinner"
                style={{
                  transform: 'scale(0.6)',
                  transformOrigin: 'left center',
                }}
              >
                <div></div>
                <div></div>
                <div></div>
                <div></div>
                <div></div>
                <div></div>
                <div></div>
                <div></div>
                <div></div>
                <div></div>
                <div></div>
                <div></div>
              </div>
              {t('system.loadingPermissions', 'Berechtigungen werden geladen …')}
            </div>
          )}

          {error && !loading && (
            <div
              style={{
                marginTop: '1.5rem',
                padding: '1rem 1.25rem',
                background: '#fff1f2',
                border: '1px solid #fecdd3',
                borderRadius: 8,
                color: '#be123c',
                fontWeight: 500,
              }}
            >
              {error}
            </div>
          )}

          {!loading && !error && (
            <Paper
              withBorder
              shadow="sm"
              radius="lg"
              style={{ marginTop: '1.5rem', marginBottom: 0 }}
            >
              <div
                style={{
                  padding: '14px 16px',
                  borderBottom: '1px solid #d6d2e3',
                  display: 'flex',
                  gap: 10,
                  flexWrap: 'wrap',
                  alignItems: 'center',
                }}
              >
                <TextInput
                  style={{ flex: '1 1 220px' }}
                  leftSection={<IconSearch size={16} />}
                  placeholder={t(
                    'system.searchPlaceholder',
                    'Nach Pfad oder Berechtigung suchen …',
                  )}
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {METHODS.map((m) => (
                    <button
                      key={m}
                      className={`chip${methodFilter === m ? ' on' : ''}`}
                      onClick={() => setMethodFilter(m)}
                    >
                      {m === 'All'
                        ? t('system.allMethods', 'Alle Methoden')
                        : m}
                    </button>
                  ))}
                </div>
                <div
                  style={{
                    marginLeft: 'auto',
                    fontSize: 'var(--mantine-font-size-sm)',
                    color: '#5e5873',
                  }}
                >
                  {filtered.length}{' '}
                  {filtered.length === 1
                    ? t('system.endpoint', 'Endpunkt')
                    : t('system.endpointsPlural', 'Endpunkte')}
                </div>
              </div>

              <Pagination {...pg} top />

              {filtered.length === 0 && !loading && (
                <div
                  style={{
                    padding: '48px 24px',
                    textAlign: 'center',
                    color: '#8c86a0',
                    fontSize: 'var(--mantine-font-size-sm)',
                  }}
                >
                  {entries.length === 0
                    ? t('system.noPermissionsLoaded', 'Keine Berechtigungen geladen.')
                    : t(
                        'system.noEndpointsMatch',
                        'Keine Endpunkte passen zu deinen Filtern.',
                      )}
                </div>
              )}

              {filtered.length > 0 && (
                <div style={{ overflowX: 'auto' }}>
                  <Table highlightOnHover className="responsive-table">
                    <Table.Thead>
                      <Table.Tr>
                        <Table.Th style={{ width: 90 }}>
                          {t('common.method', 'Methode')}
                        </Table.Th>
                        <Table.Th>{t('system.path', 'Pfad')}</Table.Th>
                        <Table.Th>
                          {t('system.permission', 'Berechtigung')}
                        </Table.Th>
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {pg.paged.map((e) => (
                        <Table.Tr key={e.method + ':' + e.path}>
                          <Table.Td data-label={t('common.method', 'Methode')}>
                            <MethodBadge method={e.method} />
                          </Table.Td>
                          <Table.Td
                            data-label={t('system.path', 'Pfad')}
                            style={{
                              fontFamily: "'JetBrains Mono', monospace",
                              fontSize: 'var(--mantine-font-size-sm)',
                              color: '#1a1625',
                            }}
                          >
                            {e.path}
                          </Table.Td>
                          <Table.Td
                            data-label={t('system.permission', 'Berechtigung')}
                            style={{ color: '#5e5873' }}
                          >
                            <div style={{ fontWeight: 600, color: '#2e2940' }}>
                              {e.display_name}
                            </div>
                            <div
                              style={{
                                fontSize: 'var(--mantine-font-size-xs)',
                                fontFamily: "'JetBrains Mono', monospace",
                              }}
                            >
                              {e.key}
                            </div>
                          </Table.Td>
                        </Table.Tr>
                      ))}
                    </Table.Tbody>
                  </Table>
                </div>
              )}

              <Pagination {...pg} />
            </Paper>
          )}
        </>
      )}

      {tab === 'roles' && <RolesTab />}
      {tab === 'health' && <HealthTab />}
      {tab === 'backups' && hasBackups && <BackupsTab />}
    </div>
  )
}
