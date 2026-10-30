import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  TextInput,
  Textarea,
  Select,
  Switch,
  NumberInput,
  ColorInput,
  FileButton,
  Button,
  Stack,
  Group,
  SimpleGrid,
  Paper,
  Text,
  Title,
  Divider,
  Box,
} from '@mantine/core'
import { IconPhoto, IconTrash, IconUpload } from '@tabler/icons-react'
import { getClubSettings, updateClubSettings, type ClubSettings } from '@/api/admin'
import { useT } from '@/locales/i18n'
import { qk } from '@/data/keys'
import { useToast } from '@/context/AppContext'
import { ErrorBanner } from '@/components/ui'

const LOGO_TYPES = ['image/png', 'image/jpeg', 'image/webp', 'image/gif', 'image/svg+xml']
const LOGO_MAX_BYTES = 2 * 1024 * 1024
// What the app looks like without club colours (Hubra violet and gold).
const DEFAULT_COLORS = { primary: '#7441e0', accent: '#ecbb00' }

function ClubSettingsForm({ initialData }: { initialData: ClubSettings }) {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const [form, setForm] = useState<ClubSettings>(initialData)
  const [saving, setSaving] = useState(false)

  const update = (key: keyof ClubSettings, value: string | boolean | number | null) => {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  const pickLogo = (file: File | null) => {
    if (!file) return
    if (!LOGO_TYPES.includes(file.type)) {
      notify('error', t('clubSettings.logoWrongType', 'Bitte ein PNG-, JPEG-, WebP-, GIF- oder SVG-Bild wählen.'))
      return
    }
    if (file.size > LOGO_MAX_BYTES) {
      notify('error', t('clubSettings.logoTooLarge', 'Das Logo ist grösser als 2 MB.'))
      return
    }
    const reader = new FileReader()
    reader.onload = () => update('logo', reader.result as string)
    reader.readAsDataURL(file)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await updateClubSettings(form)
      queryClient.invalidateQueries({ queryKey: qk.settings.club })
      queryClient.invalidateQueries({ queryKey: qk.settings.clubProfile })
      notify('success', t('clubSettings.saved', 'Einstellungen gespeichert'))
    } catch (err: unknown) {
      notify(
        'error',
        t('clubSettings.saveFailed', 'Einstellungen nicht gespeichert'),
        err instanceof Error ? err.message : undefined,
      )
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
          <div>
            <Text fz="sm" fw={500} mb={6}>
              {t('clubSettings.logo', 'Logo')}
            </Text>
            <Group gap="md" wrap="nowrap" align="center">
              <Box
                w={72}
                h={72}
                style={{
                  flexShrink: 0,
                  borderRadius: 'var(--mantine-radius-md)',
                  border: '1px solid var(--hb-border)',
                  background: 'var(--hb-surface-2)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  overflow: 'hidden',
                }}
              >
                {form.logo ? (
                  <img
                    src={form.logo}
                    alt=""
                    style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
                  />
                ) : (
                  <IconPhoto size={28} color="var(--mantine-color-gray-5)" />
                )}
              </Box>
              <Stack gap={6} style={{ minWidth: 0 }}>
                <Group gap="xs">
                  <FileButton onChange={pickLogo} accept={LOGO_TYPES.join(',')}>
                    {(props) => (
                      <Button {...props} variant="light" leftSection={<IconUpload size={16} />}>
                        {form.logo
                          ? t('clubSettings.logoReplace', 'Logo ersetzen')
                          : t('clubSettings.logoUpload', 'Logo hochladen')}
                      </Button>
                    )}
                  </FileButton>
                  {form.logo && (
                    <Button
                      variant="subtle"
                      color="red"
                      leftSection={<IconTrash size={16} />}
                      onClick={() => update('logo', null)}
                    >
                      {t('clubSettings.logoRemove', 'Logo entfernen')}
                    </Button>
                  )}
                </Group>
                <Text fz="xs" c="dimmed">
                  {t(
                    'clubSettings.logoHint',
                    'PNG, JPEG, WebP, GIF oder SVG, höchstens 2 MB. Erscheint oben in der App, im Browser-Tab und bei «Meine Vereine».',
                  )}
                </Text>
              </Stack>
            </Group>
          </div>
          <SimpleGrid cols={{ base: 1, xs: 3 }} spacing={14}>
            <ColorInput
              label={t('clubSettings.primaryColor', 'Primärfarbe')}
              placeholder={DEFAULT_COLORS.primary}
              value={form.primary_color ?? ''}
              onChange={(v) => update('primary_color', v || null)}
              eyeDropperButtonProps={eyeDropperProps}
            />
            <ColorInput
              label={t('clubSettings.secondaryColor', 'Sekundärfarbe')}
              placeholder={t('common.none', 'Keine')}
              value={form.secondary_color ?? ''}
              onChange={(v) => update('secondary_color', v || null)}
              eyeDropperButtonProps={eyeDropperProps}
            />
            <ColorInput
              label={t('clubSettings.accentColor', 'Akzentfarbe')}
              placeholder={DEFAULT_COLORS.accent}
              value={form.accent_color ?? ''}
              onChange={(v) => update('accent_color', v || null)}
              eyeDropperButtonProps={eyeDropperProps}
            />
          </SimpleGrid>
          <Group justify="space-between" align="flex-start" wrap="nowrap" gap="md">
            <Text fz="xs" c="dimmed">
              {t(
                'clubSettings.colorsHint',
                'Die Primärfarbe färbt Schaltflächen, Links und das aktive Menü, die Akzentfarbe das Ankündigungsbanner und die Sekundärfarbe den Streifen unter der Kopfzeile.',
              )}
            </Text>
            <Button
              variant="subtle"
              size="xs"
              style={{ flexShrink: 0 }}
              onClick={() =>
                setForm((prev) => ({
                  ...prev,
                  primary_color: null,
                  secondary_color: null,
                  accent_color: null,
                }))
              }
            >
              {t('clubSettings.resetColors', 'Standardfarben')}
            </Button>
          </Group>
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
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: qk.settings.club,
    queryFn: getClubSettings,
  })

  if (isLoading) {
    return <Text p={20} c="dimmed">{t('clubSettings.loading', 'Einstellungen werden geladen …')}</Text>
  }
  // Saving over settings that never loaded would show empty fields as if
  // the club had none.
  if (error) {
    return (
      <ErrorBanner
        message={t('clubSettings.loadFailed', 'Die Einstellungen konnten nicht geladen werden.')}
        onRetry={() => refetch()}
      />
    )
  }

  return <ClubSettingsForm initialData={data ?? {}} />
}
