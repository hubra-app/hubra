import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Paper, Switch, Group, Text, Stack } from '@mantine/core'
import { useT } from '@/locales/i18n'
import { useToast, useAuth } from '@/context/AppContext'
import { getFeatures, updateFeature } from '@/api/features'
import { FeatureSettingsModal } from '@/screens/private/settings/FeatureSettingsModal'

export function FeaturesTab() {
  const { t } = useT()
  const { notify } = useToast()
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const canWrite = hasPermission('features.features.write')

  const [modalFeature, setModalFeature] = useState<{
    key: string
    label: string
  } | null>(null)

  const { data: flags = [] } = useQuery({
    queryKey: ['features'],
    queryFn: getFeatures,
  })

  const handleToggle = async (key: string, enabled: boolean, label: string) => {
    if (!enabled) {
      try {
        await updateFeature(key, false)
        await queryClient.invalidateQueries({ queryKey: ['features'] })
        notify('success', 'Feature disabled', key)
      } catch {
        notify('error', 'Failed to update feature', key)
      }
      return
    }

    try {
      const updated = await updateFeature(key, true)
      await queryClient.invalidateQueries({ queryKey: ['features'] })
      if (updated.requiresConfiguration) {
        setModalFeature({ key, label })
        notify(
          'info',
          t('settings.featureConfigRequired', 'Configuration required'),
          t(
            'settings.featureConfigRequiredMsg',
            '{{label}} needs configuration before it can be used.',
            { label },
          ),
        )
      } else {
        notify('success', 'Feature enabled', key)
      }
    } catch {
      notify('error', 'Failed to update feature', key)
    }
  }

  const handleSkip = async () => {
    if (!modalFeature) return
    try {
      await updateFeature(modalFeature.key, false)
      await queryClient.invalidateQueries({ queryKey: ['features'] })
      notify(
        'info',
        t(
          'settings.featureDisabledSkipped',
          'Feature disabled — configuration required',
        ),
        t(
          'settings.featureDisabledSkippedMsg',
          '{{label}} was disabled because the required settings were not provided.',
          { label: modalFeature.label },
        ),
      )
    } catch {
      notify('error', 'Failed to disable feature', modalFeature.key)
    }
    setModalFeature(null)
  }

  const handleSaved = async () => {
    await queryClient.invalidateQueries({ queryKey: ['features'] })
    await queryClient.invalidateQueries({ queryKey: ['setup-status'] })
    setModalFeature(null)
  }

  return (
    <Paper withBorder shadow="sm" radius="lg" style={{ padding: 20 }}>
      <Stack gap="md">
        {flags.map((flag) => (
          <Group
            key={flag.key}
            justify="space-between"
            align="flex-start"
            style={{
              padding: '16px 0',
              borderBottom: `1px solid var(--mantine-color-gray-2)`,
            }}
          >
            <Stack gap={2}>
              <Text fw={600} fz="sm">
                {flag.label ?? flag.key}
              </Text>
              {flag.description && (
                <Text fz="xs" c="dimmed">
                  {flag.description}
                </Text>
              )}
            </Stack>
            <Switch
              checked={flag.enabled}
              disabled={!canWrite}
              onChange={(e) =>
                handleToggle(
                  flag.key,
                  e.currentTarget.checked,
                  flag.label ?? flag.key,
                )
              }
              size="md"
            />
          </Group>
        ))}
        {flags.length === 0 && (
          <Text c="dimmed" ta="center" py={20}>
            {t('settings.noFeatures', 'No feature flags configured')}
          </Text>
        )}
      </Stack>

      {modalFeature && (
        <FeatureSettingsModal
          featureKey={modalFeature.key}
          featureLabel={modalFeature.label}
          open={true}
          onSkip={handleSkip}
          onSaved={handleSaved}
        />
      )}
    </Paper>
  )
}
