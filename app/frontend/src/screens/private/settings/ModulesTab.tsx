import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Badge,
  Button,
  Group,
  Loader,
  Modal,
  NumberInput,
  Paper,
  PasswordInput,
  Select,
  SimpleGrid,
  Stack,
  Switch,
  Text,
  TextInput,
  ThemeIcon,
} from '@mantine/core'
import { IconPuzzle, IconSettings } from '@tabler/icons-react'
import { moduleNavIcon } from '@/components/Shell/nav'
import { useT } from '@/locales/i18n'
import { useAuth, useToast } from '@/context/AppContext'
import { PluginSlot } from '@/plugins'
import {
  getModules,
  saveModuleSettings,
  setModuleEnabled,
  type ModuleInfo,
  type ModulePlugin,
  type ModuleSettingField,
} from '@/api/modules'
import { localizeModule } from '@/modules/labels'
import { qk } from '@/data/keys'

type FormValue = string | number | boolean | null

export function ModulesTab() {
  const { t } = useT()
  const { notify } = useToast()
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const canWrite = hasPermission('modules.modules.write')
  const [editing, setEditing] = useState<ModuleInfo | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  const { data: modules = [], isLoading } = useQuery({
    queryKey: qk.modules,
    queryFn: getModules,
    select: (list) => list.map(localizeModule),
  })
  const byCode = Object.fromEntries(modules.map((m) => [m.code, m]))
  const optional = modules.filter((m) => !m.required)
  const builtIn = optional.filter((m) => !m.plugin)
  const required = modules.filter((m) => m.required)
  // One card per plugin, with every module it brings.
  const plugins = Object.values(
    optional
      .filter((m) => m.plugin)
      .reduce<Record<string, { plugin: ModulePlugin; modules: ModuleInfo[] }>>((acc, m) => {
        const p = m.plugin!
        ;(acc[p.id] ??= { plugin: p, modules: [] }).modules.push(m)
        return acc
      }, {}),
  ).sort((a, b) => a.plugin.name.localeCompare(b.plugin.name))

  const toggle = async (m: ModuleInfo, enabled: boolean) => {
    setBusy(m.code)
    try {
      const updated = await setModuleEnabled(m.code, enabled)
      await queryClient.invalidateQueries({ queryKey: qk.modules })
      notify(
        'success',
        enabled
          ? t('settings.modules.switchedOn', '{{name}} eingeschaltet', { name: m.name })
          : t('settings.modules.switchedOff', '{{name}} ausgeschaltet', { name: m.name }),
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

  const card = (m: ModuleInfo, plugin?: ModulePlugin) => (
    <ModuleCard
      key={m.code}
      m={m}
      plugin={plugin}
      byCode={byCode}
      canWrite={canWrite}
      busy={busy === m.code}
      onToggle={(on) => toggle(m, on)}
      onConfigure={() => setEditing(m)}
    />
  )

  if (isLoading) {
    return (
      <Group gap="sm" p="lg">
        <Loader size="sm" />
      </Group>
    )
  }

  return (
    <Stack gap="xl">
      <Text fz="sm" c="dimmed" maw={760}>
        {t(
          'settings.modules.intro',
          'Schalte aus, was dein Verein nicht braucht. Ein ausgeschaltetes Modul ist für alle ausgeblendet. Die Daten bleiben erhalten und sind wieder da, sobald du es einschaltest.',
        )}
      </Text>

      <Stack gap="sm">
        <SectionHead
          title={t('settings.modules.builtInTitle', 'Funktionen')}
          count={builtIn.filter((m) => m.enabled).length}
          total={builtIn.length}
        />
        <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
          {builtIn.map((m) => card(m))}
        </SimpleGrid>
      </Stack>

      <Stack gap="sm">
        <SectionHead
          title={t('settings.modules.pluginsTitle', 'Plugins')}
          count={plugins.reduce((n, p) => n + p.modules.filter((m) => m.enabled).length, 0)}
          total={plugins.reduce((n, p) => n + p.modules.length, 0)}
        />
        <Text fz="sm" c="dimmed" maw={760}>
          {t(
            'settings.modules.pluginsIntro',
            'Zusatzfunktionen aus dem Hubra-Katalog. Schalte ein, was dein Verein nutzen möchte.',
          )}
        </Text>
        {plugins.length === 0 ? (
          <Paper withBorder radius="md" p="lg">
            <Group gap="md" wrap="nowrap">
              <ThemeIcon size={44} radius="md" variant="light" color="gray">
                <IconPuzzle size={24} />
              </ThemeIcon>
              <Text fz="sm" c="dimmed">
                {t(
                  'settings.modules.noPlugins',
                  'Auf dieser Plattform ist noch kein Plugin installiert. Plugins installieren die Plattform-Admins aus dem Hubra-Katalog.',
                )}
              </Text>
            </Group>
          </Paper>
        ) : (
          <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
            {plugins.flatMap((p) => p.modules.map((m) => card(m, p.plugin)))}
          </SimpleGrid>
        )}
        {plugins.length > 0 && (
          <Text fz="xs" c="dimmed">
            {t(
              'settings.modules.morePlugins',
              'Fehlt etwas? Weitere Plugins installieren die Plattform-Admins aus dem Hubra-Katalog.',
            )}
          </Text>
        )}
      </Stack>

      {required.length > 0 && (
        <Text fz="xs" c="dimmed">
          {t('settings.modules.alwaysOn', 'Immer eingeschaltet: {{names}}', {
            names: required.map((m) => m.name).join(', '),
          })}
        </Text>
      )}
      {editing && (
        <ModuleSettingsModal
          module={editing}
          onClose={() => setEditing(null)}
          onSaved={async () => {
            await queryClient.invalidateQueries({ queryKey: qk.modules })
            setEditing(null)
          }}
        />
      )}
    </Stack>
  )
}

function SectionHead({ title, count, total }: { title: string; count: number; total: number }) {
  const { t } = useT()
  return (
    <Group gap={10} align="baseline">
      <Text fw={700} fz="lg" ff="heading">
        {title}
      </Text>
      {total > 0 && (
        <Text fz="xs" c="dimmed">
          {t('settings.modules.onCount', '{{count}} von {{total}} eingeschaltet', { count, total })}
        </Text>
      )}
    </Group>
  )
}

function ModuleCard({
  m,
  plugin,
  byCode,
  canWrite,
  busy,
  onToggle,
  onConfigure,
}: {
  m: ModuleInfo
  plugin?: ModulePlugin
  byCode: Record<string, ModuleInfo>
  canWrite: boolean
  busy: boolean
  onToggle: (on: boolean) => void
  onConfigure: () => void
}) {
  const { t } = useT()
  const on = m.switchedOn && m.allowed
  const blocker = !m.allowed
    ? t('settings.modules.blocked', 'Für diesen Verein nicht verfügbar')
    : m.switchedOn && m.missingDependencies.length > 0
      ? t('settings.modules.needs', 'Braucht {{names}}', {
          names: m.missingDependencies.map((c) => byCode[c]?.name ?? c).join(', '),
        })
      : null
  const uses = m.dependsOn.filter((d) => !byCode[d]?.required)
  const needsSetup = m.enabled && m.settings.length > 0 && !m.configured
  return (
    <Paper
      withBorder
      radius="md"
      p="lg"
      data-module={m.code}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        opacity: m.allowed ? 1 : 0.7,
        borderColor: on ? 'var(--hb-primary, var(--mantine-primary-color-filled))' : undefined,
      }}
    >
      <Group align="flex-start" wrap="nowrap" gap="md">
        <ThemeIcon size={44} radius="md" variant="light" color={on ? undefined : 'gray'} aria-hidden>
          {plugin ? moduleNavIcon(m.nav[0]?.icon ?? 'puzzle') : moduleNavIcon(m.nav[0]?.icon)}
        </ThemeIcon>
        <Stack gap={2} style={{ flex: 1, minWidth: 0 }}>
          <Text fw={700} fz="md">
            {m.name}
          </Text>
          {plugin && (
            <Text fz="xs" c="dimmed" lineClamp={1}>
              {t('settings.modules.pluginBy', 'Plugin {{name}} {{version}}', {
                name: plugin.name,
                version: plugin.version,
              })}
              {plugin.author ? ` · ${plugin.author}` : ''}
            </Text>
          )}
        </Stack>
        <Switch
          checked={on}
          disabled={!canWrite || !m.allowed || busy}
          onChange={(e) => onToggle(e.currentTarget.checked)}
          size="md"
          aria-label={m.name}
        />
      </Group>
      <Text fz="sm" c="dimmed" style={{ flex: 1 }}>
        {m.description}
      </Text>
      {(blocker || needsSetup || plugin?.trust === 'official' || uses.length > 0 || (m.settings.length > 0 && m.enabled && canWrite)) && (
        <Group justify="space-between" gap="xs" wrap="wrap">
          <Group gap={6}>
            {plugin?.trust === 'official' && (
              <Badge size="sm" variant="light" color="green">
                {t('settings.modules.official', 'Offiziell')}
              </Badge>
            )}
            {blocker && (
              <Badge size="sm" color="orange" variant="light">
                {blocker}
              </Badge>
            )}
            {needsSetup && (
              <Badge size="sm" color="red" variant="light">
                {t('settings.modules.needsSetup', 'Muss noch eingerichtet werden')}
              </Badge>
            )}
            {uses.length > 0 && (
              <Text fz="xs" c="dimmed">
                {t('settings.modules.uses', 'Nutzt {{names}}', {
                  names: uses.map((d) => byCode[d]?.name ?? d).join(', '),
                })}
              </Text>
            )}
          </Group>
          {m.settings.length > 0 && m.enabled && canWrite && (
            <Button size="xs" variant="default" leftSection={<IconSettings size={14} />} onClick={onConfigure}>
              {t('settings.modules.configure', 'Einstellungen')}
            </Button>
          )}
        </Group>
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
      notify('success', t('settings.modules.saved', 'Einstellungen gespeichert'), module.name)
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
          <PluginSlot
            name="settings.module.actions"
            props={{ code: module.code, configured: module.configured, name: module.name }}
          />
          <Button variant="default" onClick={onClose}>
            {t('common.cancel', 'Abbrechen')}
          </Button>
          <Button onClick={save} loading={busy}>
            {t('common.save', 'Speichern')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}

export function SettingInput({
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
          data={field.choices.map((c) => ({ value: c, label: field.choiceLabels?.[c] ?? c }))}
          value={typeof value === 'string' ? value : null}
          onChange={(v) => onChange(v)}
        />
      )
    case 'secret':
      return (
        <PasswordInput
          {...common}
          placeholder={t('settings.modules.secretKept', 'Leer lassen, um den gespeicherten Wert zu behalten')}
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
