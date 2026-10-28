import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Button } from '@mantine/core'
import { IconRefresh } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useData } from '@/context/AppContext'
import { Card, LoadingSpinner } from '@/components/ui'
import { getHealthDetailed, getChangelog, getVersion } from '@/api/system'

const SERVICE_LABELS: Record<string, string> = {
  db: 'Database',
  redis: 'Redis',
  smtp: 'SMTP',
  imap: 'IMAP',
}

function statusColor(status: string): string {
  if (status === 'ok') return '#1f9d57'
  if (status === 'degraded') return '#c2870f'
  return '#e53e3e'
}

export function HealthTab() {
  const { t } = useT()
  const { backendOnline } = useData()
  const [showRaw, setShowRaw] = useState(false)

  const healthQuery = useQuery({
    queryKey: ['health-detailed'],
    queryFn: () => getHealthDetailed(),
  })
  const changelogQuery = useQuery({
    queryKey: ['changelog'],
    queryFn: () => getChangelog(),
  })
  const versionQuery = useQuery({
    queryKey: ['version'],
    queryFn: () => getVersion(),
    enabled: healthQuery.isError,
  })

  const health = healthQuery.data ?? null
  const changelog = changelogQuery.data ?? null
  const version = health?.version ?? versionQuery.data?.version ?? null
  const loading = healthQuery.isLoading || changelogQuery.isLoading

  if (loading) {
    return <LoadingSpinner compact message={t('system.loadingHealth', 'Status wird geladen …')} />
  }

  const overallStatus = health?.status ?? (backendOnline ? 'ok' : 'error')
  const displayVersion = version ?? t('system.health.unknown', 'Unbekannt')

  return (
    <div
      style={{
        marginTop: '1.5rem',
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
      }}
    >
      {/* ── Section A: Summary ─────────────────────────────────────── */}
      <Card>
        <Card.Header title={t('system.health.title', 'Systemzustand')}>
          <Button
            variant="subtle"
            size="sm"
            leftSection={<IconRefresh size={14} />}
            onClick={() => {
              healthQuery.refetch()
              changelogQuery.refetch()
            }}
            loading={healthQuery.isFetching || changelogQuery.isFetching}
          >
            {t('common.refresh', 'Aktualisieren')}
          </Button>
        </Card.Header>
        <div style={{ padding: '16px 20px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: '8px 0',
                borderBottom: '1px solid #f0f0f0',
              }}
            >
              <div
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: '50%',
                  background: statusColor(overallStatus),
                  flexShrink: 0,
                }}
              />
              <span
                style={{
                  fontSize: 'var(--mantine-font-size-sm)',
                  color: '#5e5873',
                  minWidth: 140,
                }}
              >
                {t('system.health.status', 'Status')}
              </span>
              <span
                style={{
                  fontSize: 'var(--mantine-font-size-sm)',
                  fontWeight: 600,
                  color: '#1a1625',
                  textTransform: 'capitalize',
                }}
              >
                {overallStatus}
              </span>
            </div>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: '8px 0',
                borderBottom: '1px solid #f0f0f0',
              }}
            >
              <div
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: '50%',
                  background: backendOnline ? '#1f9d57' : '#e53e3e',
                  flexShrink: 0,
                }}
              />
              <span
                style={{
                  fontSize: 'var(--mantine-font-size-sm)',
                  color: '#5e5873',
                  minWidth: 140,
                }}
              >
                {t('system.health.backend', 'Backend')}
              </span>
              <span
                style={{
                  fontSize: 'var(--mantine-font-size-sm)',
                  fontWeight: 600,
                  color: '#1a1625',
                }}
              >
                {backendOnline
                  ? t('system.health.online', 'Online')
                  : t('system.health.offline', 'Offline')}
              </span>
            </div>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: '8px 0',
              }}
            >
              <div
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: '50%',
                  background: '#5e5873',
                  flexShrink: 0,
                }}
              />
              <span
                style={{
                  fontSize: 'var(--mantine-font-size-sm)',
                  color: '#5e5873',
                  minWidth: 140,
                }}
              >
                {t('system.health.version', 'Backend-Version')}
              </span>
              <span
                style={{
                  fontSize: 'var(--mantine-font-size-sm)',
                  fontWeight: 600,
                  color: '#1a1625',
                  fontFamily: "'JetBrains Mono', monospace",
                }}
              >
                {displayVersion}
              </span>
            </div>
          </div>
        </div>
      </Card>

      {/* ── Section B: Service Breakdown ───────────────────────────── */}
      <Card>
        <Card.Header title={t('system.health.services', 'Dienste')} />
        <div style={{ padding: '16px 20px' }}>
          {health ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {Object.entries(health.services).map(([key, svc]) => (
                <div
                  key={key}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12,
                    padding: '8px 0',
                    borderBottom: '1px solid #f0f0f0',
                  }}
                >
                  <div
                    style={{
                      width: 10,
                      height: 10,
                      borderRadius: '50%',
                      background: svc.ok ? '#1f9d57' : '#e53e3e',
                      flexShrink: 0,
                    }}
                  />
                  <span
                    style={{
                      fontSize: 'var(--mantine-font-size-sm)',
                      color: '#5e5873',
                      minWidth: 160,
                    }}
                  >
                    {SERVICE_LABELS[key] ?? key}
                  </span>
                  <span
                    style={{
                      fontSize: 'var(--mantine-font-size-sm)',
                      fontWeight: 600,
                      color: svc.ok ? '#1f9d57' : '#e53e3e',
                    }}
                  >
                    {svc.ok ? 'OK' : 'FAIL'}
                  </span>
                  <span
                    style={{
                      fontSize: 'var(--mantine-font-size-xs)',
                      color: '#8c86a0',
                      fontFamily: "'JetBrains Mono', monospace",
                    }}
                  >
                    {svc.latency_ms}ms
                  </span>
                  {svc.error && (
                    <span
                      style={{
                        fontSize: 'var(--mantine-font-size-xs)',
                        color: '#e53e3e',
                        marginLeft: 'auto',
                        textAlign: 'right',
                      }}
                    >
                      {svc.error}
                    </span>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div
              style={{
                fontSize: 'var(--mantine-font-size-sm)',
                color: '#8c86a0',
                padding: '8px 0',
              }}
            >
              {t(
                'system.health.adminRequired',
                'Ausführliche Dienstprüfungen brauchen die Admin-Rolle.',
              )}
            </div>
          )}
        </div>
      </Card>

      {/* ── Section C: Changelog ───────────────────────────────────── */}
      <Card>
        <Card.Header title={t('system.health.changelog', 'Änderungshistorie')} />
        <div style={{ padding: '16px 20px' }}>
          {changelog && changelog.entries.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              {changelog.entries.map((entry) => (
                <div key={entry.version}>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      marginBottom: 8,
                    }}
                  >
                    <span
                      style={{
                        fontSize: 'var(--mantine-font-size-sm)',
                        fontWeight: 700,
                        color: '#1a1625',
                      }}
                    >
                      v{entry.version}
                    </span>
                    {entry.date && (
                      <span
                        style={{
                          fontSize: 'var(--mantine-font-size-xs)',
                          color: '#8c86a0',
                        }}
                      >
                        {entry.date}
                      </span>
                    )}
                    {entry.version.toLowerCase() === 'unreleased' && (
                      <span
                        style={{
                          fontSize: 'var(--mantine-font-size-xs)',
                          fontWeight: 600,
                          color: '#c2870f',
                          background: '#fef9e7',
                          borderRadius: 4,
                          padding: '1px 6px',
                        }}
                      >
                        {t('system.health.unreleased', 'Unveröffentlicht')}
                      </span>
                    )}
                  </div>
                  {Object.entries(entry.sections).map(([section, items]) => (
                    <div
                      key={section}
                      style={{ marginLeft: 12, marginBottom: 8 }}
                    >
                      <div
                        style={{
                          fontSize: 'var(--mantine-font-size-xs)',
                          fontWeight: 600,
                          color: '#5e5873',
                          textTransform: 'uppercase',
                          letterSpacing: '0.04em',
                          marginBottom: 4,
                        }}
                      >
                        {section}
                      </div>
                      <ul
                        style={{
                          margin: 0,
                          paddingLeft: 18,
                          display: 'flex',
                          flexDirection: 'column',
                          gap: 2,
                        }}
                      >
                        {items.map((item, i) => (
                          <li
                            key={item + i}
                            style={{
                              fontSize: 'var(--mantine-font-size-sm)',
                              color: '#2e2940',
                              lineHeight: 1.5,
                            }}
                          >
                            {item}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                  {Object.keys(entry.sections).length === 0 && (
                    <div
                      style={{
                        fontSize: 'var(--mantine-font-size-xs)',
                        color: '#8c86a0',
                        marginLeft: 12,
                      }}
                    >
                      {t('system.health.noEntries', 'Keine Änderungen dokumentiert.')}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div
              style={{
                fontSize: 'var(--mantine-font-size-sm)',
                color: '#8c86a0',
              }}
            >
              {t('system.health.noData', 'Keine Daten verfügbar.')}
            </div>
          )}
        </div>
      </Card>

      {/* ── Section D: Raw Health Data ─────────────────────────────── */}
      {health && (
        <Card>
          <Card.Header
            title={t('system.health.rawData', 'Rohdaten')}
            style={{ cursor: 'pointer', userSelect: 'none' }}
          >
            <button
              onClick={() => setShowRaw((v) => !v)}
              style={{
                background: 'none',
                border: '1px solid #e6e3ef',
                borderRadius: 6,
                padding: '2px 10px',
                fontSize: 'var(--mantine-font-size-xs)',
                color: '#5e5873',
                cursor: 'pointer',
              }}
            >
              {showRaw
                ? t('system.health.hideRaw', 'Ausblenden')
                : t('system.health.showRaw', 'Anzeigen')}
            </button>
          </Card.Header>
          {showRaw && (
            <div style={{ padding: '16px 20px' }}>
              <pre
                style={{
                  margin: 0,
                  padding: 12,
                  background: '#f9f8fc',
                  borderRadius: 8,
                  border: '1px solid #e6e3ef',
                  fontSize: 'var(--mantine-font-size-xs)',
                  fontFamily: "'JetBrains Mono', monospace",
                  color: '#2e2940',
                  overflowX: 'auto',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                }}
              >
                {JSON.stringify(health, null, 2)}
              </pre>
            </div>
          )}
        </Card>
      )}
    </div>
  )
}
