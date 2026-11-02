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
} from '@/api/platform'
import { ALERT_TYPES } from './eventLabels'

const failure = (err: unknown) => (err instanceof Error ? err.message : undefined)

/** Maintenance mode: club apps show a notice and their API answers 503,
 * manage keeps working, alerts pause. */
export function MaintenanceCard({ state }: { state: Maintenance | undefined }) {
  const { notify, hasGlobalPermission } = useAdmin()
  const queryClient = useQueryClient()
  const canChange = hasGlobalPermission('platform.settings')
  const [message, setMessage] = useState('')
  const [minutes, setMinutes] = useState<string>('30')
  const [start, setStart] = useState('')
  const [busy, setBusy] = useState(false)

  const run = async (body: Parameters<typeof setMaintenance>[0], done: string) => {
    setBusy(true)
    try {
      await setMaintenance(body)
      await queryClient.invalidateQueries({ queryKey: ['alerts-overview'] })
      await queryClient.invalidateQueries({ queryKey: ['maintenance'] })
      notify('success', done)
    } catch (err) {
      notify('error', tr('Nicht geändert', 'Not changed'), failure(err))
    } finally {
      setBusy(false)
    }
  }

  const change = (on: boolean) => {
    if (!on) return run({ on }, tr('Wartungsmodus aus', 'Maintenance mode off'))
    const length = minutes === '0' ? null : Number(minutes)
    if (start) {
      return run(
        {
          on,
          message: message.trim(),
          minutes: length ?? 30,
          start: new Date(start).toISOString(),
        },
        tr('Wartung geplant', 'Maintenance planned'),
      )
    }
    return run(
      { on, message: message.trim(), minutes: length },
      tr('Wartungsmodus an', 'Maintenance mode on'),
    )
  }

  const active = !!state?.active
  const planned = state?.planned
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
      {!active && planned && (
        <Alert color="orange" variant="light" mb={12} icon={<IconTool size={18} />}>
          <Group justify="space-between" wrap="wrap" gap="xs">
            <Text size="sm">
              {tr(
                `Geplant ab ${formatDateTime(planned.start)}${planned.minutes ? ` für ${planned.minutes} Minuten` : ''}. Die Vereins-Apps zeigen ein Banner; sie beginnt von selbst.`,
                `Planned from ${formatDateTime(planned.start)}${planned.minutes ? ` for ${planned.minutes} minutes` : ''}. Club apps show a banner; it starts by itself.`,
              )}
              {planned.message ? ` «${planned.message}»` : ''}
            </Text>
            {canChange && (
              <Button
                size="xs"
                variant="light"
                color="orange"
                loading={busy}
                onClick={() =>
                  run(
                    { cancelPlan: true },
                    tr('Geplante Wartung abgesagt', 'Planned maintenance cancelled'),
                  )
                }
              >
                {tr('Absagen', 'Cancel')}
              </Button>
            )}
          </Group>
        </Alert>
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
          <TextInput
            type="datetime-local"
            label={tr('Beginn (leer: jetzt)', 'Start (empty: now)')}
            value={start}
            onChange={(e) => setStart(e.currentTarget.value)}
            w={210}
          />
          <Button color="orange" loading={busy} onClick={() => change(true)}>
            {start
              ? tr('Wartung planen', 'Plan maintenance')
              : tr('Wartung starten', 'Start maintenance')}
          </Button>
        </Group>
      )}
    </Paper>
  )
}

/** Platform-wide: whether alerts go out at all, and per type by mail and to
 * the platform Discord log. Each admin still picks their own mails. */
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
  const setType = (id: AlertType, channel: 'mail' | 'discord', on: boolean) =>
    save({ types: { [id]: { [channel]: on } } })

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
          {tr('Wohin welche Warnung geht', 'Where each alert goes')}
        </Title>
        <Text size="sm" c="dimmed" mb={12}>
          {tr(
            'Für die ganze Plattform. Ob eine Person eine Mail bekommt, wählt sie zusätzlich unter «Meine Warnungen».',
            'For the whole platform. Whether a person gets a mail, they also choose under "My alerts".',
          )}
        </Text>
        {data && !data.discordReady && (
          <Alert color="gray" variant="light" mb={12}>
            {tr(
              'Discord ist für Warnungen nicht eingerichtet (Plattform-Einstellungen › Discord › Plattform-Log, Kategorie «alerts»).',
              'Discord is not set up for alerts (Platform settings › Discord › Platform log, category "alerts").',
            )}
          </Alert>
        )}
        <Table verticalSpacing="sm" horizontalSpacing="xs" layout="fixed">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{tr('Warnung', 'Alert')}</Table.Th>
              <Table.Th w={72} ta="center">
                {tr('Mail', 'Mail')}
              </Table.Th>
              <Table.Th w={72} ta="center">
                Discord
              </Table.Th>
            </Table.Tr>
          </Table.Thead>
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
                  {(['mail', 'discord'] as const).map((ch) => (
                    <Table.Td key={ch} ta="center">
                      <Checkbox
                        checked={row?.[ch] ?? true}
                        disabled={
                          !data || !canChange || busy || (ch === 'discord' && !data.discordReady)
                        }
                        aria-label={`${t.label()}: ${ch === 'mail' ? 'Mail' : 'Discord'}`}
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
