import { useState } from 'react'
import { Badge, Button, Group, Paper, Text, TextInput } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { IconDeviceDesktop, IconPencil, IconTrash } from '@tabler/icons-react'
import * as authApi from '@/api/auth'
import type { DeviceInfo } from '@/api/auth'
import { useToast } from '@/context/AppContext'
import { Pagination, usePagination } from '@/components/ui'
import { useT } from '@/locales/i18n'

export function AccountSettingsDevicesTab() {
  const { t } = useT()
  const queryClient = useQueryClient()
  const { notify } = useToast()

  const [revokingDeviceId, setRevokingDeviceId] = useState<number | null>(null)
  const [editingDeviceId, setEditingDeviceId] = useState<number | null>(null)
  const [editDeviceName, setEditDeviceName] = useState('')
  const [savingDeviceNameId, setSavingDeviceNameId] = useState<number | null>(
    null,
  )

  const devicesQuery = useQuery({
    queryKey: ['devices'],
    queryFn: () => authApi.getDevices(),
  })
  const devices = devicesQuery.data ?? []
  const devicesLoading = devicesQuery.isLoading
  const devicesPg = usePagination(devices, 10)

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
            {t('account.devices', 'Geräte')}
          </Text>
        </Group>
        <div style={{ padding: '4px 0' }}>
          {devicesLoading && (
            <div
              style={{
                padding: '20px 24px',
                fontSize: 'var(--mantine-font-size-sm)',
                color: 'var(--mantine-color-ink-3)',
              }}
            >
              {t('account.loadingDevices', 'Geräte werde glade?')}
            </div>
          )}
          {!devicesLoading && devices.length === 0 && (
            <div
              style={{
                padding: '20px 24px',
                fontSize: 'var(--mantine-font-size-sm)',
                color: 'var(--mantine-color-ink-3)',
              }}
            >
              {t('account.noDevices', 'Keini Geräte gfunde.')}
            </div>
          )}
          {devicesPg.paged.map((d: DeviceInfo) => (
            <div
              key={d.id}
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
                  {editingDeviceId === d.id ? (
                    <TextInput
                      autoFocus
                      value={editDeviceName}
                      onChange={(e) => setEditDeviceName(e.target.value)}
                      onKeyDown={async (e) => {
                        if (e.key === 'Enter') {
                          setSavingDeviceNameId(d.id)
                          try {
                            await authApi.renameDevice(
                              d.id,
                              editDeviceName || null,
                            )
                            queryClient.invalidateQueries({
                              queryKey: ['devices'],
                            })
                          } catch {
                            notify('error', t('common.error', 'Fehler'))
                          }
                          setSavingDeviceNameId(null)
                          setEditingDeviceId(null)
                        } else if (e.key === 'Escape') {
                          setEditingDeviceId(null)
                        }
                      }}
                      disabled={savingDeviceNameId === d.id}
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
                        setEditingDeviceId(d.id)
                        setEditDeviceName(d.name ?? '')
                      }}
                      title={t('account.editName', 'Name bearbeite')}
                    >
                      {d.name ||
                        `${d.browserFamily} on ${d.platform}` ||
                        t('account.unknownDevice', 'Unbekannts Grät')}
                    </span>
                  )}
                  {editingDeviceId !== d.id && (
                    <button
                      onClick={() => {
                        setEditingDeviceId(d.id)
                        setEditDeviceName(d.name ?? '')
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
                  <Badge variant="light" radius="xl" size="sm" color="blue">
                    {d.browserFamily}
                  </Badge>
                  <Badge variant="light" radius="xl" size="sm" color="gray">
                    {d.platform}
                  </Badge>
                  {d.activeSessionCount > 0 && (
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
                      {d.activeSessionCount} {t('account.active', 'aktiv')}
                    </span>
                  )}
                </div>
                <div
                  style={{
                    fontSize: 'var(--mantine-font-size-xs)',
                    color: 'var(--mantine-color-ink-4)',
                  }}
                >
                  {d.lastSeenAt && (
                    <span>
                      {t('account.lastSeen', 'Zletscht gseh')}:{' '}
                      {new Date(d.lastSeenAt).toLocaleString()}
                    </span>
                  )}
                </div>
              </div>
              {d.activeSessionCount > 0 && (
                <Button
                  size="sm"
                  variant="default"
                  onClick={async () => {
                    setRevokingDeviceId(d.id)
                    try {
                      await authApi.revokeDeviceSessions(d.id)
                      queryClient.invalidateQueries({
                        queryKey: ['devices'],
                      })
                      queryClient.invalidateQueries({
                        queryKey: ['sessions'],
                      })
                      notify(
                        'success',
                        t('account.sessions.revoked', 'Sitzung beendet'),
                      )
                    } catch {
                      notify('error', t('common.error', 'Fehler'))
                    }
                    setRevokingDeviceId(null)
                  }}
                  disabled={revokingDeviceId === d.id}
                  style={{
                    color: 'var(--mantine-color-red-7)',
                    flexShrink: 0,
                    marginLeft: 12,
                  }}
                >
                  <IconTrash size={16} />
                  {revokingDeviceId === d.id
                    ? t('account.revoking', 'Wird beendet?')
                    : t('account.revokeAll', 'All beende')}
                </Button>
              )}
            </div>
          ))}
        </div>
      </Paper>

      {devices.length > 0 && (
        <Pagination
          page={devicesPg.page}
          perPage={devicesPg.perPage}
          total={devicesPg.total}
          totalPages={devicesPg.totalPages}
          goPage={devicesPg.goPage}
          setPerPage={devicesPg.setPerPage}
        />
      )}
    </>
  )
}
