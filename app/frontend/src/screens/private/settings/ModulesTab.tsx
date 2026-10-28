import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Badge,
  Button,
  Group,
  Modal,
  NumberInput,
  Paper,
  PasswordInput,
  Select,
  Stack,
  Switch,
  Text,
  TextInput,
} from '@mantine/core'
import { useT } from '@/locales/i18n'
import { useAuth, useToast } from '@/context/AppContext'
import {
  getModules,
  saveModuleSettings,
  setModuleEnabled,
  type ModuleInfo,
  type ModuleSettingField,
} from '@/api/modules'

type FormValue = string | number | boolean | null

export function ModulesTab() {
  const { t } = useT()
  const { notify } = useToast()
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const canWrite = hasPermission('modules.modules.write')
  const [editing, setEditing] = useState<ModuleInfo | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  const { data: modules = [] } = useQuery({
    queryKey: ['modules'],
    queryFn: getModules,
  })
  const byCode = Object.fromEntries(modules.map((m) => [m.code, m]))
  const optional = modules.filter((m) => !m.required)
  const required = modules.filter((m) => m.required)

  const toggle = async (m: ModuleInfo, enabled: boolean) => {
    setBusy(m.code)
    try {
      const updated = await setModuleEnabled(m.code, enabled)
      await queryClient.invalidateQueries({ queryKey: ['modules'] })
      notify(
        'success',
        enabled
          ? t('settings.modules.switchedOn', '{{name}} switched on', { name: m.name })
          : t('settings.modules.switchedOff', '{{name}} switched off', { name: m.name }),
      )
      if (enabled && updated.settings.length > 0 && !updated.configured) {
        setEditing(updated)
      }
    } catch (err) {
      notify('error', m.name, (err as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const describeBlocker = (m: ModuleInfo): string | null => {
    if (!m.allowed) return t('settings.modules.blocked', 'Not available for this club')
    if (m.switchedOn && m.missingDependencies.length > 0)
      return t('settings.modules.needs', 'Needs {{names}}', {
        names: m.missingDependencies.map((c) => byCode[c]?.name ?? c).join(', '),
      })
    return null
  }

  return (
    <Paper withBorder shadow="sm" radius="lg" style={{ padding: 20 }}>
      <Stack gap={0}>
        <Text fz="sm" c="dimmed" mb="sm">
          {t(
            'settings.modules.intro',
            'Switch off what your club does not use. Switching a module off hides it for everyone; its data is kept and comes back when you switch it on again.',
          )}
        </Text>
        {optional.map((m) => {
          const blocker = describeBlocker(m)
          return (
            <Group
              key={m.code}
              justify="space-between"
              align="flex-start"
              wrap="nowrap"
              style={{
                padding: '14px 0',
                borderBottom: '1px solid var(--mantine-color-gray-2)',
              }}
            >
              <Stack gap={4}>
                <Group gap={8}>
                  <Text fw={600} fz="sm">
                    {m.name}
                  </Text>
                  {blocker && (
                    <Badge size="sm" color="orange" variant="light">
                      {blocker}
                    </Badge>
                  )}
                  {m.enabled && m.settings.length > 0 && !m.configured && (
                    <Badge size="sm" color="red" variant="light">
                      {t('settings.modules.needsSetup', 'Needs setup')}
                    </Badge>
                  )}
                </Group>
                <Text fz="xs" c="dimmed">
                  {m.description}
                </Text>
                {m.dependsOn.some((d) => !byCode[d]?.required) && (
                  <Text fz="xs" c="dimmed">
                    {t('settings.modules.uses', 'Uses {{names}}', {
                      names: m.dependsOn
                        .filter((d) => !byCode[d]?.required)
                        .map((d) => byCode[d]?.name ?? d)
                        .join(', '),
                    })}
                  </Text>
                )}
              </Stack>
              <Group gap="sm" wrap="nowrap">
                {m.settings.length > 0 && m.enabled && canWrite && (
                  <Button size="xs" variant="default" onClick={() => setEditing(m)}>
                    {t('settings.modules.configure', 'Settings')}
                  </Button>
                )}
                <Switch
                  checked={m.switchedOn && m.allowed}
                  disabled={!canWrite || !m.allowed || busy === m.code}
                  onChange={(e) => toggle(m, e.currentTarget.checked)}
                  size="md"
                  aria-label={m.name}
                />
              </Group>
            </Group>
          )
        })}
        {required.length > 0 && (
          <Text fz="xs" c="dimmed" mt="md">
            {t('settings.modules.alwaysOn', 'Always on: {{names}}', {
              names: required.map((m) => m.name).join(', '),
            })}
          </Text>
        )}
      </Stack>
      {editing && (
        <ModuleSettingsModal
          module={editing}
          onClose={() => setEditing(null)}
          onSaved={async () => {
            await queryClient.invalidateQueries({ queryKey: ['modules'] })
            setEditing(null)
          }}
        />
      )}
    </Paper>
  )
}

function ModuleSettingsModal({
  module,
  onClose,
  onSaved,
}: {
  module: ModuleInfo
  onClose: () => void
  onSaved: () => void
}) {
  const { t } = useT()
  const { notify } = useToast()
  const [values, setValues] = useState<Record<string, FormValue>>(() => ({
    ...module.config,
  }))
  const [busy, setBusy] = useState(false)

  const save = async () => {
    setBusy(true)
    try {
      await saveModuleSettings(module.code, values)
      notify('success', t('settings.modules.saved', 'Settings saved'), module.name)
      onSaved()
    } catch (err) {
      notify('error', module.name, (err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal opened onClose={onClose} title={module.name} centered>
      <Stack gap="md">
        {module.settings.map((field) => (
          <SettingInput
            key={field.key}
            field={field}
            value={values[field.key] ?? null}
            onChange={(v) => setValues((prev) => ({ ...prev, [field.key]: v }))}
          />
        ))}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {t('common.cancel', 'Cancel')}
          </Button>
          <Button onClick={save} loading={busy}>
            {t('common.save', 'Save')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}

function SettingInput({
  field,
  value,
  onChange,
}: {
  field: ModuleSettingField
  value: FormValue
  onChange: (value: FormValue) => void
}) {
  const { t } = useT()
  const common = {
    label: field.label,
    description: field.description || undefined,
    required: field.required,
  }
  switch (field.type) {
    case 'bool':
      return (
        <Switch
          {...common}
          checked={value === true}
          onChange={(e) => onChange(e.currentTarget.checked)}
        />
      )
    case 'int':
    case 'float':
      return (
        <NumberInput
          {...common}
          value={typeof value === 'number' ? value : ''}
          allowDecimal={field.type === 'float'}
          onChange={(v) => onChange(v === '' ? null : Number(v))}
        />
      )
    case 'choice':
      return (
        <Select
          {...common}
          data={field.choices}
          value={typeof value === 'string' ? value : null}
          onChange={(v) => onChange(v)}
        />
      )
    case 'secret':
      return (
        <PasswordInput
          {...common}
          placeholder={t('settings.modules.secretKept', 'Leave empty to keep the stored value')}
          value={typeof value === 'string' ? value : ''}
          onChange={(e) => onChange(e.currentTarget.value)}
        />
      )
    default:
      return (
        <TextInput
          {...common}
          type={field.type === 'email' ? 'email' : field.type === 'url' ? 'url' : 'text'}
          value={value == null ? '' : String(value)}
          onChange={(e) => onChange(e.currentTarget.value)}
        />
      )
  }
}
