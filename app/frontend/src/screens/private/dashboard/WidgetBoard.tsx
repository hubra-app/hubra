import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
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
import { IconArrowAutofitHeight, IconSettings, IconTrash } from '@tabler/icons-react'
import { DashboardGrid, freeSpot } from '@bitsandbricks/ui'
import { useT } from '@/locales/i18n'
import { useNav } from '@/context/AppContext'
import { Modal } from '@/components/ui'
import type { DashboardWidget } from '@/api/dashboards'
import {
  COLS,
  GAP,
  layout,
  ROW,
  rowsFor,
  sizeFor,
  START_ROWS,
  toWidgets,
  widthOf,
  withBox,
  withSpots,
  type Placed,
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

/** What a cell measured: its content's rows, or 0 when it shows nothing. */
type Measure = (id: string, rows: number) => void

/**
 * Reports the rows the cell's content needs as it changes, and 0 when the
 * widget draws nothing (it then leaves the grid until it has something).
 */
function useMeasure(
  ref: RefObject<HTMLDivElement | null>,
  body: RefObject<HTMLDivElement | null>,
  id: string,
  editing: boolean,
  onMeasure: Measure,
) {
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const measure = () => {
      const empty = !editing && body.current !== null && !body.current.hasChildNodes()
      // Unstretched for a moment, so a shrinking widget gives its room back.
      const flex = el.style.flex
      el.style.flex = 'none'
      const px = el.offsetHeight
      el.style.flex = flex
      onMeasure(id, empty ? 0 : px > 0 ? rowsFor(px) : START_ROWS)
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
  }, [ref, body, id, editing, onMeasure])
}

