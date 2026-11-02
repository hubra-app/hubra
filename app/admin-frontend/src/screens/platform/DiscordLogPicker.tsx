import { useState } from 'react'
import { Alert, Anchor, Avatar, Button, Group, Select, Stack, Text } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { IconRefresh } from '@tabler/icons-react'
import { tr } from '@/lang'
import { getDiscordServerChannels, getDiscordServers } from '@/api/platform'

/** Pick the platform log server and channel from the bot's own lists.
 *
 * The server list is what the bot is on (so: add it first, then reload);
 * the channels are the text channels it can post in. The channel ID field
 * stays as a fallback (`fallback`), e.g. while Discord can't be reached. */
export function DiscordLogPicker({
  channelId,
  onChange,
  botTokenSet,
  addLink,
  fallback,
  channelLabel,
}: {
  channelLabel?: string
  channelId: string
  onChange: (id: string) => void
  botTokenSet: boolean
  addLink: React.ReactNode
  fallback: React.ReactNode
}) {
  const [picked, setPicked] = useState<string | null>(null)
  const [manual, setManual] = useState(false)
  const servers = useQuery({
    queryKey: ['discord-servers'],
    queryFn: getDiscordServers,
    enabled: botTokenSet,
    retry: false,
    staleTime: 60_000,
  })
  // Until one is picked: the server of the saved channel.
  const serverId = picked ?? servers.data?.currentServerId ?? null
  const channels = useQuery({
    queryKey: ['discord-server-channels', serverId],
    queryFn: () => getDiscordServerChannels(serverId as string),
    enabled: botTokenSet && !!serverId,
    retry: false,
  })

  if (!botTokenSet) {
    return (
      <Stack gap="sm">
        <Text size="sm" c="dimmed">
          {tr(
            'Zuerst den Bot-Token oben speichern, dann lassen sich Server und Kanal hier auswählen.',
            'Save the bot token above first; then you can pick the server and channel here.',
          )}
        </Text>
        {fallback}
      </Stack>
    )
  }

  const server = servers.data?.servers.find((s) => s.id === serverId)
  const channelKnown = channels.data?.channels.some((c) => c.id === channelId)

  return (
    <Stack gap="sm">
      {servers.isError && (
        <Alert color="orange" variant="light">
          {tr('Die Server-Liste kam nicht von Discord: ', 'Discord did not send the server list: ')}
          {(servers.error as Error).message}
        </Alert>
      )}
      <Group align="flex-end" gap="xs" wrap="nowrap">
        <Select
          style={{ flex: 1 }}
          label={tr('Server', 'Server')}
          description={tr(
            'Die Server, auf denen der Hubra-Bot ist. Fehlt deiner, zuerst den Bot hinzufügen und dann neu laden.',
            'The servers the Hubra bot is on. If yours is missing, add the bot first, then reload.',
          )}
          placeholder={
            servers.isLoading ? tr('Lädt …', 'Loading …') : tr('Server wählen', 'Pick a server')
          }
          data={(servers.data?.servers ?? []).map((s) => ({ value: s.id, label: s.name }))}
          value={serverId}
          onChange={(v) => {
            setPicked(v)
            if (v !== serverId) onChange('')
          }}
          leftSection={
            server?.icon ? <Avatar src={server.icon} size={20} radius="sm" /> : undefined
          }
          searchable
          nothingFoundMessage={tr('Kein Server', 'No server')}
        />
        <Button
          variant="default"
          px="xs"
          aria-label={tr('Server-Liste neu laden', 'Reload the server list')}
          loading={servers.isFetching}
          onClick={() => servers.refetch()}
        >
          <IconRefresh size={16} />
        </Button>
      </Group>
      <Text size="sm">{addLink}</Text>
      <Select
        label={channelLabel ?? tr('Kanal für das Plattform-Log', 'Channel for the platform log')}
        description={tr(
          'Nur Textkanäle, in denen der Bot lesen, schreiben und Links einbetten darf.',
          'Only text channels where the bot may view, send and embed links.',
        )}
        placeholder={
          !serverId
            ? tr('Zuerst einen Server wählen', 'Pick a server first')
            : channels.isLoading
              ? tr('Lädt …', 'Loading …')
              : tr('Kanal wählen', 'Pick a channel')
        }
        disabled={!serverId}
        data={(channels.data?.channels ?? []).map((c) => ({
          value: c.id,
          label: c.category ? `#${c.name} · ${c.category}` : `#${c.name}`,
        }))}
        value={channelKnown ? channelId : null}
        onChange={(v) => onChange(v ?? '')}
        searchable
        clearable
        nothingFoundMessage={tr(
          'Kein Kanal, in den der Bot schreiben darf',
          'No channel the bot may post in',
        )}
      />
      {channels.isError && (
        <Alert color="orange" variant="light">
          {(channels.error as Error).message}
        </Alert>
      )}
      {channelId && channels.data && !channelKnown && (
        <Text size="xs" c="orange">
          {tr(
            `Der gespeicherte Kanal ${channelId} ist nicht in der Liste: Der Bot sieht ihn nicht oder darf dort nicht schreiben.`,
            `The saved channel ${channelId} is not in the list: the bot can't see it or may not post there.`,
          )}
        </Text>
      )}
      <Anchor
        component="button"
        type="button"
        size="xs"
        style={{ alignSelf: 'flex-start' }}
        onClick={() => setManual((m) => !m)}
      >
        {manual
          ? tr('Kanal-ID ausblenden', 'Hide the channel ID')
          : tr('Kanal-ID selbst eintragen', 'Enter the channel ID yourself')}
      </Anchor>
      {manual && fallback}
    </Stack>
  )
}
