import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Badge, Button, Group, Paper, Stack, Switch, Text, Title } from '@mantine/core'
import {
  endClubApiToken,
  getApiAccessSettings,
  listClubApiTokens,
  saveApiAccessSettings,
  type ApiAccessSettings,
  type ClubApiToken,
} from '@/api/apiTokens'
import { ConfirmModal } from '@/components/ui'
import { useToast } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { formatDateTime } from '@/format'
import { useT } from '@/locales/i18n'

/**
 * Einstellungen › API & Apps: who may reach the club's data from outside
 * (docs/api-tokens.md, docs/oauth.md). Two switches (members' own access,
 * AI assistants such as Claude) and every token and app sign-in of the
 * club, each of which an admin can end.
 */
export function ApiAccessTab() {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const [endTarget, setEndTarget] = useState<ClubApiToken | null>(null)
  const [saving, setSaving] = useState<keyof ApiAccessSettings | null>(null)

  const settings = useQuery({ queryKey: qk.settings.apiAccess, queryFn: getApiAccessSettings })
  const tokens = useQuery({ queryKey: qk.settings.apiTokens, queryFn: listClubApiTokens })

  const toggle = async (field: keyof ApiAccessSettings, value: boolean) => {
    setSaving(field)
    try {
      await saveApiAccessSettings({ [field]: value })
      await queryClient.invalidateQueries({ queryKey: qk.settings.apiAccess })
      notify('success', t('apiAccess.saved', 'Gespeichert'))
    } catch (err) {
      notify('error', t('apiAccess.saveFailed', 'Nicht gespeichert'), err instanceof Error ? err.message : undefined)
    } finally {
      setSaving(null)
    }
  }

  const end = async (row: ClubApiToken) => {
    try {
      await endClubApiToken(row.id)
      await queryClient.invalidateQueries({ queryKey: qk.settings.apiTokens })
      notify('success', t('apiAccess.ended', 'Zugang beendet'))
    } catch (err) {
      notify('error', t('apiAccess.endFailed', 'Beenden fehlgeschlagen'), err instanceof Error ? err.message : undefined)
    }
  }

  const active = (tokens.data?.items ?? []).filter((r) => r.active)
  const kindLabel = (row: ClubApiToken) =>
    row.appId
      ? t('apiAccess.kind.app', 'App')
      : row.kind === 'club'
        ? t('apiAccess.kind.club', 'Vereins-Token')
        : t('apiAccess.kind.personal', 'Persönliches Token')

  return (
    <Stack gap="lg">
      <Text c="dimmed" size="sm">
        {t(
          'apiAccess.intro',
          'Apps, Skripte und KI-Assistenten, die Daten des Vereins lesen dürfen. Sie haben nie mehr Rechte als die Person, für die sie handeln, und jeder Zugriff steht im Protokoll.',
        )}
      </Text>

      <Paper withBorder p="lg">
        <Stack gap="md">
          <Title order={4}>{t('apiAccess.switches', 'Wer darf?')}</Title>
          <Switch
            label={t('apiAccess.members', 'Mitglieder dürfen Apps verbinden und eigene Tokens erstellen')}
            description={t(
              'apiAccess.membersHint',
              'Aus: nur Admins. Ein Mitglied sieht über eine App nur, was es auch selbst sieht.',
            )}
            checked={settings.data?.membersAllowed ?? false}
            disabled={!settings.data || saving !== null}
            onChange={(e) => void toggle('membersAllowed', e.currentTarget.checked)}
          />
          <Switch
            label={t('apiAccess.ai', 'KI-Assistenten erlauben (Claude-Connector)')}
            description={t(
              'apiAccess.aiHint',
              'Claude darf dann für Personen, die es selbst verbinden, Daten des Vereins lesen. Es kann nichts ändern. Aus: der Connector bekommt keine Daten des Vereins.',
            )}
            checked={settings.data?.aiAllowed ?? false}
            disabled={!settings.data || saving !== null}
            onChange={(e) => void toggle('aiAllowed', e.currentTarget.checked)}
          />
        </Stack>
      </Paper>

      <Stack gap="sm">
        <Title order={4}>{t('apiAccess.active', 'Aktive Zugänge')}</Title>
        {tokens.data && active.length === 0 && (
          <Text size="sm" c="dimmed">
            {t('apiAccess.none', 'Keine App und kein Token hat Zugang.')}
          </Text>
        )}
        {active.map((row) => (
          <Paper key={row.id} withBorder p="md">
            <Group justify="space-between" wrap="nowrap">
              <div style={{ minWidth: 0 }}>
                <Group gap="xs" wrap="nowrap">
                  <Text fw={600} truncate>
                    {row.name}
                  </Text>
                  <Badge size="sm" variant="light" color={row.appId ? 'violet' : 'gray'}>
                    {kindLabel(row)}
                  </Badge>
                </Group>
                <Text size="xs" c="dimmed">
                  {row.createdByName} · {t('apiAccess.until', 'bis')}{' '}
                  {row.expiresAt ? formatDateTime(row.expiresAt) : '–'} ·{' '}
                  {row.lastUsedAt
                    ? `${t('apiAccess.lastUsed', 'zuletzt genutzt')} ${formatDateTime(row.lastUsedAt)}`
                    : t('apiAccess.unused', 'noch nicht genutzt')}
                </Text>
              </div>
              <Button
                variant="subtle"
                color="red"
                size="xs"
                style={{ flexShrink: 0 }}
                onClick={() => setEndTarget(row)}
              >
                {t('apiAccess.end', 'Beenden')}
              </Button>
            </Group>
          </Paper>
        ))}
      </Stack>

      <ConfirmModal
        open={endTarget !== null}
        title={t('apiAccess.endTitle', 'Zugang beenden?')}
        body={t(
          'apiAccess.endBody',
          'Die App oder das Skript kann danach nichts mehr lesen. Wer es nutzt, muss neu verbinden.',
        )}
        onConfirm={() => {
          if (endTarget) void end(endTarget)
          setEndTarget(null)
        }}
        onClose={() => setEndTarget(null)}
      />
    </Stack>
  )
}
