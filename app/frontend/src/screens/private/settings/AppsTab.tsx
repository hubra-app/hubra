import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Badge, Button, Checkbox, Group, Modal, Paper, Stack, Text, Title } from '@mantine/core'
import { IconAlertTriangle, IconPlugConnected } from '@tabler/icons-react'
import {
  confirmConnection,
  disconnect,
  getConnection,
  listApps,
  startConnect,
  testConnection,
  type AppProviderInfo,
  type Connection,
} from '@/api/apps'
import { ConfirmModal } from '@/components/ui'
import { useToast } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { formatDateTime } from '@/format'
import { useT } from '@/locales/i18n'
import { PluginSlot } from '@/plugins/slot'

const ERRORS: Record<string, [string, string]> = {
  expired: ['apps.errors.expired', 'Die Verbindung ist abgelaufen oder wurde in einem anderen Browser gestartet. Bitte nochmals verbinden.'],
  cancelled: ['apps.errors.cancelled', 'Verbinden abgebrochen.'],
  taken: ['apps.errors.taken', 'Das ist bereits mit einem anderen Verein verbunden.'],
  failed: ['apps.errors.failed', 'Verbinden fehlgeschlagen. Bitte nochmals versuchen.'],
  disabled: ['apps.errors.disabled', 'Das Modul für diese App ist ausgeschaltet.'],
}

/**
 * Einstellungen › Verbundene Apps: the club's links to outside services
 * (a Discord server), what each may do, and its recent activity. Connecting
 * is a round trip to the service and back, then an explicit confirmation.
 */
export function AppsTab() {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const [params, setParams] = useSearchParams()
  const [connectTo, setConnectTo] = useState<AppProviderInfo | null>(null)
  const [openId, setOpenId] = useState<number | null>(null)
  const [removeTarget, setRemoveTarget] = useState<Connection | null>(null)

  const { data, isLoading } = useQuery({ queryKey: qk.settings.apps, queryFn: listApps })
  const refresh = () => queryClient.invalidateQueries({ queryKey: qk.settings.apps })

  const confirmId = Number(params.get('confirm')) || null
  const pending = data?.connections.find((c) => c.id === confirmId && c.status === 'pending') ?? null

  useEffect(() => {
    const error = params.get('error')
    if (!error) return
    const [key, fallback] = ERRORS[error] ?? ERRORS.failed
    notify('error', t('apps.connectFailed', 'Nicht verbunden'), t(key, fallback))
    params.delete('error')
    params.delete('app')
    setParams(params, { replace: true })
  }, [params, setParams, notify, t])

  const clearConfirm = () => {
    params.delete('confirm')
    params.delete('app')
    setParams(params, { replace: true })
  }

  const remove = async (conn: Connection) => {
    try {
      await disconnect(conn.id)
      notify('success', t('apps.disconnected', 'Getrennt'), conn.label || conn.providerName)
      if (openId === conn.id) setOpenId(null)
      refresh()
    } catch (err) {
      notify('error', t('apps.disconnectFailed', 'Trennen fehlgeschlagen'), (err as Error).message)
    }
  }

  if (isLoading || !data) return null

  const providerOf = (code: string) => data.providers.find((p) => p.code === code)
  const active = data.connections.filter((c) => c.status === 'active')

  return (
    <Stack gap="lg">
      <Text c="dimmed" size="sm">
        {t(
          'apps.intro',
          'Dienste ausserhalb von Hubra, mit denen der Verein verbunden ist, und was sie dürfen. Jede Verbindung wird im Protokoll festgehalten und kann jederzeit getrennt werden.',
        )}
      </Text>

      <Stack gap="sm">
        <Title order={4}>{t('apps.connected', 'Verbunden')}</Title>
        {active.length === 0 && (
          <Text size="sm" c="dimmed">
            {t('apps.none', 'Noch keine App verbunden.')}
          </Text>
        )}
        {active.map((conn) => (
          <ConnectionCard
            key={conn.id}
            conn={conn}
            provider={providerOf(conn.provider)}
            open={openId === conn.id}
            onToggle={() => setOpenId(openId === conn.id ? null : conn.id)}
            onRemove={() => setRemoveTarget(conn)}
          />
        ))}
      </Stack>

      <Stack gap="sm">
        <Title order={4}>{t('apps.available', 'Verfügbar')}</Title>
        {data.providers.length === 0 && (
          <Text size="sm" c="dimmed">
            {t('apps.noProviders', 'Schalte unter «Module & Plugins» ein Modul mit einer App ein, zum Beispiel Discord.')}
          </Text>
        )}
        {data.providers.map((p) => (
          <Paper key={p.code} withBorder radius="md" p="md">
            <Group justify="space-between" wrap="nowrap" align="flex-start">
              <div style={{ minWidth: 0 }}>
                <Text fw={600}>{p.name}</Text>
                <Text size="sm" c="dimmed">
                  {p.description}
                </Text>
                {p.unavailable && (
                  <Text size="xs" c="orange" mt={4}>
                    {p.unavailable}
                  </Text>
                )}
              </div>
              <Button
                leftSection={<IconPlugConnected size={16} />}
                disabled={!!p.unavailable}
                onClick={() => setConnectTo(p)}
                style={{ flexShrink: 0 }}
              >
                {t('apps.connect', 'Verbinden')}
              </Button>
            </Group>
          </Paper>
        ))}
      </Stack>

      {connectTo && <ConnectDialog provider={connectTo} onClose={() => setConnectTo(null)} />}
      {pending && (
        <ConfirmDialog
          conn={pending}
          provider={providerOf(pending.provider)}
          onDone={() => {
            clearConfirm()
            refresh()
          }}
        />
      )}
      <ConfirmModal
        open={removeTarget !== null}
        title={t('apps.disconnectTitle', 'Verbindung trennen?')}
        body={t(
          'apps.disconnectBody',
          'Die App kann danach nichts mehr für den Verein tun. Wo möglich wird sie auch beim Dienst entfernt.',
        )}
        onConfirm={() => {
          if (removeTarget) void remove(removeTarget)
          setRemoveTarget(null)
        }}
        onClose={() => setRemoveTarget(null)}
      />
    </Stack>
  )
}

