import { useState } from 'react'
import { Button, CopyButton, Group, Paper, SegmentedControl, Stack, Text, TextInput } from '@mantine/core'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { IconCalendarEvent } from '@tabler/icons-react'
import { tr } from '@/lang'
import * as authApi from '@/api/auth'

/** One calendar for every club: a personal link for a calendar app, with
 * every club's events or only those the person signed up for. */
export function CalendarFeedCard() {
  const client = useQueryClient()
  const [scope, setScope] = useState<'all' | 'mine'>('all')
  const feed = useQuery({ queryKey: ['account-calendar'], queryFn: authApi.getAccountCalendar })
  const renew = useMutation({
    mutationFn: authApi.renewAccountCalendar,
    onSuccess: (data) => client.setQueryData(['account-calendar'], data),
  })
  if (feed.isError || !feed.data) return null
  const url = feed.data[scope]
  // webcal:// opens the calendar app's "subscribe" dialog.
  const webcal = url.replace(/^https?:\/\//, 'webcal://')

  return (
    <Paper withBorder p="lg">
      <Stack gap="sm">
        <Group gap="xs">
          <IconCalendarEvent size={18} />
          <Text fw={700}>{tr('Kalender aller Vereine', 'Calendar of all clubs')}</Text>
        </Group>
        <Text size="sm" c="dimmed">
          {tr(
            'Ein Link für deine Kalender-App (Google, Apple, Outlook) mit den Anlässen aller deiner Vereine. Er hält sich selbst aktuell.',
            'One link for your calendar app (Google, Apple, Outlook) with the events of all your clubs. It keeps itself up to date.',
          )}
        </Text>
        <SegmentedControl
          value={scope}
          onChange={(v) => setScope(v as 'all' | 'mine')}
          data={[
            { value: 'all', label: tr('Alle Anlässe', 'All events') },
            { value: 'mine', label: tr('Nur meine Anmeldungen', 'Only my sign-ups') },
          ]}
          data-testid="calendar-scope"
        />
        <TextInput
          readOnly
          value={url}
          aria-label={tr('Kalender-Link', 'Calendar link')}
          onFocus={(e) => e.currentTarget.select()}
          data-testid="calendar-url"
        />
        <Group gap="xs" justify="space-between">
          <Group gap="xs">
            <CopyButton value={url}>
              {({ copied, copy }) => (
                <Button variant="default" onClick={copy}>
                  {copied ? tr('Kopiert', 'Copied') : tr('Link kopieren', 'Copy link')}
                </Button>
              )}
            </CopyButton>
            <Button component="a" href={webcal} variant="light">
              {tr('Im Kalender abonnieren', 'Subscribe in calendar')}
            </Button>
          </Group>
          <Button variant="subtle" color="red" loading={renew.isPending} onClick={() => renew.mutate()}>
            {tr('Neuen Link erstellen', 'New link')}
          </Button>
        </Group>
        <Text size="xs" c="dimmed">
          {tr(
            'Wer den Link hat, sieht die Anlässe. «Neuen Link erstellen» macht die alten Links ungültig.',
            'Anyone with the link sees the events. «New link» stops the old links working.',
          )}
        </Text>
      </Stack>
    </Paper>
  )
}
