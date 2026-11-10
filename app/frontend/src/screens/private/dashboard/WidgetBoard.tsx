import {
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
  type RefObject,
} from 'react'
import {
  ActionIcon,
  Button,
  Group,
  NumberInput,
  Paper,
  SimpleGrid,
  Stack,
  Switch,
  Text,
  TextInput,
  Textarea,
  UnstyledButton,
} from '@mantine/core'
import {
  IconArrowAutofitHeight,
  IconGripVertical,
  IconSettings,
  IconTrash,
} from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { Modal } from '@/components/ui'
import type { DashboardWidget } from '@/api/dashboards'
import {
  clampH,
  clampW,
  move,
  resized,
  rowsFor,
  sizeFor,
  tabletWidth,
  widthOf,
  withSize,
} from './grid'
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

/** Rows the element's content needs, measured as it changes (null: hidden). */
function useContentRows(ref: RefObject<HTMLDivElement | null>, active: boolean): number | null {
  const [rows, setRows] = useState<number | null>(null)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el || !active) return
    const measure = () => {
      // Unstretched for a moment, so a shrinking widget gives its room back.
      const flex = el.style.flex
      el.style.flex = 'none'
      const px = el.offsetHeight
      el.style.flex = flex
      setRows(px > 0 ? rowsFor(px) : null)
    }
    measure()
    if (typeof ResizeObserver === 'undefined') return
    const resize = new ResizeObserver(measure)
    resize.observe(el)
    const change = new MutationObserver(measure)
    change.observe(el, { childList: true, subtree: true, characterData: true })
    return () => {
      resize.disconnect()
      change.disconnect()
    }
  }, [ref, active])
  return active ? rows : null
}

const KEY_STEP: Record<string, [number, number]> = {
  ArrowLeft: [-1, 0],
  ArrowRight: [1, 0],
  ArrowUp: [0, -1],
  ArrowDown: [0, 1],
}

/** One widget in the grid, with its handles in edit mode. */
function GridCell({
  widget,
  def,
  allowed,
  editing,
  busy,
  w,
  h,
  dragging,
  onDragStart,
  onMoveKey,
  onResizeStart,
  onResizeKey,
  onAutoHeight,
  onSettings,
  onRemove,
}: {
  widget: DashboardWidget
  def: WidgetDef | undefined
  allowed: boolean
  editing: boolean
  busy: boolean
  w: number
  h: number | undefined
  dragging: boolean
  onDragStart: (e: ReactPointerEvent) => void
  onMoveKey: (by: number) => void
  onResizeStart: (e: ReactPointerEvent, rows: number) => void
  onResizeKey: (dw: number, dh: number, rows: number) => void
  onAutoHeight: () => void
  onSettings: () => void
  onRemove: () => void
}) {
  const { t } = useT()
  const inner = useRef<HTMLDivElement>(null)
  const contentRows = useContentRows(inner, h === undefined)
  const rows = h ?? contentRows ?? 1
  const name = def?.label ?? widget.type
  const style = {
    '--w': w,
    '--wt': tabletWidth(w),
    '--h': rows,
  } as CSSProperties
  return (
    <div
      className={['hb-dash-cell', h !== undefined ? 'fixed' : '', dragging ? 'dragging' : ''].join(
        ' ',
      )}
      style={style}
      data-widget-id={widget.id}
      data-testid={`widget-${widget.type}`}
      data-w={w}
      data-h={h ?? 'auto'}
    >
      <div ref={inner} className="hb-dash-inner">
        {editing && (
          <Group gap={4} mb={6} justify="space-between" wrap="nowrap" className="hb-dash-tools">
            <Group gap={4} wrap="nowrap" style={{ minWidth: 0 }}>
              <ActionIcon
                variant="subtle"
                color="gray"
                className="hb-dash-grip"
                disabled={busy}
                onPointerDown={onDragStart}
                onKeyDown={(e) => {
                  const step = KEY_STEP[e.key]
                  if (!step) return
                  e.preventDefault()
                  onMoveKey(step[0] + step[1])
                }}
                aria-label={t('dashboards.move', 'Verschieben ({{name}})', { name })}
                title={t('dashboards.moveHint', 'Ziehen zum Verschieben, oder Pfeiltasten')}
              >
                <IconGripVertical size={16} />
              </ActionIcon>
              <Text fz="xs" c="dimmed" truncate>
                {name}
              </Text>
            </Group>
            <Group gap={2} wrap="nowrap">
              {h !== undefined && (
                <ActionIcon
                  variant="subtle"
                  color="gray"
                  disabled={busy}
                  onClick={onAutoHeight}
                  aria-label={t('dashboards.autoHeight', 'Höhe nach Inhalt')}
                  title={t('dashboards.autoHeight', 'Höhe nach Inhalt')}
                >
                  <IconArrowAutofitHeight size={16} />
                </ActionIcon>
              )}
              {def?.fields?.length ? (
                <ActionIcon
                  variant="subtle"
                  color="gray"
                  onClick={onSettings}
                  aria-label={t('dashboards.settings', 'Einstellungen')}
                >
                  <IconSettings size={16} />
                </ActionIcon>
              ) : null}
              <ActionIcon
                variant="subtle"
                color="red"
                disabled={busy}
                onClick={onRemove}
                aria-label={t('dashboards.remove', 'Entfernen')}
              >
                <IconTrash size={16} />
              </ActionIcon>
            </Group>
          </Group>
        )}
        <div
          className="hb-dash-body"
          data-empty={t('dashboards.nothingNow', '{{name}}: gerade nichts anzuzeigen.', { name })}
        >
          {def && allowed ? (
            <WidgetView def={def} config={widget.config} size={sizeFor(w)} />
          ) : (
            <Paper withBorder p="md" style={{ height: '100%' }}>
              <Text fz="sm" c="dimmed">
                {def
                  ? t(
                      'dashboards.notAllowed',
                      '{{name}}: für dich nicht verfügbar (Modul aus oder fehlende Berechtigung).',
                      { name: def.label },
                    )
                  : t('dashboards.unknown', 'Dieses Widget gibt es nicht mehr (Plugin entfernt?).')}
              </Text>
            </Paper>
          )}
        </div>
      </div>
      {editing && (
        <button
          type="button"
          className="hb-dash-resize"
          disabled={busy}
          onPointerDown={(e) => onResizeStart(e, rows)}
          onKeyDown={(e) => {
            const step = KEY_STEP[e.key]
            if (!step) return
            e.preventDefault()
            onResizeKey(step[0], step[1], rows)
          }}
          aria-label={t('dashboards.resize', 'Grösse ändern ({{name}})', { name })}
          title={t('dashboards.resizeHint', 'Ziehen für Breite und Höhe, oder Pfeiltasten')}
        />
      )}
    </div>
  )
}

