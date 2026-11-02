import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Badge,
  Button,
  Checkbox,
  Group,
  Paper,
  Select,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { IconTool } from '@tabler/icons-react'
import { useAdmin } from '@/context/AdminContext'
import { formatDateTime } from '@/format'
import { tr } from '@/lang'
import {
  getAlertSwitches,
  setMaintenance,
  updateAlertSwitches,
  type AlertType,
  type Maintenance,
  type NotifyChannel,
} from '@/api/platform'
import { ALERT_TYPES, PLATFORM_EVENTS } from './eventLabels'

const CHANNEL_LABEL: Record<NotifyChannel, () => string> = {
  mail: () => tr('Mail', 'Mail'),
  discord: () => 'Discord',
}

const failure = (err: unknown) => (err instanceof Error ? err.message : undefined)

/** Maintenance mode: club apps show a notice and their API answers 503,
 * manage keeps working, alerts pause. */
export function MaintenanceCard({ state }: { state: Maintenance | undefined }) {
  const { notify, hasGlobalPermission } = useAdmin()
  const queryClient = useQueryClient()
  const canChange = hasGlobalPermission('platform.settings')
  const [message, setMessage] = useState('')
  const [minutes, setMinutes] = useState<string>('30')
  const [busy, setBusy] = useState(false)

  const change = async (on: boolean) => {
    setBusy(true)
    try {
      await setMaintenance(
        on
          ? { on, message: message.trim(), minutes: minutes === '0' ? null : Number(minutes) }
          : { on },
      )
      await queryClient.invalidateQueries({ queryKey: ['alerts-overview'] })
      await queryClient.invalidateQueries({ queryKey: ['maintenance'] })
      notify(
        'success',
        on
          ? tr('Wartungsmodus an', 'Maintenance mode on')
          : tr('Wartungsmodus aus', 'Maintenance mode off'),
      )
    } catch (err) {
      notify('error', tr('Nicht geändert', 'Not changed'), failure(err))
    } finally {
      setBusy(false)
    }
  }

  const active = !!state?.active
  return (
    <Paper
      withBorder
      shadow="sm"
      radius="lg"
      p="lg"
      style={active ? { borderColor: 'var(--mantine-color-orange-5)' } : undefined}
    >
      <Group justify="space-between" mb={6} wrap="wrap">
        <Group gap={10}>
          <IconTool size={20} />
          <Title order={4}>{tr('Wartungsmodus', 'Maintenance mode')}</Title>
          {active ? (
            <Badge color="orange" variant="light">
              {tr('An', 'On')}
            </Badge>
          ) : (
            <Badge color="gray" variant="light">
              {tr('Aus', 'Off')}
            </Badge>
          )}
        </Group>
        {active && canChange && (
          <Button color="orange" variant="light" loading={busy} onClick={() => change(false)}>
            {tr('Wartung beenden', 'End maintenance')}
          </Button>
        )}
      </Group>
      <Text size="sm" c="dimmed" mb={active || !canChange ? 0 : 12}>
        {active
          ? tr(
              `Die Vereins-Apps zeigen einen Wartungshinweis${state?.until ? ` bis ${formatDateTime(state.until)}` : ''}. manage, Anmeldung und Konto laufen weiter. Warnungen sind pausiert.`,
              `Club apps show a maintenance notice${state?.until ? ` until ${formatDateTime(state.until)}` : ''}. manage, sign-in and accounts keep working. Alerts are paused.`,
            )
          : tr(
              'Für Updates: Die Vereins-Apps zeigen einen Hinweis statt Fehlern, und Warnungen pausieren. Beim Deploy auch mit «flask maintenance on --minutes 15».',
              'For updates: club apps show a notice instead of errors, and alerts pause. For a deploy also with "flask maintenance on --minutes 15".',
            )}
      </Text>
      {active && state?.message && (
        <Text size="sm" mt={6}>
          «{state.message}»
        </Text>
      )}
      {!active && canChange && (
        <Group align="flex-end" wrap="wrap">
          <TextInput
            label={tr('Hinweis für Mitglieder (optional)', 'Notice for members (optional)')}
            placeholder={tr('Hubra wird aktualisiert …', 'Hubra is being updated…')}
            value={message}
            onChange={(e) => setMessage(e.currentTarget.value)}
            style={{ flex: 1, minWidth: 220 }}
            maxLength={500}
          />
          <Select
            label={tr('Dauer', 'Duration')}
            value={minutes}
            onChange={(v) => setMinutes(v ?? '30')}
            allowDeselect={false}
            w={170}
            data={[
              { value: '15', label: tr('15 Minuten', '15 minutes') },
              { value: '30', label: tr('30 Minuten', '30 minutes') },
              { value: '60', label: tr('1 Stunde', '1 hour') },
              { value: '240', label: tr('4 Stunden', '4 hours') },
              { value: '0', label: tr('Bis ich sie beende', 'Until I end it') },
            ]}
          />
          <Button color="orange" loading={busy} onClick={() => change(true)}>
            {tr('Wartung starten', 'Start maintenance')}
          </Button>
        </Group>
      )}
    </Paper>
  )
}

