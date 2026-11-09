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
import { IconBulb, IconSettings } from '@tabler/icons-react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { moduleNavIcon } from '@/components/Shell/nav'
import { useT } from '@/locales/i18n'
import { useAuth, useToast } from '@/context/AppContext'
import { PluginSlot } from '@/plugins'
import {
  getModules,
  saveModuleSettings,
  setModuleEnabled,
  type ModuleInfo,
  type ModuleSettingField,
} from '@/api/modules'
import { localizeModule } from '@/modules/labels'
import { qk } from '@/data/keys'
import { openReport } from '@/screens/private/support/reportStore'
import type { HubraAddonOffer } from '@/api/billing'
import { addonPrice, useAddonSwitch, useHubraCatalog } from './subscriptionHooks'

type FormValue = string | number | boolean | null

/**
 * Modules whose settings have their own page in the module (more than the
 * generic form can show). Their "Einstellungen" button goes there, so each
 * setting is edited in one place only.
 */
const SETTINGS_PAGES: Record<string, string> = { finance: '/app/finance/settings' }

/** "Fehlt ein Modul?": opens the idea form with the area "Modul" set. */
function MissingModule() {
  const { t } = useT()
  return (
    <Paper withBorder radius="md" p="md" data-testid="missing-module">
      <Group gap="md" wrap="wrap" justify="space-between" align="center">
        <Group gap="sm" wrap="nowrap" align="flex-start" style={{ flex: '1 1 320px', minWidth: 0 }}>
          <ThemeIcon variant="light" radius="xl" size={36} color="orange">
            <IconBulb size={20} />
          </ThemeIcon>
          <div style={{ minWidth: 0 }}>
            <Text fw={650}>{t('settings.modules.missingTitle', 'Fehlt ein Modul?')}</Text>
            <Text fz="sm" c="dimmed">
              {t(
                'settings.modules.missingDesc',
                'Schlag es vor. Nimmt das Hubra-Team die Idee auf die Roadmap, können alle Vereine dafür stimmen.',
              )}
            </Text>
          </div>
        </Group>
        <Group gap="xs" wrap="wrap">
          <Button component={Link} to="/app/feedback/roadmap" variant="default">
            {t('settings.modules.roadmap', 'Roadmap ansehen')}
          </Button>
          <Button
            leftSection={<IconBulb size={16} />}
            onClick={() => openReport('feature', { area: 'modules' })}
          >
            {t('settings.modules.suggest', 'Modul vorschlagen')}
          </Button>
        </Group>
      </Group>
    </Paper>
  )
}

