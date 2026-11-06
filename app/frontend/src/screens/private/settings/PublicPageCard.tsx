import { Anchor, Group, Paper, Stack, Switch, Text, TextInput, Title } from '@mantine/core'
import { IconExternalLink } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useInstance } from '@/context/InstanceContext'
import { URL_CLUB } from '@/clubBase'

/** Settings › Membership: the club's public page on the join portal. */
export function PublicPageCard({
  on,
  website,
  onToggle,
  onWebsite,
}: {
  on: boolean
  website: string
  onToggle: (on: boolean) => void
  onWebsite: (url: string) => void
}) {
  const { t } = useT()
  const { ssoUrl } = useInstance()
  const pageUrl = URL_CLUB && ssoUrl ? `${ssoUrl.replace(/\/$/, '')}/clubs/${URL_CLUB}` : null

  return (
    <Paper withBorder p="lg" data-testid="public-page-card">
      <Title order={3} mb="md">
        {t('clubSettings.publicPage.title', 'Öffentliche Vereinsseite')}
      </Title>
      <Stack gap={14}>
        <Switch
          label={t('clubSettings.publicPage.switch', 'Vereinsseite für alle sichtbar')}
          description={t(
            'clubSettings.publicPage.hint',
            'Name, Logo, Beschreibung, eure öffentlichen Anlässe und ein Knopf «Mitglied werden», ohne Anmeldung. Gruppen nur, wenn «Gruppen öffentlich auflisten» an ist. Mitglieder und ihre Daten erscheinen nie.',
          )}
          checked={on}
          onChange={(e) => onToggle(e.currentTarget.checked)}
        />
        <TextInput
          maw={420}
          label={t('clubSettings.publicPage.website', 'Website des Vereins')}
          placeholder="https://"
          value={website}
          onChange={(e) => onWebsite(e.currentTarget.value)}
        />
        {on && pageUrl && (
          <Group gap={6}>
            <Text fz="sm" c="dimmed">
              {t('clubSettings.publicPage.link', 'Eure Seite:')}
            </Text>
            <Anchor href={pageUrl} target="_blank" rel="noopener noreferrer" fz="sm">
              <Group gap={4} component="span">
                {pageUrl.replace(/^https?:\/\//, '')}
                <IconExternalLink size={14} />
              </Group>
            </Anchor>
          </Group>
        )}
        <Text fz="xs" c="dimmed">
          {t(
            'clubSettings.publicPage.widgetHint',
            'Eure öffentlichen Anlässe auf der eigenen Website: den Code dafür findet ihr unter Anlässe › Kalender abonnieren.',
          )}
        </Text>
      </Stack>
    </Paper>
  )
}