function scopeLabels(conn: Connection, provider?: AppProviderInfo): string[] {
  return conn.scopes.map((key) => provider?.scopes.find((s) => s.key === key)?.label ?? key)
}

function ConnectionCard({
  conn,
  provider,
  open,
  onToggle,
  onRemove,
}: {
  conn: Connection
  provider?: AppProviderInfo
  open: boolean
  onToggle: () => void
  onRemove: () => void
}) {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const [testing, setTesting] = useState(false)
  const details = useQuery({
    queryKey: qk.settings.appConnection(conn.id),
    queryFn: () => getConnection(conn.id),
    enabled: open,
  })
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: qk.settings.apps })
    void queryClient.invalidateQueries({ queryKey: qk.settings.appConnection(conn.id) })
  }

  const test = async () => {
    setTesting(true)
    try {
      const r = await testConnection(conn.id)
      notify('success', t('apps.testOk', 'Verbindung funktioniert'), r.message)
    } catch (err) {
      notify('error', t('apps.testFailed', 'Test fehlgeschlagen'), (err as Error).message)
    } finally {
      setTesting(false)
      refresh()
    }
  }

  return (
    <Paper withBorder radius="md" p="md">
      <Group justify="space-between" wrap="wrap" gap="sm">
        <div style={{ minWidth: 0 }}>
          <Group gap="xs">
            <Text fw={600}>{conn.label || conn.providerName}</Text>
            <Badge size="sm" variant="light">
              {conn.providerName}
            </Badge>
          </Group>
          <Text size="xs" c="dimmed">
            {t('apps.connectedBy', 'Verbunden von {{name}}', { name: conn.createdBy })}
            {conn.confirmedAt ? ` · ${formatDateTime(conn.confirmedAt)}` : ''}
            {conn.lastUsedAt ? ` · ${t('apps.lastUsed', 'zuletzt aktiv')} ${formatDateTime(conn.lastUsedAt)}` : ''}
          </Text>
          <Text size="xs" c="dimmed">
            {t('apps.allowed', 'Darf')}: {scopeLabels(conn, provider).join(', ') || '–'}
          </Text>
        </div>
        <Group gap="xs">
          <Button variant="default" size="xs" onClick={onToggle}>
            {open ? t('common.close', 'Schliessen') : t('apps.details', 'Details')}
          </Button>
          <Button variant="default" size="xs" loading={testing} onClick={test}>
            {t('apps.test', 'Testen')}
          </Button>
          <Button variant="light" color="red" size="xs" onClick={onRemove}>
            {t('apps.disconnect', 'Trennen')}
          </Button>
        </Group>
      </Group>
      {conn.lastError && (
        <Alert color="red" variant="light" mt="sm" icon={<IconAlertTriangle size={16} />}>
          {conn.lastError}
          {conn.lastErrorAt ? ` (${formatDateTime(conn.lastErrorAt)})` : ''}
        </Alert>
      )}
      {open && details.data && (
        <Stack gap="sm" mt="md">
          <PluginSlot name="apps.connection" props={{ connection: details.data, onChange: refresh }} />
          <Text fw={600} size="sm">
            {t('apps.activity', 'Letzte Aktivität')}
          </Text>
          {(details.data.events ?? []).length === 0 && (
            <Text size="sm" c="dimmed">
              {t('apps.noActivity', 'Noch keine Aktivität.')}
            </Text>
          )}
          {(details.data.events ?? []).map((e, i) => (
            <Group key={i} gap="xs" wrap="nowrap" align="flex-start">
              <Badge size="xs" color={e.ok ? 'green' : 'red'} variant="light" style={{ flexShrink: 0 }}>
                {e.ok ? 'OK' : t('apps.error', 'Fehler')}
              </Badge>
              <Text size="xs" style={{ minWidth: 0 }}>
                {e.at ? formatDateTime(e.at) : ''} · {t(`apps.actions.${e.action}`, e.action)}
                {e.detail ? ` · ${e.detail}` : ''}
              </Text>
            </Group>
          ))}
        </Stack>
      )}
    </Paper>
  )
}

