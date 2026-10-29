import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  TextInput,
  Textarea,
  Select,
  Switch,
  NumberInput,
  ColorInput,
  Button,
  Stack,
  Group,
  SimpleGrid,
  Paper,
  Text,
  Title,
  Divider,
} from '@mantine/core'
import { getClubSettings, updateClubSettings, type ClubSettings } from '@/api/admin'
import { useT } from '@/locales/i18n'
import { qk } from '@/data/keys'

function ClubSettingsForm({ initialData }: { initialData: ClubSettings }) {
  const { t } = useT()
  const queryClient = useQueryClient()
  const [form, setForm] = useState<ClubSettings>(initialData)
  const [saving, setSaving] = useState(false)

  const update = (key: keyof ClubSettings, value: string | boolean | number) => {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await updateClubSettings(form)
      queryClient.invalidateQueries({ queryKey: qk.settings.club })
      queryClient.invalidateQueries({ queryKey: qk.settings.clubProfile })
    } finally {
      setSaving(false)
    }
  }

  const eyeDropperProps = { 'aria-label': t('clubSettings.pickColor') }

  return (
    <Stack gap={20}>
      <Paper withBorder p="lg">
        <Title order={3} mb="md">{t('clubSettings.identity', 'Vereinsprofil')}</Title>
        <Stack gap={14}>
          <TextInput
            label={t('clubSettings.clubName', 'Vereinsname')}
            value={form.club_name ?? ''}
            onChange={(e) => update('club_name', e.target.value)}
          />
          <Textarea
            label={t('clubSettings.description', 'Beschreibung')}
            value={form.club_description ?? ''}
            onChange={(e) => update('club_description', e.target.value)}
            rows={3}
          />
        </Stack>
      </Paper>

      <Paper withBorder p="lg">
        <Title order={3} mb="md">{t('clubSettings.branding', 'Erscheinungsbild')}</Title>
        <Stack gap={14}>
          <SimpleGrid cols={{ base: 1, xs: 3 }} spacing={14}>
            <ColorInput
              label={t('clubSettings.primaryColor', 'Primärfarbe')}
              value={form.primary_color ?? '#7441e0'}
              onChange={(v) => update('primary_color', v)}
              eyeDropperButtonProps={eyeDropperProps}
            />
            <ColorInput
              label={t('clubSettings.secondaryColor', 'Sekundärfarbe')}
              value={form.secondary_color ?? '#2596be'}
              onChange={(v) => update('secondary_color', v)}
              eyeDropperButtonProps={eyeDropperProps}
            />
            <ColorInput
              label={t('clubSettings.accentColor', 'Akzentfarbe')}
              value={form.accent_color ?? '#f59e0b'}
              onChange={(v) => update('accent_color', v)}
              eyeDropperButtonProps={eyeDropperProps}
            />
          </SimpleGrid>
        </Stack>
      </Paper>

      <Paper withBorder p="lg">
        <Title order={3} mb="md">{t('clubSettings.localization', 'Region und Sprache')}</Title>
        <SimpleGrid cols={{ base: 1, sm: 3 }} spacing={14}>
          <Select
            label={t('clubSettings.timezone', 'Zeitzone')}
            value={form.timezone ?? 'Europe/Zurich'}
            onChange={(v) => v && update('timezone', v)}
            data={[
              'Europe/Zurich',
              'Europe/London',
              'Europe/Paris',
              'Europe/Berlin',
              'Europe/Vienna',
              'UTC',
            ]}
          />
          <Select
            label={t('clubSettings.locale', 'Sprache')}
            value={form.locale ?? 'de-CH'}
            onChange={(v) => v && update('locale', v)}
            data={[
              { value: 'de-CH', label: 'Deutsch (Schweiz)' },
              { value: 'en-GB', label: 'English' },
              { value: 'de-DE', label: 'Deutsch (Deutschland)' },
              { value: 'fr-FR', label: 'Français' },
              { value: 'it-IT', label: 'Italiano' },
            ]}
          />
          <Select
            label={t('clubSettings.dateFormat', 'Datumsformat')}
            value={form.date_format ?? 'DD.MM.YYYY'}
            onChange={(v) => v && update('date_format', v)}
            data={['DD.MM.YYYY', 'YYYY-MM-DD', 'DD/MM/YYYY', 'MM/DD/YYYY']}
          />
        </SimpleGrid>
      </Paper>

      <Paper withBorder p="lg">
        <Title order={3} mb="md">{t('clubSettings.privacy', 'Privatsphäre')}</Title>
        <Stack gap={14}>
          <Switch
            label={t('clubSettings.directoryVisible', 'Mitgliederverzeichnis für alle Mitglieder sichtbar')}
            checked={form.member_directory_visible ?? false}
            onChange={(e) => update('member_directory_visible', e.currentTarget.checked)}
          />
          <Switch
            label={t('clubSettings.publicGroups', 'Gruppen öffentlich auflisten')}
            checked={form.public_group_listing ?? false}
            onChange={(e) => update('public_group_listing', e.currentTarget.checked)}
          />
        </Stack>
      </Paper>

      <Paper withBorder p="lg">
        <Title order={3} mb="md">{t('clubSettings.membership', 'Mitgliedschaft')}</Title>
        <Switch
          label={t('clubSettings.leaveRequiresApproval', 'Austritt nur mit Bestätigung')}
          description={t(
            'clubSettings.leaveRequiresApprovalHint',
            'Ein: Mitglieder beantragen den Austritt, und ihr bestätigt ihn unter Mitglieder › Anträge. Aus: Mitglieder treten sofort selbst aus.',
          )}
          checked={form.leave_requires_approval ?? false}
          onChange={(e) => update('leave_requires_approval', e.currentTarget.checked)}
        />
        <Switch
          mt={14}
          label={t('clubSettings.joinRequestsOpen', 'Beitrittsanfragen annehmen')}
          description={t(
            'clubSettings.joinRequestsOpenHint',
            'Aus: Neue Mitglieder kommen nur noch über eine Einladung dazu, und auf join.hubra.club steht «Nur auf Einladung».',
          )}
          checked={form.join_requests_open ?? true}
          onChange={(e) => update('join_requests_open', e.currentTarget.checked)}
        />
        <NumberInput
          mt={14}
          maw={240}
          label={t('clubSettings.inviteValidDays', 'Einladungen gültig (Tage)')}
          min={1}
          max={60}
          value={form.invite_valid_days ?? 14}
          onChange={(v) => typeof v === 'number' && update('invite_valid_days', v)}
        />
      </Paper>

      <Paper withBorder p="lg">
        <Title order={3} mb="md">{t('clubSettings.banner', 'Ankündigungsbanner')}</Title>
        <Stack gap={14}>
          <Switch
            label={t('clubSettings.showBanner', 'Banner anzeigen')}
            checked={form.announcement_banner_active ?? false}
            onChange={(e) => update('announcement_banner_active', e.currentTarget.checked)}
          />
          <TextInput
            label={t('clubSettings.bannerText', 'Bannertext')}
            value={form.announcement_banner_text ?? ''}
            onChange={(e) => update('announcement_banner_text', e.target.value)}
            placeholder={t('clubSettings.bannerPlaceholder', 'Generalversammlung am Freitag!')}
          />
        </Stack>
      </Paper>

      <Divider />
      <Group justify="flex-end">
        <Button loading={saving} onClick={handleSave}>
          {t('clubSettings.save', 'Einstellungen speichern')}
        </Button>
      </Group>
    </Stack>
  )
}

export function ClubSettingsTab() {
  const { t } = useT()
  const { data, isLoading } = useQuery({
    queryKey: qk.settings.club,
    queryFn: getClubSettings,
  })

  if (isLoading) {
    return <Text p={20} c="dimmed">{t('clubSettings.loading', 'Einstellungen werden geladen …')}</Text>
  }

  return <ClubSettingsForm initialData={data ?? {}} />
}