/** One widget on the grid, with its tools in edit mode. */
function GridCell({
  widget,
  def,
  allowed,
  editing,
  busy,
  w,
  auto,
  onMeasure,
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
  auto: boolean
  onMeasure: Measure
  onAutoHeight?: () => void
  onSettings?: () => void
  onRemove?: () => void
}) {
  const { t } = useT()
  const root = useRef<HTMLDivElement>(null)
  const body = useRef<HTMLDivElement>(null)
  useMeasure(root, body, widget.id, editing, onMeasure)
  const name = def?.label ?? widget.type
  return (
    <div
      ref={root}
      className={['hb-dash-cell', auto ? '' : 'fixed'].join(' ').trim()}
      data-widget-id={widget.id}
      data-testid={`widget-${widget.type}`}
      data-w={w}
      data-h={auto ? 'auto' : widget.h}
    >
      {editing && (
        <Group gap={4} mb={6} justify="space-between" wrap="nowrap" className="hb-dash-tools">
          <Text fz="xs" c="dimmed" truncate style={{ minWidth: 0 }}>
            {name}
          </Text>
          <Group gap={2} wrap="nowrap">
            {!auto && onAutoHeight && (
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
            {def?.fields?.length && onSettings ? (
              <ActionIcon
                variant="subtle"
                color="gray"
                onClick={onSettings}
                aria-label={t('dashboards.settings', 'Einstellungen')}
              >
                <IconSettings size={16} />
              </ActionIcon>
            ) : null}
            {onRemove && (
              <ActionIcon
                variant="subtle"
                color="red"
                disabled={busy}
                onClick={onRemove}
                aria-label={t('dashboards.remove', 'Entfernen')}
              >
                <IconTrash size={16} />
              </ActionIcon>
            )}
          </Group>
        </Group>
      )}
      <div
        ref={body}
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
  )
}

/**
 * Widgets on the shared dashboard grid (12 columns), with the tools to change
 * them in edit mode: drag the grip to move a widget (or arrow keys), the
 * corner to change its width and height (or Shift+arrows), the cog for its
 * settings, the bin to remove it. Used by own dashboards and by the start
 * pages; *save* stores the new list.
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
  save: (next: DashboardWidget[]) => Promise<unknown> | void
  picking: boolean
  setPicking: (open: boolean) => void
  /** Shown when no widget is left to show. */
  empty: ReactNode
}) {
  const { t } = useT()
  const { go } = useNav()
  const catalogue = useWidgetCatalogue()
  const allowed = useWidgetAllowed()
  const [configuring, setConfiguring] = useState<{
    widget: DashboardWidget
    isNew: boolean
  } | null>(null)
  // Content heights in rows, by widget id (0: draws nothing right now).
  const [rows, setRows] = useState<ReadonlyMap<string, number>>(() => new Map())
  const onMeasure = useCallback<Measure>(
    (id, n) => setRows((old) => (old.get(id) === n ? old : new Map(old).set(id, n))),
    [],
  )
  // While a move or resize is under way: the layout shown, for these widgets.
  const [draft, setDraft] = useState<{ of: DashboardWidget[]; items: Placed[] } | null>(null)
  const pointerDown = useRef(false)
  const pending = useRef<Placed[] | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const byType = useMemo(() => new Map(catalogue.map((d) => [d.type, d])), [catalogue])

  const shown = widgets.filter((w) => {
    const def = byType.get(w.type)
    return editing || (def !== undefined && allowed(def))
  })
  // In edit mode every widget takes room, so an empty one can be moved too.
  const measured = useMemo(
    () => (editing ? new Map([...rows].filter(([, n]) => n > 0)) : rows),
    [rows, editing],
  )
  const placed = layout(shown, measured)
  const items = draft?.of === widgets ? draft.items : placed
  const hidden = shown.filter((w) => !placed.some((p) => p.widget.id === w.id))

  const store = (next: DashboardWidget[]) => {
    pending.current = null
    void Promise.resolve(save(next)).finally(() => setDraft(null))
  }
  // Every save keeps the spots, so a dashboard from before them keeps its look.
  const saveAll = (next: DashboardWidget[]) => store(withSpots(next, items))

  const flush = () => {
    clearTimeout(timer.current)
    if (pending.current) store(toWidgets(pending.current, placed))
  }

  // A drag saves when the pointer is let go, keys a moment after the last one.
  useEffect(() => {
    if (!editing) return
    const up = () => {
      if (!pointerDown.current) return
      pointerDown.current = false
      flush()
    }
    window.addEventListener('pointerup', up)
    window.addEventListener('pointercancel', up)
    return () => {
      window.removeEventListener('pointerup', up)
      window.removeEventListener('pointercancel', up)
    }
  })
  useEffect(() => () => clearTimeout(timer.current), [])

  const change = (next: Placed[]) => {
    if (busy) return
    setDraft({ of: widgets, items: next })
    pending.current = next
    if (pointerDown.current) return
    clearTimeout(timer.current)
    timer.current = setTimeout(() => store(toWidgets(next, placed)), 400)
  }

  const add = (def: WidgetDef) => {
    setPicking(false)
    const w = widthOf({ size: def.size })
    const spot = freeSpot(items, w, START_ROWS, COLS)
    const widget: DashboardWidget = {
      id: newId(widgets),
      type: def.type,
      size: def.size,
      x: spot.x,
      y: spot.y,
      w,
      config: defaults(def),
    }
    if (def.fields?.length) setConfiguring({ widget, isNew: true })
    else saveAll([...widgets, widget])
  }

  // A link inside a widget to a page of the app opens it without a reload.
  const followLink = (e: ReactMouseEvent) => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey) return
    const a = (e.target as HTMLElement).closest('a')
    const href = a?.getAttribute('href')
    if (!a || !href || a.target || !href.startsWith('/') || href.startsWith('//')) return
    e.preventDefault()
    go(href)
  }

  const cell = (w: DashboardWidget, p: Placed | null) => {
    const def = byType.get(w.type)
    return (
      <GridCell
        widget={w}
        def={def}
        allowed={def !== undefined && allowed(def)}
        editing={editing}
        busy={busy}
        w={p?.w ?? widthOf(w)}
        auto={p ? p.auto : w.h === undefined}
        onMeasure={onMeasure}
        onAutoHeight={
          p
            ? () => saveAll(widgets.map((x) => (x.id === w.id ? withBox(x, p, undefined) : x)))
            : undefined
        }
        onSettings={() => setConfiguring({ widget: w, isNew: false })}
        onRemove={() => saveAll(widgets.filter((x) => x.id !== w.id))}
      />
    )
  }

  return (
    <>
      {items.length === 0 ? (
        empty
      ) : (
        <div
          className={['hb-dash', editing ? 'editing' : ''].join(' ').trim()}
          onPointerDownCapture={() => {
            pointerDown.current = editing
          }}
          onClick={followLink}
        >
          <DashboardGrid
            items={items}
            itemKey={(p) => p.widget.id}
            cols={COLS}
            rowHeight={ROW}
            gap={GAP}
            heights={[]}
            label={t('dashboards.grid', 'Widgets')}
            className="hb-dash-grid"
            onChange={editing ? change : undefined}
            renderItem={(p) => cell(p.widget, p)}
          />
        </div>
      )}
      {/* Widgets that draw nothing right now wait out of sight until they do. */}
      {hidden.length > 0 && (
        <div className="hb-dash-waiting" aria-hidden>
          {hidden.map((w) => (
            <div key={w.id}>{cell(w, null)}</div>
          ))}
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
          saveAll(
            isNew ? [...widgets, widget] : widgets.map((x) => (x.id === widget.id ? widget : x)),
          )
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
