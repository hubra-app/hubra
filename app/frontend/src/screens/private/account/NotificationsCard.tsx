import { useState } from 'react'
import { Checkbox, Group, Paper, Stack, Switch, Table, Text } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { IconBellRinging } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useToast } from '@/context/AppContext'
import { qk } from '@/data/keys'
import {
  getMyNotifications,
  setMyNotifications,
  type NotifyChannel,
  type NotifyTopic,
} from '@/api/members'

const TOPICS: [NotifyTopic, string][] = [
  ['posts', 'Neue Beiträge'],
  ['events', 'Neue Anlässe'],
  ['polls', 'Neue Umfragen'],
  ['event_reminders', 'Erinnerung vor Anlässen und Trainings'],
  ['poll_reminders', 'Erinnerung vor Ende einer Umfrage'],
  ['my_events', 'Änderungen an meinen Anlässen'],
  ['bookings', 'Bestätigung meiner Anmeldungen'],
  ['waitlist', 'Warteliste: Platz frei geworden'],
  ['my_polls', 'Stimmen in meinen Umfragen, Vollmachten'],
  ['tasks', 'Aufgaben für mich (Gesuche, Anmeldungen zum Bestätigen)'],
  ['requests', 'Antworten auf meine Anfragen'],
  ['payments', 'Rechnungen: neu, bald fällig, überfällig'],
  ['membership', 'Mitgliedschaft verlängern'],
  ['qualifications', 'Qualifikationen, die bald ablaufen'],
  ['digest', 'Wochenübersicht am Montag'],
]
const CHANNELS: [NotifyChannel, string][] = [
  ['bell', 'Glocke'],
  ['push', 'Push'],
  ['mail', 'E-Mail'],
]

/** The member chooses per topic: bell, browser push and (reminders) mail. */
export function NotificationsCard() {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const [busy, setBusy] = useState(false)
  const { data } = useQuery({ queryKey: qk.account.notifications, queryFn: getMyNotifications })
  if (!data) return null
  const channels: [NotifyChannel, string][] = [
    ...CHANNELS,
    ...(data.apps ?? []).map((a): [NotifyChannel, string] => [a.key, a.name]),
  ]

  const toggle = async (topic: NotifyTopic, channel: NotifyChannel, on: boolean) => {
    setBusy(true)
    try {
      queryClient.setQueryData(
        qk.account.notifications,
        await setMyNotifications({ [topic]: { [channel]: on } }),
      )
    } catch (err) {
      notify('error', t('common.error'), err instanceof Error ? err.message : '')
    } finally {
      setBusy(false)
    }
  }

  const setMuted = async (on: boolean) => {
    setBusy(true)
    try {
      queryClient.setQueryData(qk.account.notifications, await setMyNotifications({ muted: on }))
    } catch (err) {
      notify('error', t('common.error'), err instanceof Error ? err.message : '')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Paper withBorder>
      <Group p="md" gap="sm" style={{ borderBottom: '1px solid var(--hb-border)' }}>
        <IconBellRinging size={16} style={{ color: 'var(--mantine-color-ink-4)' }} />
        <Text fw={700} fz="md">
          {t('account.notify.title', 'Benachrichtigungen')}
        </Text>
      </Group>
      <Stack p="md" gap="sm">
        <Text fz="sm" c="dimmed">
          {t(
            'account.notify.hint',
            'Wähle pro Thema, wo du es bekommst: in der Glocke in Hubra, als Push im Browser oder per E-Mail. Hinweise zur Sicherheit deines Kontos kommen immer.',
          )}
        </Text>
        <Table verticalSpacing={6} horizontalSpacing={6} layout="fixed">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{t('account.notify.topic', 'Thema')}</Table.Th>
              {channels.map(([channel, label]) => (
                <Table.Th key={channel} w={64} ta="center" fz="xs">
                  {t(`account.notify.${channel}`, label)}
                </Table.Th>
              ))}
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {TOPICS.map(([topic, label]) => (
              <Table.Tr key={topic}>
                <Table.Td fz="sm" style={{ wordBreak: 'break-word' }}>
                  {t(`account.notify.topics.${topic}`, label)}
                </Table.Td>
                {channels.map(([channel, channelLabel]) => {
                  const value = data.topics[topic]?.[channel]
                  return (
                    <Table.Td key={channel} ta="center">
                      {value === undefined ? (
                        <Text c="dimmed" fz="xs" aria-hidden>
                          –
                        </Text>
                      ) : (
                        <Checkbox
                          checked={value}
                          disabled={busy}
                          aria-label={`${t(`account.notify.topics.${topic}`, label)}: ${t(
                            `account.notify.${channel}`,
                            channelLabel,
                          )}`}
                          onChange={(e) => toggle(topic, channel, e.currentTarget.checked)}
                          style={{ display: 'inline-block' }}
                        />
                      )}
                    </Table.Td>
                  )
                })}
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
        <Text fz="xs" c="dimmed">
          {t(
            'account.notify.pushHint',
            'Push kommt nur auf Geräte, auf denen du Push unten eingeschaltet hast.',
          )}
        </Text>
        {(data.apps ?? []).length > 0 && (
          <Switch
            mt="xs"
            checked={!!data.muted}
            disabled={busy}
            onChange={(e) => setMuted(e.currentTarget.checked)}
            label={t('account.notify.muteAll', 'Alle Direktnachrichten stummschalten')}
            description={t(
              'account.notify.muteAllHint',
              'Keine Direktnachricht von Hubra auf Discord, in keinem Verein und auch nicht für dein Konto. Deine Auswahl oben bleibt gespeichert.',
            )}
          />
        )}
        {(data.apps ?? []).some((a) => a.key === 'discord') && (
          <Text fz="xs" c="dimmed">
            {t(
              'account.notify.discordHint',
              'Discord schickt dir eine Direktnachricht vom Bot des Vereins. Dafür müssen Direktnachrichten von Mitgliedern des Servers erlaubt sein (Discord › Privatsphäre-Einstellungen des Servers).',
            )}
          </Text>
        )}
      </Stack>
    </Paper>
  )
}
