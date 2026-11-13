import { Checkbox, Group, Text } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { getEventChannels } from '@/api/events'
import { getPostChannels } from '@/api/posts'
import { Field } from '@/components/ui'
import { qk } from '@/data/keys'
import { useT } from '@/locales/i18n'
import { isOn, toggle, type ChannelPick } from './postChannels'

/** "Send to": the app (bell and push) and each module that announces posts
 * or events (Discord, Messengers); every channel still follows its own
 * settings. */
export function PostChannelsField({
  value,
  onChange,
  kind = 'posts',
}: {
  value: ChannelPick
  onChange: (value: ChannelPick) => void
  /** A post (the feed) or a new event (the calendar). */
  kind?: 'posts' | 'events'
}) {
  const { t } = useT()
  const events = kind === 'events'
  const { data: channels = [] } = useQuery({
    queryKey: events ? qk.eventChannels : qk.posts.channels,
    queryFn: events ? getEventChannels : getPostChannels,
    staleTime: 5 * 60_000,
  })
  if (channels.length === 0) return null
  const all = channels.map((c) => c.key)
  const label = (key: string, name: string) =>
    key === 'app'
      ? t('posts.channels.app', 'Mitteilung in Hubra (Glocke und Push)')
      : t(`modules.${key}.name`, name)
  return (
    <Field
      label={t('posts.channels.label', 'Senden an')}
      hint={
        events
          ? t(
              'events.channels.hint',
              'Der Anlass steht immer im Kalender. Jeder Kanal folgt zusätzlich seinen eigenen Einstellungen.',
            )
          : t(
              'posts.channels.hint',
              'Der Beitrag steht immer im Feed. Jeder Kanal folgt zusätzlich seinen eigenen Einstellungen.',
            )
      }
    >
      <Group gap="lg" data-testid="post-channels">
        {channels.map((c) => (
          <Checkbox
            key={c.key}
            label={label(c.key, c.name)}
            checked={isOn(value, c.key)}
            onChange={() => onChange(toggle(value, c.key, all))}
            data-testid={`post-channel-${c.key}`}
          />
        ))}
      </Group>
      {value !== null && value.length === 0 && (
        <Text size="xs" c="dimmed" mt={4}>
          {events
            ? t('events.channels.none', 'Ohne Benachrichtigung: nur im Kalender.')
            : t('posts.channels.none', 'Ohne Benachrichtigung: nur im Feed.')}
        </Text>
      )}
    </Field>
  )
}
