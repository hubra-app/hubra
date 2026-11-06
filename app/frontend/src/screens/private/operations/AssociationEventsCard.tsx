import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Anchor, Badge, Group, Paper, Stack, Text, Title, UnstyledButton } from '@mantine/core'
import { IconBuildingCommunity, IconChevronDown, IconChevronRight } from '@tabler/icons-react'
import { listAssociationEvents, type AssociationEvent } from '@/api/federation'
import { qk } from '@/data/keys'
import { formatDate } from '@/format'
import { useT } from '@/locales/i18n'

const SHOWN = 4

function when(ev: AssociationEvent): string {
  const days = ev.endDate && ev.endDate !== ev.date ? `${formatDate(ev.date)} – ${formatDate(ev.endDate)}` : formatDate(ev.date)
  return ev.time ? `${days}, ${ev.time}` : days
}

function Row({ ev }: { ev: AssociationEvent }) {
  const { t } = useT()
  const [open, setOpen] = useState(false)
  const more = Boolean(ev.description || ev.onlineUrl)
  return (
    <div>
      <UnstyledButton
        onClick={() => more && setOpen(!open)}
        style={{ width: '100%', cursor: more ? 'pointer' : 'default' }}
        aria-expanded={more ? open : undefined}
      >
        <Group justify="space-between" wrap="nowrap" align="flex-start" gap="sm">
          <div style={{ minWidth: 0 }}>
            <Text fw={600} size="sm">
              {ev.title}
            </Text>
            <Text size="xs" c="dimmed">
              {when(ev)}
              {ev.location ? ` · ${ev.location}` : ''}
            </Text>
          </div>
          <Group gap={6} wrap="nowrap" style={{ flexShrink: 0 }}>
            <Badge size="sm" variant="light" color="grape">
              {ev.federation}
            </Badge>
            {more && (open ? <IconChevronDown size={16} /> : <IconChevronRight size={16} />)}
          </Group>
        </Group>
      </UnstyledButton>
      {open && (
        <Stack gap={4} mt={6}>
          {ev.description && (
            <Text size="sm" style={{ whiteSpace: 'pre-line' }}>
              {ev.description}
            </Text>
          )}
          {ev.onlineUrl && /^https?:\/\//.test(ev.onlineUrl) && (
            <Anchor href={ev.onlineUrl} target="_blank" rel="noopener noreferrer" size="sm">
              {t('associationEvents.online', 'Online teilnehmen')}
            </Anchor>
          )}
        </Stack>
      )}
    </div>
  )
}

/** Upcoming events the club's associations share with their member clubs. */
export function AssociationEventsCard() {
  const { t } = useT()
  const query = useQuery({ queryKey: qk.associationEvents, queryFn: listAssociationEvents, staleTime: 5 * 60_000 })
  const [all, setAll] = useState(false)
  const events = query.data?.events ?? []
  if (events.length === 0) return null
  const shown = all ? events : events.slice(0, SHOWN)
  return (
    <Paper withBorder p="md" mb={16} data-testid="association-events">
      <Group gap="xs" mb="sm">
        <IconBuildingCommunity size={18} />
        <Title order={4}>{t('associationEvents.title', 'Vom Verband')}</Title>
      </Group>
      <Stack gap="sm">
        {shown.map((ev) => (
          <Row key={`${ev.federationSlug}-${ev.id}`} ev={ev} />
        ))}
      </Stack>
      {events.length > SHOWN && (
        <Anchor component="button" size="sm" mt="sm" onClick={() => setAll(!all)}>
          {all
            ? t('associationEvents.less', 'Weniger anzeigen')
            : t('associationEvents.more', 'Alle {{count}} anzeigen', { count: events.length })}
        </Anchor>
      )}
    </Paper>
  )
}
