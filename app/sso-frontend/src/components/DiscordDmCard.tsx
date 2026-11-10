import { useState } from 'react'
import { Group, Paper, Stack, Switch, Text } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { IconBrandDiscord } from '@tabler/icons-react'
import { useSso } from '@/context/SsoContext'
import { tr } from '@/lang'
import * as authApi from '@/api/auth'
import type { DiscordDms } from '@/api/auth'

const KEY = ['discord-dms']

/** Discord direct messages for the account itself (sign-in alerts, answers
 * to its own requests) and the switch that mutes every Hubra direct
 * message. Shown once the account linked Discord. */
export function DiscordDmCard() {
  const { notify } = useSso()
  const queryClient = useQueryClient()
  const [busy, setBusy] = useState(false)
  const { data } = useQuery({ queryKey: KEY, queryFn: authApi.getDiscordDms })
  if (!data?.available) return null

  const save = async (change: Parameters<typeof authApi.setDiscordDms>[0]) => {
    setBusy(true)
    try {
      queryClient.setQueryData<DiscordDms>(KEY, await authApi.setDiscordDms(change))
    } catch (err) {
      notify('error', tr('Nicht gespeichert', 'Not saved'), err instanceof Error ? err.message : '')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Paper withBorder p="md">
      <Stack gap="sm">
        <Group gap="xs">
          <IconBrandDiscord size={18} style={{ color: 'var(--mantine-color-dimmed)' }} />
          <Text fw={600}>{tr('Direktnachrichten auf Discord', 'Direct messages on Discord')}</Text>
        </Group>
        <Text size="sm" c="dimmed">
          {tr(
            'Der Hubra-Bot schreibt dir auf Discord, was nur dich betrifft. Was deine Vereine dir schicken, wählst du im Verein unter Konto › Mitgliedschaft › Benachrichtigungen.',
            'The Hubra bot messages you on Discord about things that only concern you. What your clubs send you, you choose in the club under Account › Membership › Notifications.',
          )}
        </Text>
        <Switch
          checked={data.kinds.sign_in}
          disabled={busy || data.muted}
          onChange={(e) => save({ kinds: { sign_in: e.currentTarget.checked } })}
          label={tr('Anmeldung von einem neuen Gerät', 'Sign-in from a new device')}
          description={tr(
            'Mit Zeit, Gerät, IP-Adresse und einem Knopf «Das war ich nicht». Die E-Mail kommt weiterhin.',
            'With time, device, IP address and a "This wasn\'t me" button. The email still comes.',
          )}
        />
        <Switch
          checked={data.kinds.requests}
          disabled={busy || data.muted}
          onChange={(e) => save({ kinds: { requests: e.currentTarget.checked } })}
          label={tr('Antworten auf meine Anfragen', 'Answers to my requests')}
          description={tr(
            'Support-Meldungen und Anfragen für einen neuen Verein.',
            'Support reports and requests for a new club.',
          )}
        />
        <Switch
          color="red"
          checked={data.muted}
          disabled={busy}
          onChange={(e) => save({ muted: e.currentTarget.checked })}
          label={tr('Alle Direktnachrichten stummschalten', 'Mute all direct messages')}
          description={tr(
            'Keine Direktnachricht von Hubra, auch nicht aus deinen Vereinen. Deine Auswahl bleibt gespeichert.',
            'No Hubra direct message at all, from your clubs neither. Your choices stay saved.',
          )}
        />
        <Text size="xs" c="dimmed">
          {tr(
            'Discord stellt sie nur zu, wenn du einen Server mit dem Hubra-Bot teilst und Direktnachrichten von Mitgliedern dieses Servers erlaubst.',
            'Discord only delivers them when you share a server with the Hubra bot and allow direct messages from that server\'s members.',
          )}
        </Text>
      </Stack>
    </Paper>
  )
}
