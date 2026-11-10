import { Anchor, Badge, Button, Group, Paper, SimpleGrid, Stack, Text, Title } from '@mantine/core'
import { IconCalendarEvent, IconExternalLink, IconMapPin, IconUsersGroup } from '@tabler/icons-react'
import { Link } from 'react-router-dom'
import { useLang } from '@/lang'
import type { PublicClub } from '@/api/publicClub'

/** The club's public information: description, events, groups, trial link. */
export function PublicClubDetails({ club }: { club: PublicClub }) {
  const { tr, lang } = useLang()
  const day = (iso: string) =>
    new Date(`${iso}T00:00:00Z`).toLocaleDateString(lang === 'en' ? 'en-GB' : 'de-CH', {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      timeZone: 'UTC',
    })

  return (
    <Stack gap="lg">
      {(club.description || club.website) && (
        <Stack gap={6}>
          {club.description && (
            <Text style={{ whiteSpace: 'pre-line' }}>{club.description}</Text>
          )}
          {club.website && (
            <Anchor href={club.website} target="_blank" rel="noopener noreferrer" size="sm">
              <Group gap={4} component="span">
                {club.website.replace(/^https?:\/\//, '').replace(/\/$/, '')}
                <IconExternalLink size={14} />
              </Group>
            </Anchor>
          )}
        </Stack>
      )}

      {club.trials && (
        <Paper withBorder p="md" radius="md">
          <Group justify="space-between" wrap="wrap" gap="sm">
            <Text size="sm" style={{ flex: 1, minWidth: 200 }}>
              {tr(
                'Lust, es auszuprobieren? Melde dich für ein Schnuppertraining an, ohne Konto.',
                'Want to try it out? Book a trial training, no account needed.',
              )}
            </Text>
            <Button component={Link} to={`/clubs/${club.slug}/trial`} variant="light">
              {tr('Schnuppertraining buchen', 'Book a trial training')}
            </Button>
          </Group>
        </Paper>
      )}

      <Stack gap="xs">
        <Group justify="space-between">
          <Title order={4}>
            <Group gap={8} component="span">
              <IconCalendarEvent size={18} />
              {tr('Öffentliche Anlässe', 'Public events')}
            </Group>
          </Title>
          {club.calendar && (
            <Anchor href={club.calendar.replace(/^https?:/, 'webcal:')} size="sm">
              {tr('Kalender abonnieren', 'Subscribe')}
            </Anchor>
          )}
        </Group>
        {club.events.length === 0 ? (
          <Text size="sm" c="dimmed">
            {tr('Zurzeit keine öffentlichen Anlässe.', 'No public events at the moment.')}
          </Text>
        ) : (
          <Stack gap={0}>
            {club.events.map((e) => (
              <Group
                key={e.id}
                wrap="nowrap"
                align="flex-start"
                gap="md"
                py="sm"
                style={{ borderBottom: '1px solid var(--mantine-color-default-border)' }}
              >
                <Badge variant="light" radius="sm" size="lg" style={{ minWidth: 104, flex: 'none' }}>
                  {day(e.date)}
                </Badge>
                <div style={{ minWidth: 0 }}>
                  <Text fw={600}>{e.title}</Text>
                  {(e.time || e.location) && (
                    <Group gap={6} c="dimmed">
                      {e.time && <Text size="sm">{e.time}</Text>}
                      {e.location && (
                        <Group gap={2}>
                          <IconMapPin size={14} />
                          <Text size="sm">{e.location}</Text>
                        </Group>
                      )}
                    </Group>
                  )}
                  {e.description && (
                    <Text size="sm" c="dimmed" lineClamp={2}>
                      {e.description}
                    </Text>
                  )}
                </div>
              </Group>
            ))}
          </Stack>
        )}
      </Stack>

      {club.groups.length > 0 && (
        <Stack gap="xs">
          <Title order={4}>
            <Group gap={8} component="span">
              <IconUsersGroup size={18} />
              {tr('Gruppen', 'Groups')}
            </Group>
          </Title>
          <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm">
            {club.groups.map((g) => (
              <Paper key={g.name} withBorder p="sm" radius="md">
                <Text fw={600}>{g.name}</Text>
                {(g.sessions || g.description) && (
                  <Text size="sm" c="dimmed">
                    {[g.sessions, g.description].filter(Boolean).join(' · ')}
                  </Text>
                )}
              </Paper>
            ))}
          </SimpleGrid>
        </Stack>
      )}
    </Stack>
  )
}