/** The platform notification matrix: what (platform events, alerts) goes
 * where (mail to platform admins, Discord; more channels are more columns).
 * Each admin still picks their own alert mails. */
export function AlertRulesPanel() {
  const { notify, hasGlobalPermission } = useAdmin()
  const queryClient = useQueryClient()
  const canChange = hasGlobalPermission('platform.settings')
  const query = useQuery({ queryKey: ['alert-switches'], queryFn: getAlertSwitches })
  const data = query.data
  const [busy, setBusy] = useState(false)

  const save = async (change: Parameters<typeof updateAlertSwitches>[0]) => {
    setBusy(true)
    try {
      queryClient.setQueryData(['alert-switches'], await updateAlertSwitches(change))
      queryClient.invalidateQueries({ queryKey: ['alerts-overview'] })
    } catch (err) {
      notify('error', tr('Nicht gespeichert', 'Not saved'), failure(err))
    } finally {
      setBusy(false)
    }
  }
  const setType = (id: AlertType, channel: NotifyChannel, on: boolean) =>
    save({ types: { [id]: { [channel]: on } } })
  const setEvent = (id: string, channel: NotifyChannel, on: boolean) =>
    save({ events: { [id]: { [channel]: on } } })
  const channels: NotifyChannel[] = data?.channels ?? ['mail', 'discord']
  const cellDisabled = (ch: NotifyChannel) =>
    !data || !canChange || busy || (ch === 'discord' && !data.discordReady)

  const head = (first: string) => (
    <Table.Thead>
      <Table.Tr>
        <Table.Th>{first}</Table.Th>
        {channels.map((ch) => (
          <Table.Th key={ch} w={72} ta="center">
            {CHANNEL_LABEL[ch]()}
          </Table.Th>
        ))}
      </Table.Tr>
    </Table.Thead>
  )

  return (
    <Stack gap={16}>
      <Paper withBorder shadow="sm" radius="lg" p="lg">
        <Switch
          size="md"
          checked={data?.enabled ?? true}
          disabled={!data || !canChange || busy}
          onChange={(e) => save({ enabled: e.currentTarget.checked })}
          label={<Text fw={600}>{tr('Warnungen senden', 'Send alerts')}</Text>}
          description={tr(
            'Aus: keine Warnung geht per Mail oder auf Discord raus. Das Ereignisprotokoll und die Übersicht zeigen weiter alles.',
            'Off: no alert goes out by mail or to Discord. The event log and the overview still show everything.',
          )}
        />
        {!canChange && (
          <Text size="xs" c="dimmed" mt={8}>
            {tr(
              'Ändern können das Plattform-Admins mit Plattform-Einstellungen.',
              'Platform admins with platform settings can change this.',
            )}
          </Text>
        )}
      </Paper>

      <Paper withBorder shadow="sm" radius="lg" p="lg">
        <Title order={4} mb={4}>
          {tr('Was wohin gemeldet wird', 'What goes where')}
        </Title>
        <Text size="sm" c="dimmed" mb={12}>
          {tr(
            'Für die ganze Plattform. Mail geht an die Plattform-Admins; bei Warnungen wählt jede Person zusätzlich unter «Meine Warnungen». Discord ist das Plattform-Log, Plattform-Ereignisse gehen in den Audit-Kanal, wenn einer gewählt ist.',
            'For the whole platform. Mail goes to the platform admins; for alerts each person also chooses under "My alerts". Discord is the platform log; platform events go to the audit channel when one is picked.',
          )}
        </Text>
        {data && !data.discordReady && (
          <Alert color="gray" variant="light" mb={12}>
            {tr(
              'Discord ist nicht eingerichtet (Discord › Kanäle: Bot-Token und Kanal für das Plattform-Log).',
              'Discord is not set up (Discord › Channels: bot token and platform log channel).',
            )}
          </Alert>
        )}
        <Table verticalSpacing="sm" horizontalSpacing="xs" layout="fixed" mb="md">
          {head(tr('Plattform-Ereignis', 'Platform event'))}
          <Table.Tbody>
            {(data
              ? Object.keys(data.events).map(
                  (id) =>
                    PLATFORM_EVENTS.find((e) => e.id === id) ?? { id, label: () => id },
                )
              : PLATFORM_EVENTS
            ).map((ev) => {
              const row = data?.events?.[ev.id]
              return (
                <Table.Tr key={ev.id}>
                  <Table.Td>
                    <Text size="sm" style={{ wordBreak: 'break-word' }}>
                      {ev.label()}
                    </Text>
                  </Table.Td>
                  {channels.map((ch) => (
                    <Table.Td key={ch} ta="center">
                      {row && !(ch in row) ? (
                        <Text span size="sm" c="dimmed" aria-label={tr('nicht verfügbar', 'not available')}>
                          –
                        </Text>
                      ) : (
                      <Checkbox
                        checked={row?.[ch] ?? false}
                        disabled={cellDisabled(ch)}
                        aria-label={`${ev.label()}: ${CHANNEL_LABEL[ch]()}`}
                        onChange={(e) => setEvent(ev.id, ch, e.currentTarget.checked)}
                        style={{ display: 'inline-block' }}
                      />
                      )}
                    </Table.Td>
                  ))}
                </Table.Tr>
              )
            })}
          </Table.Tbody>
        </Table>
        <Table verticalSpacing="sm" horizontalSpacing="xs" layout="fixed">
          {head(tr('Warnung', 'Alert'))}
          <Table.Tbody>
            {ALERT_TYPES.map((t) => {
              const row = data?.types[t.id]
              const off = !data?.enabled
              return (
                <Table.Tr key={t.id} style={off ? { opacity: 0.5 } : undefined}>
                  <Table.Td>
                    <Text size="sm" fw={600}>
                      {t.label()}
                    </Text>
                    <Text size="xs" c="dimmed" style={{ wordBreak: 'break-word' }}>
                      {t.desc()}
                    </Text>
                  </Table.Td>
                  {channels.map((ch) => (
                    <Table.Td key={ch} ta="center">
                      <Checkbox
                        checked={row?.[ch] ?? true}
                        disabled={cellDisabled(ch)}
                        aria-label={`${t.label()}: ${CHANNEL_LABEL[ch]()}`}
                        onChange={(e) => setType(t.id, ch, e.currentTarget.checked)}
                        style={{ display: 'inline-block' }}
                      />
                    </Table.Td>
                  ))}
                </Table.Tr>
              )
            })}
          </Table.Tbody>
        </Table>
      </Paper>
    </Stack>
  )
}