export function ModulesTab() {
  const { t } = useT()
  const { notify } = useToast()
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const canWrite = hasPermission('modules.modules.write')
  const [picked, setPicked] = useState<ModuleInfo | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  // Paid modules: the price on the card, and switching one on books it.
  const { data: catalog } = useHubraCatalog()
  const offers: Record<string, HubraAddonOffer> = Object.fromEntries(
    (catalog?.addons ?? []).map((a) => [a.code, a]),
  )
  const addonSwitch = useAddonSwitch()

  const { data: modules = [], isLoading } = useQuery({
    queryKey: qk.modules,
    queryFn: getModules,
    select: (list) => list.map(localizeModule),
  })
  const byCode = Object.fromEntries(modules.map((m) => [m.code, m]))

  // ?module=<code> opens that module's settings, so a module's own page can
  // link straight to them (/app/settings/modules?module=messengers).
  const wanted = byCode[params.get('module') ?? '']
  const fromUrl = wanted && wanted.enabled && canWrite && wanted.settings.length > 0 ? wanted : null
  const editing = picked ?? fromUrl
  const setEditing = (m: ModuleInfo | null) => {
    setPicked(m)
    if (m === null && params.has('module')) {
      const next = new URLSearchParams(params)
      next.delete('module')
      setParams(next, { replace: true })
    }
  }

  const configure = (m: ModuleInfo) =>
    SETTINGS_PAGES[m.code] ? navigate(SETTINGS_PAGES[m.code]) : setEditing(m)

  const optional = modules.filter((m) => !m.required)
  const required = modules.filter((m) => m.required)
  // One list for the club: whether a module ships with Hubra or as a plugin
  // is the platform's business (plugins let it ship modules without a new
  // release of the whole app). A plugin's module goes right after the area
  // it extends (finance.budgets after finance), the rest keep their order.
  const listed = optional.filter((m) => !m.plugin)
  optional
    .filter((m) => m.plugin)
    .sort((a, b) => a.name.localeCompare(b.name))
    .forEach((m) => {
      const area = m.code.split('.')[0]
      let at = -1
      listed.forEach((x, i) => {
        if (x.code === area || x.code.startsWith(area + '.')) at = i
      })
      listed.splice(at < 0 ? listed.length : at + 1, 0, m)
    })

  const toggle = async (m: ModuleInfo, enabled: boolean) => {
    const offer = offers[m.code]
    if (offer && ((enabled && offer.source === null) || (!enabled && offer.source === 'addon'))) {
      addonSwitch.ask(offer, enabled)
      return
    }
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

  const card = (m: ModuleInfo) => (
    <ModuleCard
      key={m.code}
      m={m}
      byCode={byCode}
      canWrite={canWrite}
      busy={busy === m.code || addonSwitch.busy === m.code}
      offer={offers[m.code]}
      onToggle={(on) => toggle(m, on)}
      onConfigure={() => configure(m)}
    />
  )

  if (fromUrl && SETTINGS_PAGES[fromUrl.code])
    return <Navigate to={SETTINGS_PAGES[fromUrl.code]} replace />

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
          title={t('settings.modules.title', 'Module')}
          count={listed.filter((m) => m.enabled).length}
          total={listed.length}
        />
        <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
          {listed.map((m) => card(m))}
        </SimpleGrid>
      </Stack>

      <MissingModule />

      {required.length > 0 && (
        <Text fz="xs" c="dimmed">
          {t('settings.modules.alwaysOn', 'Immer eingeschaltet: {{names}}', {
            names: required.map((m) => m.name).join(', '),
          })}
        </Text>
      )}
      {addonSwitch.modal}
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
  byCode,
  canWrite,
  busy,
  offer,
  onToggle,
  onConfigure,
}: {
  m: ModuleInfo
  byCode: Record<string, ModuleInfo>
  canWrite: boolean
  busy: boolean
  offer?: HubraAddonOffer
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
        <ThemeIcon
          size={44}
          radius="md"
          variant="light"
          color={on ? undefined : 'gray'}
          aria-hidden
        >
          {m.plugin ? moduleNavIcon(m.nav[0]?.icon ?? 'puzzle') : moduleNavIcon(m.nav[0]?.icon)}
        </ThemeIcon>
        <Stack gap={2} style={{ flex: 1, minWidth: 0 }}>
          <Text fw={700} fz="md">
            {m.name}
          </Text>
          {offer && (
            <Text fz="xs" c={offer.source === 'included' ? 'green' : 'dimmed'} data-price={m.code}>
              {offer.source === 'included'
                ? t('settings.modules.inPlan', 'Im Tarif inklusive')
                : offer.source === null
                  ? t('settings.modules.extra', 'Aufpreis: {{price}}', {
                      price: addonPrice(t, offer),
                    })
                  : addonPrice(t, offer)}
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
      {(blocker ||
        needsSetup ||
        uses.length > 0 ||
        (m.settings.length > 0 && m.enabled && canWrite)) && (
        <Group justify="space-between" gap="xs" wrap="wrap">
          <Group gap={6}>
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
            <Button
              size="xs"
              variant="default"
              leftSection={<IconSettings size={14} />}
              onClick={onConfigure}
            >
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
          placeholder={t(
            'settings.modules.secretKept',
            'Leer lassen, um den gespeicherten Wert zu behalten',
          )}
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
