import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  TextInput,
  Textarea,
  Select,
  Switch,
  ColorInput,
  Button,
  Stack,
  Group,
  Paper,
  Text,
  Title,
  Divider,
} from '@mantine/core'
import { getClubSettings, updateClubSettings, type ClubSettings } from '@/api/admin'

function ClubSettingsForm({ initialData }: { initialData: ClubSettings }) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<ClubSettings>(initialData)
  const [saving, setSaving] = useState(false)

  const update = (key: keyof ClubSettings, value: string | boolean) => {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await updateClubSettings(form)
      queryClient.invalidateQueries({ queryKey: ['club-settings'] })
    } finally {
      setSaving(false)
    }
  }

  return (
    <Stack gap={20}>
      <Paper withBorder shadow="sm" radius="lg" p="lg">
        <Title order={3} mb={16}>Club Identity</Title>
        <Stack gap={14}>
          <TextInput
            label="Club Name"
            value={form.club_name ?? ''}
            onChange={(e) => update('club_name', e.target.value)}
          />
          <Textarea
            label="Description"
            value={form.club_description ?? ''}
            onChange={(e) => update('club_description', e.target.value)}
            rows={3}
          />
        </Stack>
      </Paper>

      <Paper withBorder shadow="sm" radius="lg" p="lg">
        <Title order={3} mb={16}>Branding</Title>
        <Stack gap={14}>
          <Group gap={14} grow>
            <ColorInput
              label="Primary Color"
              value={form.primary_color ?? '#7441e0'}
              onChange={(v) => update('primary_color', v)}
            />
            <ColorInput
              label="Secondary Color"
              value={form.secondary_color ?? '#2596be'}
              onChange={(v) => update('secondary_color', v)}
            />
            <ColorInput
              label="Accent Color"
              value={form.accent_color ?? '#f59e0b'}
              onChange={(v) => update('accent_color', v)}
            />
          </Group>
        </Stack>
      </Paper>

      <Paper withBorder shadow="sm" radius="lg" p="lg">
        <Title order={3} mb={16}>Localization</Title>
        <Group gap={14} grow>
          <Select
            label="Timezone"
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
            label="Locale"
            value={form.locale ?? 'de-CH'}
            onChange={(v) => v && update('locale', v)}
            data={['de-CH', 'en-GB', 'de-DE', 'fr-FR', 'it-IT']}
          />
          <Select
            label="Date Format"
            value={form.date_format ?? 'DD.MM.YYYY'}
            onChange={(v) => v && update('date_format', v)}
            data={['DD.MM.YYYY', 'YYYY-MM-DD', 'DD/MM/YYYY', 'MM/DD/YYYY']}
          />
        </Group>
      </Paper>

      <Paper withBorder shadow="sm" radius="lg" p="lg">
        <Title order={3} mb={16}>Privacy</Title>
        <Stack gap={14}>
          <Switch
            label="Member directory visible to all members"
            checked={form.member_directory_visible ?? false}
            onChange={(e) => update('member_directory_visible', e.currentTarget.checked)}
          />
          <Switch
            label="Public group listing"
            checked={form.public_group_listing ?? false}
            onChange={(e) => update('public_group_listing', e.currentTarget.checked)}
          />
        </Stack>
      </Paper>

      <Paper withBorder shadow="sm" radius="lg" p="lg">
        <Title order={3} mb={16}>Announcement Banner</Title>
        <Stack gap={14}>
          <Switch
            label="Show banner"
            checked={form.announcement_banner_active ?? false}
            onChange={(e) => update('announcement_banner_active', e.currentTarget.checked)}
          />
          <TextInput
            label="Banner Text"
            value={form.announcement_banner_text ?? ''}
            onChange={(e) => update('announcement_banner_text', e.target.value)}
            placeholder="Annual meeting on Friday!"
          />
        </Stack>
      </Paper>

      <Divider />
      <Group justify="flex-end">
        <Button loading={saving} onClick={handleSave}>
          Save Settings
        </Button>
      </Group>
    </Stack>
  )
}

export function ClubSettingsTab() {
  const { data, isLoading } = useQuery({
    queryKey: ['club-settings'],
    queryFn: getClubSettings,
  })

  if (isLoading) {
    return <Text p={20} c="dimmed">Loading settings...</Text>
  }

  return <ClubSettingsForm initialData={data ?? {}} />
}
