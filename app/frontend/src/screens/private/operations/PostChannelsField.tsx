import { Checkbox, Group, Text } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { getPostChannels } from '@/api/posts'
import { Field } from '@/components/ui'
import { qk } from '@/data/keys'
import { useT } from '@/locales/i18n'
import { isOn, toggle, type ChannelPick } from './postChannels'

/** "Send to": the app (bell and push) and each module that announces posts
 * (Discord, Messengers); every channel still follows its own settings. */
export function PostChannelsField({
  value,
  onChange,
}: {
  value: ChannelPick
  onChange: (value: ChannelPick) => void
}) {
  const { t } = useT()
  const { data: channels = [] } = useQuery({
    queryKey: qk.posts.channels,
    queryFn: getPostChannels,
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
      hint={t(
        'posts.channels.hint',
        'Der Beitrag steht immer im Feed. Jeder Kanal folgt zusätzlich seinen eigenen Einstellungen.',
      )}
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
          {t('posts.channels.none', 'Ohne Benachrichtigung: nur im Feed.')}
        </Text>
      )}
    </Field>
  )
}
