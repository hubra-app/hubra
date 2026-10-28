import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Modal as MantineModal,
  TextInput,
  PasswordInput,
  Button,
  Text,
  Group,
  Stack,
  ScrollArea,
  Alert,
  Box,
} from '@mantine/core'
import { IconAlertTriangle } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useToast } from '@/context/AppContext'
import { getFeatureSettings, saveFeatureSettings } from '@/api/features'

export function FeatureSettingsModal({
  featureKey,
  featureLabel,
  open,
  onSkip,
  onSaved,
}: {
  featureKey: string
  featureLabel: string
  open: boolean
  onSkip: () => void
  onSaved: () => void
}) {
  const { t } = useT()
  const { notify } = useToast()

  const { data, isPending } = useQuery({
    queryKey: ['feature-settings', featureKey],
    queryFn: () => getFeatureSettings(featureKey),
    enabled: open,
  })

  const [values, setValues] = useState<Record<string, string>>({})
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [touched, setTouched] = useState(false)
  const [busy, setBusy] = useState(false)

  const fields = data?.settings ?? []

  const [prevData, setPrevData] = useState(data)
  if (data !== prevData) {
    setPrevData(data)
    if (data) {
      const init: Record<string, string> = {}
      for (const f of data.settings) init[f.key] = f.value ?? ''
      setValues(init)
      setErrors({})
      setTouched(false)
    }
  }

  const handleChange = (key: string, value: string) => {
    setValues((prev) => ({ ...prev, [key]: value }))
    if (touched && !value.trim()) {
      setErrors((prev) => ({
        ...prev,
        [key]: t('common.required', 'Required'),
      }))
    } else {
      setErrors((prev) => {
        if (!prev[key]) return prev
        const next = { ...prev }
        delete next[key]
        return next
      })
    }
  }

  const handleSave = async () => {
    setTouched(true)
    const newErrors: Record<string, string> = {}
    for (const f of fields) {
      if (!(values[f.key] ?? '').trim()) {
        newErrors[f.key] = t('common.required', 'Required')
      }
    }
    setErrors(newErrors)
    if (Object.keys(newErrors).length > 0) return

    setBusy(true)
    try {
      await saveFeatureSettings(featureKey, values)
      notify(
        'success',
        t('settings.featureEnabledConfigured', 'Feature enabled & configured'),
        t(
          'settings.featureEnabledConfiguredMsg',
          '{{label}} is now ready to use.',
          { label: featureLabel },
        ),
      )
      onSaved()
    } catch {
      notify(
        'error',
        t('common.updateFailed', 'Update fehlgeschlage'),
        t(
          'settings.featureSettingsSaveFailed',
          'Settings chönnet nöd gspeichert wärde.',
        ),
      )
    } finally {
      setBusy(false)
    }
  }

  const handleSkip = () => {
    onSkip()
  }

  const handleClose = () => {
    handleSkip()
  }

  return (
    <MantineModal
      opened={open}
      onClose={handleClose}
      title={t('settings.featureSettingsTitle', 'Configure {{label}}', {
        label: featureLabel,
      })}
      size={520}
      centered
      closeOnClickOutside={false}
      closeOnEscape={false}
      withCloseButton={false}
    >
      <Stack gap="sm">
        <Text size="sm" c="dimmed">
          {t(
            'settings.featureSettingsSubtitle',
            'Fill in the required settings to use this feature. Skipping disables it.',
          )}
        </Text>

        {isPending && (
          <Text size="sm" c="dimmed">
            {t('common.loading', 'Laden…')}
          </Text>
        )}

        {fields.length === 0 && !isPending && (
          <Alert color="blue" variant="light">
            {t('setup.noSettings', 'No settings required for this feature.')}
          </Alert>
        )}

        <ScrollArea.Autosize mah="55vh" type="auto">
          <Stack gap="sm">
            {fields.map((field) => (
              <Box key={field.key}>
                <Text component="label" size="sm" fw={500}>
                  {field.label}
                </Text>
                {field.description && (
                  <Text size="xs" c="dimmed" mb={4}>
                    {field.description}
                  </Text>
                )}
                {field.sensitive ? (
                  <PasswordInput
                    value={values[field.key] ?? ''}
                    onChange={(e) =>
                      handleChange(field.key, e.currentTarget.value)
                    }
                    error={errors[field.key]}
                    disabled={busy}
                  />
                ) : (
                  <TextInput
                    value={values[field.key] ?? ''}
                    onChange={(e) =>
                      handleChange(field.key, e.currentTarget.value)
                    }
                    error={errors[field.key]}
                    disabled={busy}
                  />
                )}
              </Box>
            ))}
          </Stack>
        </ScrollArea.Autosize>

        {Object.keys(errors).length > 0 && touched && (
          <Alert
            color="red"
            variant="light"
            icon={<IconAlertTriangle size={16} />}
          >
            {t(
              'settings.featureSettingsRequired',
              'Please fill in all required fields.',
            )}
          </Alert>
        )}
      </Stack>

      <Group justify="space-between" mt="lg">
        <Button
          variant="subtle"
          color="red"
          onClick={handleSkip}
          disabled={busy}
        >
          {t('settings.skip', 'Skip')}
        </Button>
        <Button variant="filled" onClick={handleSave} loading={busy}>
          {busy
            ? t('common.saving', 'Saving...')
            : t('settings.saveAndEnable', 'Save & enable')}
        </Button>
      </Group>
    </MantineModal>
  )
}
