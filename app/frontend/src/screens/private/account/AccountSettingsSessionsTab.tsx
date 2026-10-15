import { useState } from 'react'
import { Button, Group, Paper, Text, TextInput } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  IconDeviceDesktop,
  IconPencil,
  IconTrash,
  IconLogout as Leave,
} from '@tabler/icons-react'
import * as authApi from '@/api/auth'
import type { SessionInfo } from '@/api/auth'
import { useToast } from '@/context/AppContext'
import { Pagination, Toggle, usePagination } from '@/components/ui'
import { useT } from '@/locales/i18n'

export function AccountSettingsSessionsTab() {
  const { t } = useT()
  const queryClient = useQueryClient()
  const { notify } = useToast()

  const [revokingId, setRevokingId] = useState<number | null>(null)
  const [revokeAllLoading, setRevokeAllLoading] = useState(false)
  const [editingSessionId, setEditingSessionId] = useState<number | null>(null)
  const [editSessionName, setEditSessionName] = useState('')
  const [savingNameId, setSavingNameId] = useState<number | null>(null)
  const [showRevoked, setShowRevoked] = useState(false)

  const sessionsQuery = useQuery({
    queryKey: ['sessions', showRevoked],
    queryFn: () => authApi.getSessions(showRevoked),
  })
  const sessions = sessionsQuery.data ?? []
  const sessionsLoading = sessionsQuery.isLoading
  const sessionsPg = usePagination(sessions, 10)

  const handleRevokeSession = async (sessionId: number) => {
    setRevokingId(sessionId)
    try {
      await authApi.revokeSession(sessionId)
      queryClient.invalidateQueries({ queryKey: ['sessions'] })
      notify(
        'success',
        t('account.sessions.revoked', 'Sitzung beendet'),
        t(
          'account.sessions.revokedMsg',
          'D Sitzung isch erfolgreich beendet worde.',
        ),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error', 'Fehler'),
        err instanceof Error
          ? err.message
          : t(
              'account.couldNotRevokeSession',
              'Sitzung chunt nöd beendet wärde.',
            ),
      )
    } finally {
      setRevokingId(null)
    }
  }

  const handleRenameSession = async (sessionId: number) => {
    const name = editSessionName.trim() || null
    setSavingNameId(sessionId)
    try {
      await authApi.renameSession(sessionId, name)
      queryClient.invalidateQueries({ queryKey: ['sessions'] })
      setEditingSessionId(null)
      notify(
        'success',
        t('account.sessions.renamed', 'Sitzig umbenennt'),
        name ?? t('account.nameCleared', 'Name glöscht'),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('account.renameFailed', 'Umbenenne fählgschlage'),
        err instanceof Error ? err.message : 'Unknown error',
      )
    } finally {
      setSavingNameId(null)
    }
  }

  const handleRevokeAll = async () => {
    setRevokeAllLoading(true)
    try {
      const result = await authApi.revokeAllSessions(false)
      queryClient.invalidateQueries({ queryKey: ['sessions'] })
      notify(
        'success',
        t('account.allOtherSessionsRevoked', 'Anderi Sitzungen beendet'),
        t(
          'account.allOtherSessionsRevokedMsg',
          `${result.revoked} Sitzung(e) beendet.`,
        ),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error', 'Fehler'),
        err instanceof Error
          ? err.message
          : t(
              'account.couldNotRevokeAll',
              'Sitzungen chented nöd beendet wärde.',
            ),
      )
    } finally {
      setRevokeAllLoading(false)
    }
  }

  return (
    <>
      <Paper withBorder shadow="sm" radius="lg">
        <Group
          p="md"
          gap="sm"
          style={{
            borderBottom: '1px solid var(--mantine-color-gray-3)',
          }}
        >
          <IconDeviceDesktop
            size={16}
            style={{ color: 'var(--mantine-color-ink-4)' }}
          />
          <Text fw={700} fz="md">
            {t('account.activeSessions', 'Aktivi Sitzunge')}
          </Text>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Toggle checked={showRevoked} onChange={(v) => setShowRevoked(v)} />
            <Text fz="xs" c="dimmed">
              {t('account.showRevoked', 'Beendeti zeige')}
            </Text>
          </div>
        </Group>
        <div style={{ padding: '4px 0' }}>
          {sessionsLoading && (
            <div
              style={{
                padding: '20px 24px',
                fontSize: 'var(--mantine-font-size-sm)',
                color: 'var(--mantine-color-ink-3)',
              }}
            >
              {t('account.loadingSessions', 'Sitzunge werde glade…')}
            </div>
          )}
          {!sessionsLoading && sessions.length === 0 && (
            <div
              style={{
                padding: '20px 24px',
                fontSize: 'var(--mantine-font-size-sm)',
                color: 'var(--mantine-color-ink-3)',
              }}
            >
              {t('account.noSessions', 'Kei aktivi Sitzunge gfunde.')}
            </div>
          )}
          {sessionsPg.paged.map((s: SessionInfo) => (
            <div
              key={s.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '14px 24px',
                borderBottom: '1px solid #f0f4f1',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 3,
                  flex: 1,
                  minWidth: 0,
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                  }}
                >
                  {editingSessionId === s.id ? (
                    <TextInput
                      autoFocus
                      value={editSessionName}
                      onChange={(e) => setEditSessionName(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          handleRenameSession(s.id)
                        } else if (e.key === 'Escape') {
                          setEditingSessionId(null)
                        }
                      }}
                      onBlur={() => handleRenameSession(s.id)}
                      disabled={savingNameId === s.id}
                      placeholder={t(
                        'account.sessions.namePlaceholder',
                        'Mis Grät',
                      )}
                      style={{
                        height: 28,
                        fontSize: 'var(--mantine-font-size-sm)',
                        padding: '0 8px',
                        maxWidth: 240,
                        minWidth: 140,
                      }}
                      onClick={(e) => e.stopPropagation()}
                    />
                  ) : (
                    <span
                      style={{
                        fontSize: 'var(--mantine-font-size-sm)',
                        fontWeight: 500,
                        color: 'var(--mantine-color-ink-8)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        cursor: 'pointer',
                      }}
                      onClick={() => {
                        setEditingSessionId(s.id)
                        setEditSessionName(s.deviceName ?? '')
                      }}
                      title={t('account.editName', 'Name bearbeite')}
                    >
                      {s.deviceName ||
                        `${s.browserFamily} on ${s.platform}` ||
                        s.userAgent ||
                        t('account.unknownDevice', 'Unbekannts Grät')}
                    </span>
                  )}
                  {editingSessionId !== s.id && (
                    <button
                      onClick={() => {
                        setEditingSessionId(s.id)
                        setEditSessionName(s.deviceName ?? '')
                      }}
                      style={{
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                        color: 'var(--mantine-color-ink-3)',
                        padding: 0,
                        lineHeight: 1,
                        display: 'flex',
                        alignItems: 'center',
                      }}
                      title={t('account.editName', 'Name bearbeite')}
                    >
                      <IconPencil size={11} />
                    </button>
                  )}
                  {s.current && (
                    <span
                      style={{
                        fontSize: 'var(--mantine-font-size-xs)',
                        fontWeight: 600,
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em',
                        color: 'var(--mantine-color-green-7)',
                        background: 'rgba(26,127,55,.08)',
                        padding: '2px 7px',
                        borderRadius: 4,
                      }}
                    >
                      {t('account.currentSession', 'Aktuell')}
                    </span>
                  )}
                  {s.createReason && !s.current && !s.revokedAt && (
                    <span
                      style={{
                        fontSize: 'var(--mantine-font-size-xs)',
                        fontWeight: 500,
                        color: 'var(--mantine-color-acc-6)',
                        background: 'var(--mantine-color-acc-0)',
                        padding: '2px 7px',
                        borderRadius: 4,
                      }}
                    >
                      {s.createReason === 'new_device'
                        ? t('account.reasonNewDevice', 'Neus Grät')
                        : s.createReason === 'new_ip'
                          ? t('account.reasonNewIp', 'Neui IP')
                          : s.createReason === 'new_ua'
                            ? t('account.reasonNewUa', 'Neuer Browser')
                            : s.createReason === 'session_expired'
                              ? t('account.reasonExpired', 'Sitzig abgloffe')
                              : s.createReason === 'first_login'
                                ? t(
                                    'account.reasonFirstLogin',
                                    'Ersti Aameldig',
                                  )
                                : s.createReason}
                    </span>
                  )}
                  {s.revokedAt && !s.current && (
                    <span
                      style={{
                        fontSize: 'var(--mantine-font-size-xs)',
                        fontWeight: 600,
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em',
                        color: 'var(--mantine-color-ink-3)',
                        background: 'var(--mantine-color-surface-1)',
                        padding: '2px 7px',
                        borderRadius: 4,
                      }}
                    >
                      {t('account.revoked', 'Beendet')}
                    </span>
                  )}
                </div>
                <div
                  style={{
                    fontSize: 'var(--mantine-font-size-xs)',
                    color: 'var(--mantine-color-ink-4)',
                  }}
                >
                  {s.ipAddress || '?'}
                  {s.lastActiveAt && (
                    <span>
                      {' ? '}
                      {t('account.lastActive', 'Zletscht aktiv')}:{' '}
                      {new Date(s.lastActiveAt).toLocaleString()}
                    </span>
                  )}
                </div>
              </div>
              {!s.current && !s.revokedAt && (
                <Button
                  size="sm"
                  variant="default"
                  onClick={() => handleRevokeSession(s.id)}
                  disabled={revokingId === s.id}
                  style={{
                    color: 'var(--mantine-color-red-7)',
                    flexShrink: 0,
                    marginLeft: 12,
                  }}
                >
                  <IconTrash size={16} />
                  {revokingId === s.id
                    ? t('account.revoking', 'Wird beendet…')
                    : t('account.revoke', 'Beende')}
                </Button>
              )}
            </div>
          ))}
        </div>
      </Paper>

      <div
        style={{
          display: 'flex',
          justifyContent: 'flex-end',
        }}
      >
        <Button
          variant="default"
          onClick={handleRevokeAll}
          disabled={
            revokeAllLoading ||
            sessions.filter((s: SessionInfo) => !s.current && !s.revokedAt)
              .length === 0
          }
          style={{ color: 'var(--mantine-color-red-7)' }}
        >
          <Leave size={16} />
          {revokeAllLoading
            ? t('account.revoking', 'Wird beendet…')
            : t('account.revokeAllOthers', 'Alli andere Sitzige beende')}
        </Button>
      </div>

      <div
        style={{
          padding: '14px 20px',
          background: 'var(--mantine-color-surface-1)',
          borderRadius: 10,
          fontSize: 'var(--mantine-font-size-sm)',
          color: 'var(--mantine-color-ink-4)',
        }}
      >
        {t(
          'account.sessionsInfo',
          'Verwalte dini aktive Sitzige. Wemmer e Sitzig beendet, wird die sofort ungültig.',
        )}
      </div>

      {sessions.length > 0 && (
        <Pagination
          page={sessionsPg.page}
          perPage={sessionsPg.perPage}
          total={sessionsPg.total}
          totalPages={sessionsPg.totalPages}
          goPage={sessionsPg.goPage}
          setPerPage={sessionsPg.setPerPage}
        />
      )}
    </>
  )
}
