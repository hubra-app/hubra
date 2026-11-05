import { useState } from 'react'
import { Alert, Anchor, Avatar, Button, Checkbox, Group, Select, Stack, Text, TextInput } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { IconPlus, IconRefresh } from '@tabler/icons-react'
import { tr } from '@/lang'
import { useAdmin } from '@/context/AdminContext'
import { createDiscordChannel, getDiscordServerChannels, getDiscordServers } from '@/api/platform'

/** One channel to pick on the shared server. */
export interface DiscordChannelSlot {
  label: string
  description: string
  channelId: string
  onChange: (id: string) => void
  /** The channel ID field, e.g. while Discord can't be reached. */
  fallback: React.ReactNode
  /** The name offered when the bot makes a new channel for this slot. */
  suggestedName?: string
  /** The bot also opens private threads there (support channel). */
  threads?: boolean
}

/** Make a new channel on the server through the bot, then pick it. */
function NewChannel({
  serverId,
  suggestedName,
  threads,
  onMade,
}: {
  serverId: string
  suggestedName: string
  threads?: boolean
  onMade: (id: string) => void
}) {
  const { notify } = useAdmin()
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [name, setName] = useState(suggestedName)
  const [hidden, setHidden] = useState(true)
  const [busy, setBusy] = useState(false)
  if (!open)
    return (
      <Anchor
        component="button"
        type="button"
        size="xs"
        style={{ alignSelf: 'flex-start' }}
        onClick={() => setOpen(true)}
      >
        <Group gap={4} component="span">
          <IconPlus size={12} />
          {tr('Neuen Kanal anlegen lassen', 'Have the bot make a new channel')}
        </Group>
      </Anchor>
    )
  const make = async () => {
    setBusy(true)
    try {
      const made = await createDiscordChannel(serverId, { name, private: hidden, threads })
      await queryClient.invalidateQueries({ queryKey: ['discord-server-channels', serverId] })
      onMade(made.id)
      notify('success', tr(`#${made.name} angelegt`, `#${made.name} made`), tr('Noch speichern.', 'Save to use it.'))
      setOpen(false)
    } catch (err) {
      notify('error', tr('Kanal nicht angelegt', 'Channel not made'), (err as Error).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <Group gap="xs" align="flex-end" wrap="wrap">
      <TextInput
        size="xs"
        style={{ flex: '1 1 180px' }}
        label={tr('Name des neuen Kanals', 'New channel name')}
        value={name}
        onChange={(e) => setName(e.currentTarget.value)}
        maxLength={100}
      />
      <Checkbox
        size="xs"
        mb={6}
        label={tr('Nur für Plattform-Admins sichtbar', 'Only platform admins see it')}
        checked={hidden}
        onChange={(e) => setHidden(e.currentTarget.checked)}
      />
      <Button size="xs" loading={busy} disabled={!name.trim()} onClick={make}>
        {tr('Anlegen', 'Make')}
      </Button>
      <Button size="xs" variant="subtle" onClick={() => setOpen(false)}>
        {tr('Abbrechen', 'Cancel')}
      </Button>
    </Group>
  )
}

/** Pick the platform server once and one channel per slot (platform log,
 * audit channel) from the bot's own lists.
 *
 * The server list is what the bot is on (so: add it first, then reload);
 * the channels are the text channels it can post in. The channel ID fields
 * stay as a fallback. */
export function DiscordLogPicker({
  slots,
  botTokenSet,
  addLink,
}: {
  slots: DiscordChannelSlot[]
  botTokenSet: boolean
  addLink: React.ReactNode
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
        {slots.map((slot) => (
          <div key={slot.label}>{slot.fallback}</div>
        ))}
      </Stack>
    )
  }

  const server = servers.data?.servers.find((s) => s.id === serverId)
  const known = (id: string) => !!channels.data?.channels.some((c) => c.id === id)
  const options = (channels.data?.channels ?? []).map((c) => ({
    value: c.id,
    label: c.category ? `#${c.name} · ${c.category}` : `#${c.name}`,
  }))

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
            // Both channels live on this server: a new server clears them.
            if (v !== serverId) slots.forEach((slot) => slot.onChange(''))
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
      {slots.map((slot) => (
        <Stack key={slot.label} gap={4}>
          <Select
            label={slot.label}
            description={slot.description}
            placeholder={
              !serverId
                ? tr('Zuerst einen Server wählen', 'Pick a server first')
                : channels.isLoading
                  ? tr('Lädt …', 'Loading …')
                  : tr('Kanal wählen', 'Pick a channel')
            }
            disabled={!serverId}
            data={options}
            value={known(slot.channelId) ? slot.channelId : null}
            onChange={(v) => slot.onChange(v ?? '')}
            searchable
            clearable
            nothingFoundMessage={tr(
              'Kein Kanal, in den der Bot schreiben darf',
              'No channel the bot may post in',
            )}
          />
          {serverId && (
            <NewChannel
              serverId={serverId}
              suggestedName={slot.suggestedName ?? 'hubra'}
              threads={slot.threads}
              onMade={slot.onChange}
            />
          )}
          {slot.channelId && channels.data && !known(slot.channelId) && (
            <Text size="xs" c="orange">
              {tr(
                `Der gespeicherte Kanal ${slot.channelId} ist nicht in der Liste: Der Bot sieht ihn nicht oder darf dort nicht schreiben.`,
                `The saved channel ${slot.channelId} is not in the list: the bot can't see it or may not post there.`,
              )}
            </Text>
          )}
        </Stack>
      ))}
      {channels.isError && (
        <Alert color="orange" variant="light">
          {(channels.error as Error).message}
        </Alert>
      )}
      <Anchor
        component="button"
        type="button"
        size="xs"
        style={{ alignSelf: 'flex-start' }}
        onClick={() => setManual((m) => !m)}
      >
        {manual
          ? tr('Kanal-IDs ausblenden', 'Hide the channel IDs')
          : tr('Kanal-IDs selbst eintragen', 'Enter the channel IDs yourself')}
      </Anchor>
      {manual &&
        slots.map((slot) => <div key={slot.label}>{slot.fallback}</div>)}
    </Stack>
  )
}