function ConnectDialog({ provider, onClose }: { provider: AppProviderInfo; onClose: () => void }) {
  const { t } = useT()
  const { notify } = useToast()
  const [scopes, setScopes] = useState(provider.scopes.map((s) => s.key))
  const [busy, setBusy] = useState(false)

  const go = async () => {
    setBusy(true)
    try {
      const { url } = await startConnect(provider.code, scopes)
      window.location.assign(url)
    } catch (err) {
      notify('error', t('apps.connectFailed', 'Nicht verbunden'), (err as Error).message)
      setBusy(false)
    }
  }

  return (
    <Modal opened onClose={onClose} title={t('apps.connectTitle', '{{name}} verbinden', { name: provider.name })} centered>
      <Stack gap="md">
        <Text size="sm" c="dimmed">
          {t(
            'apps.connectHint',
            'Du meldest dich gleich beim Dienst an und wählst aus, was verbunden wird. Danach bestätigst du die Verbindung hier.',
          )}
        </Text>
        {provider.scopes.length > 0 && (
          <Stack gap="xs">
            <Text fw={600} size="sm">
              {t('apps.mayDo', 'Was die App darf')}
            </Text>
            {provider.scopes.map((s) => (
              <Checkbox
                key={s.key}
                label={s.label}
                description={s.description}
                checked={scopes.includes(s.key)}
                onChange={(e) =>
                  setScopes((prev) =>
                    e.currentTarget.checked ? [...prev, s.key] : prev.filter((k) => k !== s.key),
                  )
                }
              />
            ))}
          </Stack>
        )}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {t('common.cancel', 'Abbrechen')}
          </Button>
          <Button onClick={go} loading={busy}>
            {t('apps.continue', 'Weiter zu {{name}}', { name: provider.name })}
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}

function ConfirmDialog({
  conn,
  provider,
  onDone,
}: {
  conn: Connection
  provider?: AppProviderInfo
  onDone: () => void
}) {
  const { t } = useT()
  const { notify } = useToast()
  const [busy, setBusy] = useState(false)

  const confirm = async () => {
    setBusy(true)
    try {
      await confirmConnection(conn.id)
      notify('success', t('apps.connectedOk', 'Verbunden'), conn.label || conn.providerName)
    } catch (err) {
      notify('error', t('apps.connectFailed', 'Nicht verbunden'), (err as Error).message)
    } finally {
      setBusy(false)
      onDone()
    }
  }

  const cancel = async () => {
    try {
      await disconnect(conn.id)
    } finally {
      onDone()
    }
  }

  return (
    <Modal opened onClose={cancel} title={t('apps.confirmTitle', 'Verbindung bestätigen')} centered>
      <Stack gap="md">
        <Text size="sm">
          {t('apps.confirmBody', '{{provider}} «{{label}}» mit dem Verein verbinden?', {
            provider: conn.providerName,
            label: conn.label,
          })}
        </Text>
        <div>
          <Text fw={600} size="sm">
            {t('apps.mayDo', 'Was die App darf')}
          </Text>
          {scopeLabels(conn, provider).map((label) => (
            <Text key={label} size="sm">
              • {label}
            </Text>
          ))}
        </div>
        <Group justify="flex-end">
          <Button variant="default" onClick={cancel}>
            {t('common.cancel', 'Abbrechen')}
          </Button>
          <Button onClick={confirm} loading={busy}>
            {t('apps.confirm', 'Bestätigen')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}
