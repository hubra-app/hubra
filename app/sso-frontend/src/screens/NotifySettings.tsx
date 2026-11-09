import { useState } from 'react'
import { Accordion, Avatar, Checkbox, Group, Loader, Paper, Stack, Table, Text } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { clubLogoUrl } from '@hubra/api-client'
import { useSso } from '@/context/SsoContext'
import { LoadFailed } from '@/components/LoadFailed'
import { tr } from '@/lang'
import * as authApi from '@/api/auth'
import type { ClubNotifySettings, NotifyChannel, NotifyTopic } from '@/api/auth'

const TOPICS: [NotifyTopic, () => string][] = [
  ['posts', () => tr('Neue Beiträge', 'New posts')],
  ['events', () => tr('Neue Anlässe', 'New events')],
  ['polls', () => tr('Neue Umfragen', 'New polls')],
  ['event_reminders', () => tr('Erinnerung vor Anlässen und Trainings', 'Reminder before events and trainings')],
  ['poll_reminders', () => tr('Erinnerung vor Ende einer Umfrage', 'Reminder before a poll closes')],
  ['my_events', () => tr('Änderungen an meinen Anlässen', 'Changes to my events')],
  ['bookings', () => tr('Bestätigung meiner Anmeldungen', 'Confirmation of my sign-ups')],
  ['waitlist', () => tr('Warteliste: Platz frei geworden', 'Waitlist: a place came free')],
  ['my_polls', () => tr('Stimmen in meinen Umfragen, Vollmachten', 'Votes in my polls, proxies')],
  [
    'tasks',
    () =>
      tr(
        'Aufgaben für mich (Gesuche, Anmeldungen zum Bestätigen)',
        'Tasks for me (applications, sign-ups to approve)',
      ),
  ],
  ['requests', () => tr('Antworten auf meine Anfragen', 'Answers to my requests')],
  ['payments', () => tr('Rechnungen: neu, bald fällig, überfällig', 'Invoices: new, due soon, overdue')],
  ['membership', () => tr('Mitgliedschaft verlängern', 'Membership renewal')],
  ['qualifications', () => tr('Qualifikationen, die bald ablaufen', 'Qualifications that end soon')],
  ['digest', () => tr('Wochenübersicht am Montag', 'Weekly overview on Monday')],
]

const CHANNELS: [NotifyChannel, () => string][] = [
  ['bell', () => tr('Glocke', 'Bell')],
  ['push', () => tr('Push', 'Push')],
  ['mail', () => tr('E-Mail', 'E-mail')],
]

type Data = { data: ClubNotifySettings[] }
const KEY = ['notify-settings']

function ClubTable({ club }: { club: ClubNotifySettings }) {
  const { notify } = useSso()
  const queryClient = useQueryClient()
  const [busy, setBusy] = useState(false)
  const channels: [NotifyChannel, () => string][] = [
    ...CHANNELS,
    ...club.apps.map((a): [NotifyChannel, () => string] => [a.key, () => a.name]),
  ]

  const toggle = async (topic: NotifyTopic, channel: NotifyChannel, on: boolean) => {
    setBusy(true)
    try {
      const next = await authApi.setNotifySettings(club.club.slug, { [topic]: { [channel]: on } })
      queryClient.setQueryData<Data>(KEY, (prev) =>
        prev
          ? { data: prev.data.map((c) => (c.club.slug === next.club.slug ? next : c)) }
          : prev,
      )
    } catch (err) {
      notify(
        'error',
        tr('Speichern fehlgeschlagen', 'Saving failed'),
        err instanceof Error ? err.message : '',
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <Stack gap="xs">
      <Table verticalSpacing={6} horizontalSpacing={6} layout="fixed">
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{tr('Thema', 'Topic')}</Table.Th>
            {channels.map(([channel, label]) => (
              <Table.Th key={channel} w={64} ta="center" fz="xs">
                {label()}
              </Table.Th>
            ))}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {TOPICS.map(([topic, label]) => (
            <Table.Tr key={topic}>
              <Table.Td fz="sm" style={{ wordBreak: 'break-word' }}>
                {label()}
              </Table.Td>
              {channels.map(([channel, channelLabel]) => {
                const value = club.topics[topic]?.[channel]
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
                        aria-label={`${club.club.name ?? ''}, ${label()}: ${channelLabel()}`}
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
      {club.apps.some((a) => a.key === 'discord') && (
        <Text fz="xs" c="dimmed">
          {tr(
            'Discord schickt dir eine Direktnachricht vom Bot des Vereins. Dafür müssen Direktnachrichten von Mitgliedern des Servers erlaubt sein.',
            "Discord sends you a direct message from the club's bot. Direct messages from server members must be allowed.",
          )}
        </Text>
      )}
    </Stack>
  )
}

/** Per club, which notifications come in the bell, by push, by mail or as
 * a direct message: the same choices as the club's own account page. */
export function NotifySettings() {
  const settings = useQuery({ queryKey: KEY, queryFn: authApi.getNotifySettings })
  if (settings.isError) return <LoadFailed onRetry={() => settings.refetch()} />
  if (!settings.data) return <Loader size="sm" />
  const clubs = settings.data.data

  return (
    <Stack gap="sm">
      <Text size="sm" c="dimmed">
        {tr(
          'Wähle pro Verein und Thema, wo du es bekommst: in der Glocke, als Push im Browser oder per E-Mail. Hinweise zur Sicherheit deines Kontos kommen immer.',
          "Choose per club and topic where you get it: in the bell, as a browser push or by e-mail. Notices about your account's security always come.",
        )}
      </Text>
      {clubs.length === 0 ? (
        <Paper withBorder py={40} ta="center" c="dimmed">
          <Text size="sm">{tr('Noch in keinem Verein.', 'Not in a club yet.')}</Text>
        </Paper>
      ) : (
        <Accordion
          variant="separated"
          multiple
          defaultValue={clubs.length === 1 ? [clubs[0].club.slug ?? '-'] : []}
        >
          {clubs.map((c) => (
            <Accordion.Item key={c.club.slug ?? '-'} value={c.club.slug ?? '-'}>
              <Accordion.Control>
                <Group gap="sm" wrap="nowrap">
                  {c.club.slug && (
                    <Avatar
                      radius="md"
                      size={28}
                      color="acc"
                      variant="light"
                      src={clubLogoUrl(c.club.slug, c.club.logoVersion)}
                      alt=""
                      styles={{ image: { objectFit: 'contain' } }}
                    >
                      {(c.club.name ?? c.club.slug).slice(0, 2).toUpperCase()}
                    </Avatar>
                  )}
                  <Text fw={600} truncate>
                    {c.club.name ?? tr('Verein', 'Club')}
                  </Text>
                </Group>
              </Accordion.Control>
              <Accordion.Panel>
                <ClubTable club={c} />
              </Accordion.Panel>
            </Accordion.Item>
          ))}
        </Accordion>
      )}
      <Text fz="xs" c="dimmed">
        {tr(
          'Push kommt nur auf Geräte, auf denen du Push im Verein eingeschaltet hast.',
          'Push only reaches devices where you turned push on in the club.',
        )}
      </Text>
    </Stack>
  )
}