/** Wide enough for the 12 columns (narrower, widths follow the screen). */
const isWide = () =>
  typeof window === 'undefined' || !window.matchMedia
    ? true
    : window.matchMedia('(min-width: 62em)').matches

/**
 * Widgets on a grid of 12 columns, with the tools to change them in edit
 * mode: drag the grip to move a widget, the corner to change its width and
 * height, the cog for its settings, the bin to remove it. Used by own
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
  // While dragging: the order shown, and the widget being moved.
  const [order, setOrder] = useState<string[] | null>(null)
  const [dragged, setDragged] = useState<string | null>(null)
  // While resizing: the size shown.
  const [sizing, setSizing] = useState<{ id: string; w: number; h: number } | null>(null)
  const grid = useRef<HTMLDivElement>(null)
  const byType = new Map(catalogue.map((d) => [d.type, d]))
  const byId = new Map(widgets.map((w) => [w.id, w]))

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

  const startDrag = (e: ReactPointerEvent, id: string) => {
    if (busy || e.button !== 0) return
    e.preventDefault()
    let current = widgets.map((w) => w.id)
    let last: string | null = null
    setDragged(id)
    setOrder(current)
    const onMove = (ev: PointerEvent) => {
      const over = document
        .elementFromPoint(ev.clientX, ev.clientY)
        ?.closest<HTMLElement>('[data-widget-id]')?.dataset.widgetId
      // Only a new widget under the pointer moves it, so it doesn't flip back.
      if (!over || over === id) {
        last = null
        return
      }
      if (over === last) return
      last = over
      current = move(current, current.indexOf(id), current.indexOf(over))
      setOrder(current)
    }
    const onUp = () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      window.removeEventListener('pointercancel', onUp)
      setDragged(null)
      setOrder(null)
      if (current.some((wid, i) => widgets[i]?.id !== wid)) {
        save(current.map((wid) => byId.get(wid)).filter((w) => w !== undefined))
      }
    }
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    window.addEventListener('pointercancel', onUp)
  }

  const moveBy = (id: string, by: number) => {
    const i = widgets.findIndex((w) => w.id === id)
    const next = move(widgets, i, i + by)
    if (next !== widgets) save(next)
  }

  const resize = (id: string, w: number, h: number | undefined) =>
    save(widgets.map((x) => (x.id === id ? withSize(x, w, h) : x)))

  const startResize = (e: ReactPointerEvent, widget: DashboardWidget, rows: number) => {
    if (busy || e.button !== 0 || !grid.current) return
    e.preventDefault()
    const start = { w: widthOf(widget), h: widget.h ?? rows }
    const width = grid.current.clientWidth
    const wide = isWide()
    let size = start
    setSizing({ id: widget.id, ...start })
    const onMove = (ev: PointerEvent) => {
      size = resized(start, ev.clientX - e.clientX, ev.clientY - e.clientY, width, wide)
      setSizing({ id: widget.id, ...size })
    }
    const onUp = () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      window.removeEventListener('pointercancel', onUp)
      setSizing(null)
      if (size.w !== start.w || size.h !== start.h) resize(widget.id, size.w, size.h)
    }
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    window.addEventListener('pointercancel', onUp)
  }

  const ordered = order ? order.map((id) => byId.get(id)).filter((w) => w !== undefined) : widgets
  const shown = ordered.filter((w) => {
    const def = byType.get(w.type)
    return editing || (def !== undefined && allowed(def))
  })

  return (
    <>
      {shown.length === 0 ? (
        empty
      ) : (
        <div
          ref={grid}
          className={['hb-dash-grid', editing ? 'editing' : '', sizing ? 'sizing' : '']
            .join(' ')
            .trim()}
        >
          {shown.map((w) => {
            const def = byType.get(w.type)
            const live = sizing?.id === w.id ? sizing : null
            return (
              <GridCell
                key={w.id}
                widget={w}
                def={def}
                allowed={def !== undefined && allowed(def)}
                editing={editing}
                busy={busy}
                w={live?.w ?? widthOf(w)}
                h={live?.h ?? w.h}
                dragging={dragged === w.id}
                onDragStart={(e) => startDrag(e, w.id)}
                onMoveKey={(by) => moveBy(w.id, by)}
                onResizeStart={(e, rows) => startResize(e, w, rows)}
                onResizeKey={(dw, dh, rows) =>
                  resize(w.id, clampW(widthOf(w) + dw), clampH((w.h ?? rows) + dh))
                }
                onAutoHeight={() => resize(w.id, widthOf(w), undefined)}
                onSettings={() => setConfiguring({ widget: w, isNew: false })}
                onRemove={() => save(widgets.filter((x) => x.id !== w.id))}
              />
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
