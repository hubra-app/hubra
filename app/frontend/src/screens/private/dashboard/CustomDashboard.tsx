import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import {
  ActionIcon,
  Badge,
  Button,
  Group,
  Menu,
  NumberInput,
  Paper,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Switch,
  Text,
  TextInput,
  Textarea,
  UnstyledButton,
} from '@mantine/core'
import {
  IconArrowDown,
  IconArrowUp,
  IconDots,
  IconPencil,
  IconPlus,
  IconSettings,
  IconTrash,
  IconUsers,
} from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useNav, useToast } from '@/context/AppContext'
import { ConfirmModal, EmptyState, Modal } from '@/components/ui'
import { qk } from '@/data/keys'
import {
  deleteDashboard,
  shareDashboard,
  updateDashboard,
  type Dashboard,
  type DashboardWidget,
  type WidgetSize,
} from '@/api/dashboards'
import {
  useWidgetAllowed,
  useWidgetCatalogue,
  WidgetView,
  type WidgetDef,
  type WidgetField,
} from './widgets'

type Config = Record<string, unknown>

function newId(widgets: DashboardWidget[]): string {
  let i = widgets.length + 1
  while (widgets.some((w) => w.id === `w${i}`)) i += 1
  return `w${i}`
}

function defaults(def: WidgetDef): Config {
  return Object.fromEntries(
    (def.fields ?? []).filter((f) => f.default !== undefined).map((f) => [f.key, f.default]),
  )
}

/** The fields of a widget's settings. */
function ConfigForm({
  fields,
  value,
  onChange,
}: {
  fields: WidgetField[]
  value: Config
  onChange: (v: Config) => void
}) {
  const set = (key: string, v: unknown) => onChange({ ...value, [key]: v })
  return (
    <Stack gap="sm">
      {fields.map((f) =>
        f.kind === 'switch' ? (
          <Switch
            key={f.key}
            label={f.label}
            checked={value[f.key] === true}
            onChange={(e) => set(f.key, e.currentTarget.checked)}
          />
        ) : f.kind === 'number' ? (
          <NumberInput
            key={f.key}
            label={f.label}
            min={f.min}
            max={f.max}
            value={typeof value[f.key] === 'number' ? (value[f.key] as number) : ''}
            onChange={(v) => set(f.key, typeof v === 'number' ? v : undefined)}
          />
        ) : f.kind === 'textarea' ? (
          <Textarea
            key={f.key}
            label={f.label}
            description={f.hint}
            autosize
            minRows={3}
            maxLength={2000}
            value={typeof value[f.key] === 'string' ? (value[f.key] as string) : ''}
            onChange={(e) => set(f.key, e.currentTarget.value)}
          />
        ) : (
          <TextInput
            key={f.key}
            label={f.label}
            description={f.hint}
            maxLength={100}
            value={typeof value[f.key] === 'string' ? (value[f.key] as string) : ''}
            onChange={(e) => set(f.key, e.currentTarget.value)}
          />
        ),
      )}
    </Stack>
  )
}

/**
 * A member's own dashboard: widgets in a grid. Its owner edits it (add,
 * order, size, settings, remove) and, with the right to, shares it with
 * the club; everyone sees only the widgets they may.
 */
