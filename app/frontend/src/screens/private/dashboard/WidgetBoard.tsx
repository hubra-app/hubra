import { useState, type ReactNode } from 'react'
import {
  ActionIcon,
  Button,
  Group,
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
import { IconArrowDown, IconArrowUp, IconSettings, IconTrash } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { Modal } from '@/components/ui'
import type { DashboardWidget, WidgetSize } from '@/api/dashboards'
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
 * Widgets in a grid, with the tools to change them in edit mode (size,
 * order, settings, remove) and the widget list to add one. Used by own
 * dashboards and by the start pages; *save* stores the new list.
 */
export function WidgetBoard({
  widgets,
  editing,
  busy,
  save,
  picking,
  setPicking,
  empty,
}: {
  widgets: DashboardWidget[]
  editing: boolean
  busy: boolean
  save: (next: DashboardWidget[]) => void
  picking: boolean
  setPicking: (open: boolean) => void
  /** Shown when no widget is left to show. */
  empty: ReactNode
}) {
  const { t } = useT()
  const catalogue = useWidgetCatalogue()
  const allowed = useWidgetAllowed()
  const [configuring, setConfiguring] = useState<{
    widget: DashboardWidget
    isNew: boolean
  } | null>(null)
  const byType = new Map(catalogue.map((d) => [d.type, d]))

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
    <>
      {shown.length === 0 ? (
        empty
      ) : (
        <div className={editing ? 'hb-dash-grid editing' : 'hb-dash-grid'}>
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
                <div
                  className="hb-dash-body"
                  data-empty={t('dashboards.nothingNow', '{{name}}: gerade nichts anzuzeigen.', {
                    name: def?.label ?? w.type,
                  })}
                >
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
    </>
  )
}