export function CustomDashboard({
  dashboard,
  canShare,
  startEditing = false,
}: {
  dashboard: Dashboard
  canShare: boolean
  startEditing?: boolean
}) {
  const { t } = useT()
  const { go } = useNav()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const catalogue = useWidgetCatalogue()
  const allowed = useWidgetAllowed()
  const [editing, setEditing] = useState(startEditing && dashboard.canEdit)
  // A new, empty dashboard opens with the widget list.
  const [picking, setPicking] = useState(
    startEditing && dashboard.canEdit && dashboard.widgets.length === 0,
  )
  const [configuring, setConfiguring] = useState<{
    widget: DashboardWidget
    isNew: boolean
  } | null>(null)
  const [renaming, setRenaming] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [busy, setBusy] = useState(false)
  const widgets = dashboard.widgets
  const byType = new Map(catalogue.map((d) => [d.type, d]))

  const refresh = (d: Dashboard) =>
    queryClient.setQueryData(qk.dashboards, (old: { items: Dashboard[] } | undefined) =>
      old ? { ...old, items: old.items.map((x) => (x.id === d.id ? d : x)) } : old,
    )

  const run = async (action: () => Promise<Dashboard | void>, done?: string) => {
    setBusy(true)
    try {
      const d = await action()
      if (d) refresh(d)
      else await queryClient.invalidateQueries({ queryKey: qk.dashboards })
      if (done) notify('success', done)
    } catch (err) {
      notify('error', t('common.error'), err instanceof Error ? err.message : '')
    } finally {
      setBusy(false)
    }
  }

  const save = (next: DashboardWidget[]) =>
    run(() => updateDashboard(dashboard.id, { widgets: next }))

  const move = (i: number, by: number) => {
    const next = [...widgets]
    const [w] = next.splice(i, 1)
    next.splice(i + by, 0, w)
    save(next)
  }

  const add = (def: WidgetDef) => {
    setPicking(false)
    const widget: DashboardWidget = {
      id: newId(widgets),
      type: def.type,
      size: def.size,
      config: defaults(def),
    }
    if (def.fields?.length) setConfiguring({ widget, isNew: true })
    else save([...widgets, widget])
  }

  const shown = widgets.filter((w) => {
    const def = byType.get(w.type)
    return editing || (def !== undefined && allowed(def))
  })

  return (
    <div>
      <Group justify="space-between" mb="md" gap="xs" className="page-actions">
        <Group gap={8}>
          <Badge
            variant="light"
            color={dashboard.shared ? 'blue' : 'gray'}
            leftSection={dashboard.shared ? <IconUsers size={12} /> : undefined}
          >
            {dashboard.shared
              ? t('dashboards.shared', 'Mit dem Verein geteilt')
              : t('dashboards.private', 'Privat')}
          </Badge>
          {!dashboard.mine && dashboard.owner.name && (
            <Text fz="xs" c="dimmed">
              {t('dashboards.by', 'von {{name}}', { name: dashboard.owner.name })}
            </Text>
          )}
        </Group>
        {dashboard.canEdit && (
          <Group gap="xs">
            {editing && (
              <Button
                variant="default"
                leftSection={<IconPlus size={16} />}
                onClick={() => setPicking(true)}
              >
                {t('dashboards.addWidget', 'Widget hinzufügen')}
              </Button>
            )}
            <Button
              variant={editing ? 'filled' : 'default'}
              leftSection={editing ? undefined : <IconPencil size={16} />}
              onClick={() => setEditing((e) => !e)}
            >
              {editing ? t('dashboards.done', 'Fertig') : t('dashboards.edit', 'Bearbeiten')}
            </Button>
            <Menu position="bottom-end" withinPortal>
              <Menu.Target>
                <ActionIcon variant="default" size="lg" aria-label={t('common.more', 'Mehr')}>
                  <IconDots size={16} />
                </ActionIcon>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Item onClick={() => setRenaming(dashboard.name)}>
                  {t('dashboards.rename', 'Umbenennen')}
                </Menu.Item>
                {((canShare && dashboard.mine) || dashboard.shared) && (
                  <Menu.Item
                    leftSection={<IconUsers size={14} />}
                    onClick={() =>
                      run(
                        () => shareDashboard(dashboard.id, !dashboard.shared),
                        dashboard.shared
                          ? t('dashboards.unsharedDone', 'Nicht mehr geteilt')
                          : t('dashboards.sharedDone', 'Mit dem Verein geteilt'),
                      )
                    }
                  >
                    {dashboard.shared
                      ? t('dashboards.unshare', 'Nicht mehr teilen')
                      : t('dashboards.share', 'Mit dem Verein teilen')}
                  </Menu.Item>
                )}
                <Menu.Item
                  color="red"
                  leftSection={<IconTrash size={14} />}
                  onClick={() => setDeleting(true)}
                >
                  {t('dashboards.delete', 'Dashboard löschen')}
                </Menu.Item>
              </Menu.Dropdown>
            </Menu>
          </Group>
        )}
      </Group>

      {shown.length === 0 ? (
        <EmptyState
          title={t('dashboards.empty', 'Noch keine Widgets')}
          description={
            dashboard.canEdit
              ? t(
                  'dashboards.emptyHint',
                  'Füge Widgets hinzu: Anlässe, Beiträge, Zahlen, Notizen und mehr.',
                )
              : undefined
          }
          action={
            dashboard.canEdit
              ? {
                  label: t('dashboards.addWidget', 'Widget hinzufügen'),
                  onClick: () => {
                    setEditing(true)
                    setPicking(true)
                  },
                }
              : undefined
          }
        />
      ) : (
        <div className="hb-dash-grid">
          {shown.map((w) => {
            const def = byType.get(w.type)
            const i = widgets.indexOf(w)
            return (
              <div key={w.id} className={`hb-dash-${w.size}`} data-testid={`widget-${w.type}`}>
                {editing && (
                  <Group gap={4} mb={6} justify="space-between" wrap="wrap">
                    <SegmentedControl
                      size="xs"
                      value={w.size}
                      onChange={(v) =>
                        save(
                          widgets.map((x) => (x.id === w.id ? { ...x, size: v as WidgetSize } : x)),
                        )
                      }
                      data={[
                        { value: 's', label: t('dashboards.size.s', 'Schmal') },
                        { value: 'm', label: t('dashboards.size.m', 'Halb') },
                        { value: 'l', label: t('dashboards.size.l', 'Breit') },
                      ]}
                    />
                    <Group gap={2} wrap="nowrap">
                      <ActionIcon
                        variant="subtle"
                        color="gray"
                        disabled={i === 0 || busy}
                        onClick={() => move(i, -1)}
                        aria-label={t('dashboards.up', 'Nach vorne')}
                      >
                        <IconArrowUp size={16} />
                      </ActionIcon>
                      <ActionIcon
                        variant="subtle"
                        color="gray"
                        disabled={i === widgets.length - 1 || busy}
                        onClick={() => move(i, 1)}
                        aria-label={t('dashboards.down', 'Nach hinten')}
                      >
                        <IconArrowDown size={16} />
                      </ActionIcon>
                      {def?.fields?.length ? (
                        <ActionIcon
                          variant="subtle"
                          color="gray"
                          onClick={() => setConfiguring({ widget: w, isNew: false })}
                          aria-label={t('dashboards.settings', 'Einstellungen')}
                        >
                          <IconSettings size={16} />
                        </ActionIcon>
                      ) : null}
                      <ActionIcon
                        variant="subtle"
                        color="red"
                        disabled={busy}
                        onClick={() => save(widgets.filter((x) => x.id !== w.id))}
                        aria-label={t('dashboards.remove', 'Entfernen')}
                      >
                        <IconTrash size={16} />
                      </ActionIcon>
                    </Group>
                  </Group>
                )}
                <div className="hb-dash-body">
                  {def && allowed(def) ? (
                    <WidgetView def={def} config={w.config} size={w.size} />
                  ) : (
                    <Paper withBorder p="md" style={{ height: '100%' }}>
                      <Text fz="sm" c="dimmed">
                        {def
                          ? t(
                              'dashboards.notAllowed',
                              '{{name}}: für dich nicht verfügbar (Modul aus oder fehlende Berechtigung).',
                              { name: def.label },
                            )
                          : t(
                              'dashboards.unknown',
                              'Dieses Widget gibt es nicht mehr (Plugin entfernt?).',
                            )}
                      </Text>
                    </Paper>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      <Modal
        open={picking}
        onClose={() => setPicking(false)}
        title={t('dashboards.addWidget', 'Widget hinzufügen')}
        wide
      >
        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm">
          {catalogue.filter(allowed).map((def) => (
            <UnstyledButton
              key={def.type}
              onClick={() => add(def)}
              data-testid={`pick-${def.type}`}
            >
              <Paper withBorder p="sm" style={{ height: '100%' }}>
                <Text fw={600} fz="sm">
                  {def.label}
                </Text>
                <Text fz="xs" c="dimmed">
                  {def.description}
                </Text>
              </Paper>
            </UnstyledButton>
          ))}
        </SimpleGrid>
      </Modal>

      <Modal
        open={configuring !== null}
        onClose={() => setConfiguring(null)}
        title={configuring ? (byType.get(configuring.widget.type)?.label ?? '') : ''}
        onSubmit={(e) => {
          e?.preventDefault()
          if (!configuring) return
          const { widget, isNew } = configuring
          setConfiguring(null)
          save(isNew ? [...widgets, widget] : widgets.map((x) => (x.id === widget.id ? widget : x)))
        }}
        footer={
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setConfiguring(null)}>
              {t('common.cancel', 'Abbrechen')}
            </Button>
            <Button type="submit">
              {configuring?.isNew
                ? t('dashboards.add', 'Hinzufügen')
                : t('common.save', 'Speichern')}
            </Button>
          </Group>
        }
      >
        {configuring && (
          <ConfigForm
            fields={byType.get(configuring.widget.type)?.fields ?? []}
            value={configuring.widget.config}
            onChange={(config) =>
              setConfiguring({ ...configuring, widget: { ...configuring.widget, config } })
            }
          />
        )}
      </Modal>

      <Modal
        open={renaming !== null}
        onClose={() => setRenaming(null)}
        title={t('dashboards.rename', 'Umbenennen')}
        onSubmit={(e) => {
          e?.preventDefault()
          const name = (renaming ?? '').trim()
          setRenaming(null)
          if (name) run(() => updateDashboard(dashboard.id, { name }))
        }}
        footer={
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setRenaming(null)}>
              {t('common.cancel', 'Abbrechen')}
            </Button>
            <Button type="submit">{t('common.save', 'Speichern')}</Button>
          </Group>
        }
      >
        <TextInput
          label={t('dashboards.name', 'Name')}
          maxLength={100}
          data-autofocus
          value={renaming ?? ''}
          onChange={(e) => setRenaming(e.currentTarget.value)}
        />
      </Modal>

      <ConfirmModal
        open={deleting}
        title={t('dashboards.deleteTitle', 'Dashboard löschen')}
        body={t('dashboards.deleteBody', '«{{name}}» und seine Widgets werden gelöscht.', {
          name: dashboard.name,
        })}
        onConfirm={() => {
          setDeleting(false)
          run(() => deleteDashboard(dashboard.id)).then(() => go('/app/dashboard'))
        }}
        onClose={() => setDeleting(false)}
      />
    </div>
  )
}
