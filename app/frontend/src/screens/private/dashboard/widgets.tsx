/* eslint-disable react-refresh/only-export-components -- the catalogue hooks sit with the widgets they list */
import { useMemo, type ComponentType, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Anchor, Group, Paper, Stack, Text, UnstyledButton } from '@mantine/core'
import { useT } from '@/locales/i18n'
import { useAuth, useNav } from '@/context/AppContext'
import { useModules } from '@/modules/useModules'
import { usePluginWidgets, PluginBoundary, PluginSlot, useSlotFilled } from '@/plugins'
import { StatTile } from '@/components/ui'
import {
  MyEventsCard,
  MyPaymentsCard,
  MySummaryTiles,
  MyVotesCard,
} from '@/screens/private/account/Account'
import { MyAttendanceCard } from '@/screens/private/account/MyAttendanceCard'
import { MyGroupsCard } from '@/screens/private/account/MyGroupsCard'
import { VoteNeededCard } from './homeCards'
import { qk } from '@/data/keys'
import { useDashboardSummary, useEvents, usePolls, usePosts } from '@/data/lists'
import { getMemberStats } from '@/api/members'
import {
  getWidgetData,
  listContractWidgets,
  type ContractWidget,
  type DashboardWidget,
  type ListWidgetData,
  type StatWidgetData,
  type WidgetSize,
} from '@/api/dashboards'

/** A setting the member fills in when adding a widget. */
export interface WidgetField {
  key: string
  label: string
  kind: 'text' | 'textarea' | 'number' | 'switch'
  default?: string | number | boolean
  min?: number
  max?: number
  hint?: string
}

type Config = Record<string, unknown>

/** A widget members can put on a dashboard. */
export interface WidgetDef {
  type: string
  label: string
  description: string
  size: WidgetSize
  module?: string
  perm?: string
  fields?: WidgetField[]
  /** Comes from a plugin (shown in its own error boundary). */
  plugin?: string
  render: ComponentType<{ config: Config; size: WidgetSize }>
}

/** A titled box with the widget's content. */
export function WidgetFrame({
  title,
  action,
  children,
}: {
  title: string
  action?: ReactNode
  children: ReactNode
}) {
  return (
    <Paper withBorder p="md" style={{ height: '100%' }}>
      <Group justify="space-between" mb="xs" wrap="nowrap">
        <Text fw={700} fz="sm" style={{ minWidth: 0 }} truncate>
          {title}
        </Text>
        {action}
      </Group>
      {children}
    </Paper>
  )
}

function Empty({ children }: { children: ReactNode }) {
  return (
    <Text fz="sm" c="dimmed" py="xs">
      {children}
    </Text>
  )
}

function Row({ title, sub, onClick }: { title: string; sub?: string; onClick?: () => void }) {
  return (
    <UnstyledButton
      onClick={onClick}
      style={{
        display: 'block',
        width: '100%',
        padding: '6px 0',
        borderBottom: '1px solid var(--mantine-color-line-0)',
      }}
    >
      <Text fz="sm" fw={600} truncate>
        {title}
      </Text>
      {sub && (
        <Text fz="xs" c="dimmed" truncate>
          {sub}
        </Text>
      )}
    </UnstyledButton>
  )
}

const num = (config: Config, key: string, fallback: number, max = 20) => {
  const n = Number(config[key])
  return Number.isFinite(n) && n > 0 ? Math.min(Math.round(n), max) : fallback
}

const str = (config: Config, key: string) =>
  typeof config[key] === 'string' ? (config[key] as string) : ''

// ── Built-in widgets ───────────────────────────────────────────────────────

function MembersStat() {
  const { t } = useT()
  const { go } = useNav()
  const { data } = useDashboardSummary()
  return (
    <StatTile
      label={t('dashboard.activeMembers')}
      value={data ? String(data.stats.activeMembers) : '—'}
      sub={data ? t('dashboard.joinedLast30', { count: data.stats.memberDelta }) : undefined}
      onClick={() => go('/app/members')}
    />
  )
}

function EventsStat() {
  const { t } = useT()
  const { go } = useNav()
  const { data } = useDashboardSummary()
  return (
    <StatTile
      label={t('dashboard.upcomingEventsLabel')}
      value={data ? String(data.stats.upcomingEvents) : '—'}
      accent="var(--mantine-color-acc-text)"
      onClick={() => go('/app/operations/events')}
    />
  )
}

function OpenInvoicesStat() {
  const { t } = useT()
  const { go } = useNav()
  const { data } = useDashboardSummary()
  const open = data?.stats.openInvoices
  return (
    <StatTile
      label={t('common.openInvoices')}
      value={open == null ? '—' : String(open)}
      sub={open ? t('dashboard.outstanding', { count: open }) : t('dashboard.allPaid')}
      accent="var(--mantine-color-acc-7)"
      onClick={() => go('/app/finance/invoices')}
    />
  )
}

/** Numbers plugins add to the club overview (slot dashboard.stats). */
function PluginStats() {
  const filled = useSlotFilled('dashboard.stats')
  if (!filled) return null
  return (
    <div className="hb-dash-stats">
      <PluginSlot name="dashboard.stats" />
    </div>
  )
}

/** Cards plugins add to the member's own page (slot account.cards). */
function PluginCards() {
  const filled = useSlotFilled('account.cards')
  if (!filled) return null
  return (
    <Stack gap="md">
      <PluginSlot name="account.cards" />
    </Stack>
  )
}

function FinanceStat() {
  const { t, i18n } = useT()
  const { go } = useNav()
  const { data } = useDashboardSummary()
  const net = data?.stats.netMonth
  return (
    <StatTile
      label={t('dashboard.netThisMonth')}
      value={
        net == null ? '—' : `CHF ${net.toLocaleString(i18n.language, { maximumFractionDigits: 0 })}`
      }
      sub={
        data?.stats.openInvoices != null
          ? t('dashboards.w.openInvoicesCount', '{{count}} offene Rechnungen', {
              count: data.stats.openInvoices,
            })
          : undefined
      }
      accent="var(--mantine-color-green-text)"
      onClick={() => go('/app/finance')}
    />
  )
}

function UpcomingEvents({ config }: { config: Config }) {
  const { t, i18n } = useT()
  const { go } = useNav()
  const { currentUser } = useAuth()
  const { events } = useEvents()
  const count = num(config, 'count', 5)
  const onlyMine = config.onlyMine === true
  const today = new Date().toISOString().slice(0, 10)
  const list = events
    .filter((e) => e.date >= today)
    .filter((e) => !onlyMine || e.attendees.includes(currentUser?.id ?? ''))
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(0, count)
  return (
    <WidgetFrame
      title={
        str(config, 'title') ||
        (onlyMine
          ? t('dashboards.w.myEvents', 'Meine Anlässe')
          : t('dashboard.upcomingEvents.title'))
      }
    >
      {list.length === 0 ? (
        <Empty>{t('dashboard.noUpcomingEvents')}</Empty>
      ) : (
        list.map((e) => (
          <Row
            key={e.id}
            title={e.title}
            sub={[
              new Date(`${e.date}T00:00:00`).toLocaleDateString(i18n.language, {
                weekday: 'short',
                day: 'numeric',
                month: 'short',
              }),
              e.time,
              e.location,
            ]
              .filter(Boolean)
              .join(' · ')}
            onClick={() => go(`/app/operations/events?event=${e.id}`)}
          />
        ))
      )}
    </WidgetFrame>
  )
}

function RecentPosts({ config }: { config: Config }) {
  const { t } = useT()
  const { go } = useNav()
  const { posts } = usePosts()
  const list = [...posts]
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
    .slice(0, num(config, 'count', 5))
  return (
    <WidgetFrame title={str(config, 'title') || t('dashboard.recentPosts.title')}>
      {list.length === 0 ? (
        <Empty>{t('dashboards.w.noPosts', 'Noch keine Beiträge.')}</Empty>
      ) : (
        list.map((p) => (
          <Row
            key={p.id}
            title={p.title}
            sub={p.summary || p.author}
            onClick={() => go(`/app/operations/posts/${p.id}`)}
          />
        ))
      )}
    </WidgetFrame>
  )
}

function OpenPolls({ config }: { config: Config }) {
  const { t, i18n } = useT()
  const { go } = useNav()
  const { polls } = usePolls()
  const list = polls
    .filter((p) => p.status === 'open' && p.myVote == null && p.mayVote !== false)
    .slice(0, num(config, 'count', 5))
  return (
    <WidgetFrame
      title={str(config, 'title') || t('dashboards.w.openPolls', 'Offene Abstimmungen für mich')}
    >
      {list.length === 0 ? (
        <Empty>{t('dashboards.w.noPolls', 'Keine offenen Abstimmungen.')}</Empty>
      ) : (
        list.map((p) => (
          <Row
            key={p.id}
            title={p.question}
            sub={
              p.closesAt
                ? t('dashboards.w.closes', 'endet am {{date}}', {
                    date: new Date(p.closesAt).toLocaleDateString(i18n.language),
                  })
                : undefined
            }
            onClick={() => go(`/app/operations/polls?poll=${p.id}`)}
          />
        ))
      )}
    </WidgetFrame>
  )
}

function MemberChart({ config }: { config: Config }) {
  const { t, i18n } = useT()
  const today = new Date()
  const on = today.toISOString().slice(0, 10)
  const year = today.getFullYear()
  const { data } = useQuery({
    queryKey: qk.members.stats(on, year),
    queryFn: () => getMemberStats(on, year),
  })
  const months = data?.months ?? []
  const max = Math.max(1, ...months.flatMap((m) => [m.joins, m.leaves]))
  return (
    <WidgetFrame
      title={
        str(config, 'title') ||
        t('dashboards.w.joinsLeaves', 'Ein- und Austritte {{year}}', { year })
      }
      action={
        data ? (
          <Text fz="xs" c="dimmed">
            {t('dashboards.w.total', '{{count}} Mitglieder', { count: data.total })}
          </Text>
        ) : undefined
      }
    >
      <Group gap={4} align="flex-end" h={110} wrap="nowrap" aria-hidden>
        {months.map((m) => (
          <Stack key={m.month} gap={2} align="center" style={{ flex: 1, minWidth: 0 }}>
            <Group gap={1} align="flex-end" h={90} wrap="nowrap">
              <div
                style={{
                  width: 6,
                  height: `${(m.joins / max) * 90}px`,
                  background: 'var(--mantine-color-green-6)',
                  borderRadius: 2,
                }}
              />
              <div
                style={{
                  width: 6,
                  height: `${(m.leaves / max) * 90}px`,
                  background: 'var(--mantine-color-red-5)',
                  borderRadius: 2,
                }}
              />
            </Group>
            <Text fz={10} c="dimmed">
              {new Date(`${m.month}-01T00:00:00`).toLocaleDateString(i18n.language, {
                month: 'narrow',
              })}
            </Text>
          </Stack>
        ))}
      </Group>
      <Text fz="xs" c="dimmed" mt={4}>
        {t('dashboards.w.joinsLeavesLegend', 'Grün: Eintritte, rot: Austritte')}
      </Text>
    </WidgetFrame>
  )
}

function Note({ config }: { config: Config }) {
  const { t } = useT()
  const text = str(config, 'text')
  return (
    <WidgetFrame title={str(config, 'title') || t('dashboards.w.note', 'Notiz')}>
      <Text fz="sm" style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
        {text ||
          t('dashboards.w.noteEmpty', 'Noch leer. Bearbeite das Widget, um Text einzufügen.')}
      </Text>
    </WidgetFrame>
  )
}

/** "Label | https://…" per line; only http(s) addresses become links. */
export function parseLinks(text: string): { label: string; url: string }[] {
  return text
    .split('\n')
    .map((line) => {
      const [a, b] = line.includes('|') ? line.split('|', 2) : [line, line]
      return { label: a.trim(), url: b.trim() }
    })
    .filter((l) => l.label && /^https?:\/\/\S+$/i.test(l.url))
}

function Links({ config }: { config: Config }) {
  const { t } = useT()
  const links = parseLinks(str(config, 'links'))
  return (
    <WidgetFrame title={str(config, 'title') || t('dashboards.w.links', 'Links')}>
      {links.length === 0 ? (
        <Empty>{t('dashboards.w.linksEmpty', 'Noch keine Links.')}</Empty>
      ) : (
        <Stack gap={6}>
          {links.map((l, i) => (
            <Anchor key={i} href={l.url} target="_blank" rel="noopener noreferrer" fz="sm">
              {l.label}
            </Anchor>
          ))}
        </Stack>
      )}
    </WidgetFrame>
  )
}

// ── Widgets offered as contracts ───────────────────────────────────────────

/** The data a contract widget's handler reads for the viewer. */
function useWidgetData<T>(name: string, config: Config) {
  return useQuery({
    queryKey: qk.widgetData(name, config),
    queryFn: () => getWidgetData<T>(name, config).then((r) => r.data),
    staleTime: 60_000,
  })
}

function ContractStat({ widget, config }: { widget: ContractWidget; config: Config }) {
  const { t } = useT()
  const { go } = useNav()
  const { data, isError } = useWidgetData<StatWidgetData>(widget.name, config)
  const path = data?.path
  return (
    <StatTile
      label={str(config, 'title') || t(widget.label, widget.label)}
      value={isError ? '!' : data ? String(data.value) : '—'}
      sub={isError ? t('dashboards.widgetFailed', 'Konnte nicht geladen werden') : (data?.sub ?? undefined)}
      onClick={path ? () => go(path) : undefined}
    />
  )
}

function ContractList({ widget, config }: { widget: ContractWidget; config: Config }) {
  const { t } = useT()
  const { go } = useNav()
  const { data, isError } = useWidgetData<ListWidgetData>(widget.name, config)
  const title = str(config, 'title') || t(widget.label, widget.label)
  const items = data?.items ?? []
  return (
    <WidgetFrame title={title}>
      {isError ? (
        <Empty>{t('dashboards.widgetFailed', 'Konnte nicht geladen werden')}</Empty>
      ) : data && items.length === 0 ? (
        <Empty>{t('dashboards.nothing', 'Nichts anzuzeigen')}</Empty>
      ) : (
        <Stack gap={0}>
          {items.map((row, i) => (
            <Row
              key={i}
              title={row.label}
              sub={row.sub ?? undefined}
              onClick={row.path ? () => go(row.path as string) : undefined}
            />
          ))}
          {data?.total != null && data.total > items.length && (
            <Text fz="xs" c="dimmed" pt={4}>
              {t('dashboards.more', '{{count}} weitere', { count: data.total - items.length })}
            </Text>
          )}
        </Stack>
      )}
    </WidgetFrame>
  )
}

function ContractCustom({
  widget,
  config,
  size,
  component: C,
}: {
  widget: ContractWidget
  config: Config
  size: WidgetSize
  component?: ComponentType<{ config: Config; size: WidgetSize; data?: unknown }>
}) {
  const { t } = useT()
  const { data, isError } = useWidgetData<unknown>(widget.name, config)
  if (!C) {
    return (
      <WidgetFrame title={t(widget.label, widget.label)}>
        <Empty>{t('dashboards.noView', 'Das Plugin bringt keine Ansicht für dieses Widget mit')}</Empty>
      </WidgetFrame>
    )
  }
  if (isError) {
    return (
      <WidgetFrame title={t(widget.label, widget.label)}>
        <Empty>{t('dashboards.widgetFailed', 'Konnte nicht geladen werden')}</Empty>
      </WidgetFrame>
    )
  }
  return <C config={config} size={size} data={data} />
}

/** Widgets modules and plugins offer as contracts, for this member. */
function useContractWidgets(): ContractWidget[] {
  const { data } = useQuery({
    queryKey: qk.contractWidgets,
    queryFn: () => listContractWidgets().then((r) => r.items),
    staleTime: 5 * 60_000,
  })
  return data ?? []
}

// ── The catalogue ──────────────────────────────────────────────────────────

/** Every widget there is, built in and from plugins, translated. */
export function useWidgetCatalogue(): WidgetDef[] {
  const { t } = useT()
  const pluginWidgets = usePluginWidgets()
  const contractWidgets = useContractWidgets()
  return useMemo(() => {
    const title: WidgetField = {
      key: 'title',
      label: t('dashboards.f.title', 'Titel (leer: Standard)'),
      kind: 'text',
    }
    const count: WidgetField = {
      key: 'count',
      label: t('dashboards.f.count', 'Anzahl'),
      kind: 'number',
      default: 5,
      min: 1,
      max: 20,
    }
    const builtIn: WidgetDef[] = [
      {
        type: 'stat.members',
        label: t('dashboard.activeMembers'),
        description: t(
          'dashboards.d.membersStat',
          'Aktive Mitglieder und Eintritte der letzten 30 Tage',
        ),
        size: 's',
        module: 'members',
        render: MembersStat,
      },
      {
        type: 'stat.events',
        label: t('dashboards.w.eventsCount', 'Anzahl bevorstehender Anlässe'),
        description: t('dashboards.d.eventsStat', 'Wie viele Anlässe bevorstehen'),
        size: 's',
        module: 'events',
        render: EventsStat,
      },
      {
        type: 'stat.finance',
        label: t('dashboard.netThisMonth'),
        description: t('dashboards.d.financeStat', 'Ergebnis des Monats und offene Rechnungen'),
        size: 's',
        module: 'finance',
        perm: 'finance.invoices.read',
        render: FinanceStat,
      },
      {
        type: 'events.upcoming',
        label: t('dashboard.upcomingEvents.title'),
        description: t('dashboards.d.events', 'Die nächsten Anlässe, auf Wunsch nur deine'),
        size: 'm',
        module: 'events',
        fields: [
          title,
          count,
          {
            key: 'onlyMine',
            label: t('dashboards.f.onlyMine', 'Nur Anlässe, für die ich angemeldet bin'),
            kind: 'switch',
          },
        ],
        render: UpcomingEvents,
      },
      {
        type: 'posts.recent',
        label: t('dashboard.recentPosts.title'),
        description: t('dashboards.d.posts', 'Die neuesten Beiträge'),
        size: 'm',
        module: 'posts',
        fields: [title, count],
        render: RecentPosts,
      },
      {
        type: 'polls.open',
        label: t('dashboards.w.openPolls', 'Offene Abstimmungen für mich'),
        description: t('dashboards.d.polls', 'Umfragen, in denen du noch abstimmen kannst'),
        size: 'm',
        module: 'polls',
        fields: [title, count],
        render: OpenPolls,
      },
      {
        type: 'members.chart',
        label: t('dashboards.w.joinsLeavesShort', 'Ein- und Austritte'),
        description: t('dashboards.d.chart', 'Ein- und Austritte pro Monat in diesem Jahr'),
        size: 'm',
        module: 'members',
        perm: 'members.members.read',
        fields: [title],
        render: MemberChart,
      },
      {
        type: 'note',
        label: t('dashboards.w.note', 'Notiz'),
        description: t('dashboards.d.note', 'Ein Text, z. B. Termine oder Hinweise fürs Team'),
        size: 's',
        fields: [title, { key: 'text', label: t('dashboards.f.text', 'Text'), kind: 'textarea' }],
        render: Note,
      },
      {
        type: 'links',
        label: t('dashboards.w.links', 'Links'),
        description: t('dashboards.d.links', 'Wichtige Adressen auf einen Blick'),
        size: 's',
        fields: [
          title,
          {
            key: 'links',
            label: t('dashboards.f.links', 'Links'),
            kind: 'textarea',
            hint: t('dashboards.f.linksHint', 'Pro Zeile: Bezeichnung | https://…'),
          },
        ],
        render: Links,
      },
      {
        type: 'stat.openInvoices',
        label: t('common.openInvoices'),
        description: t('dashboards.d.openInvoices', 'Wie viele Rechnungen des Vereins offen sind'),
        size: 's',
        module: 'finance',
        perm: 'finance.invoices.read',
        render: OpenInvoicesStat,
      },
      {
        type: 'polls.voteNeeded',
        label: t('dashboard.voteNeeded.title'),
        description: t(
          'dashboards.d.voteNeeded',
          'Hinweis auf Umfragen, in denen du noch abstimmen musst; leer, wenn keine offen ist',
        ),
        size: 'l',
        module: 'polls',
        render: VoteNeededCard,
      },
      {
        type: 'me.payments',
        label: t('account.pendingPayment', 'Offene Zahlung'),
        description: t(
          'dashboards.d.myPayments',
          'Deine offenen Rechnungen mit QR-Rechnung; leer, wenn alles bezahlt ist',
        ),
        size: 'l',
        render: MyPaymentsCard,
      },
      {
        type: 'me.summary',
        label: t('dashboards.w.mySummary', 'Meine Zahlen'),
        description: t(
          'dashboards.d.mySummary',
          'Deine Anmeldungen, Abstimmungen und offenen Rechnungen',
        ),
        size: 'l',
        render: MySummaryTiles,
      },
      {
        type: 'me.events',
        label: t('common.myEvents', 'Meine Anlässe'),
        description: t(
          'dashboards.d.myEvents',
          'Anlässe, für die du angemeldet bist, mit Abmelden',
        ),
        size: 'l',
        module: 'events',
        render: MyEventsCard,
      },
      {
        type: 'me.votes',
        label: t('account.myVotes', 'Meine Abstimmungen'),
        description: t(
          'dashboards.d.myVotes',
          'Umfragen, in denen du abgestimmt hast, mit deiner Wahl',
        ),
        size: 'l',
        module: 'polls',
        render: MyVotesCard,
      },
      {
        type: 'me.attendance',
        label: t('dashboards.w.myAttendance', 'Meine Präsenz'),
        description: t(
          'dashboards.d.myAttendance',
          'Wie oft du an Trainings und Anlässen dabei warst',
        ),
        size: 'l',
        module: 'events',
        render: MyAttendanceCard,
      },
      {
        type: 'me.groups',
        label: t('dashboards.w.myGroups', 'Meine Gruppen'),
        description: t('dashboards.d.myGroups', 'Die Gruppen, in denen du bist'),
        size: 'l',
        module: 'groups',
        render: MyGroupsCard,
      },
      {
        type: 'plugins.stats',
        label: t('dashboards.w.pluginStats', 'Zahlen aus Plugins'),
        description: t(
          'dashboards.d.pluginStats',
          'Was installierte Plugins zur Vereinsübersicht beisteuern',
        ),
        size: 'l',
        render: PluginStats,
      },
      {
        type: 'plugins.cards',
        label: t('dashboards.w.pluginCards', 'Karten aus Plugins'),
        description: t(
          'dashboards.d.pluginCards',
          'Was installierte Plugins zu deiner persönlichen Seite beisteuern',
        ),
        size: 'l',
        render: PluginCards,
      },
    ]
    // A plugin component that draws a contract widget isn't a widget of its own.
    const drawers = new Map(
      pluginWidgets.filter((w) => w.contract).map((w) => [w.contract as string, w.component]),
    )
    const fromContracts: WidgetDef[] = contractWidgets.map((c) => ({
      type: c.type,
      label: t(c.label, c.label),
      description: c.description ? t(c.description, c.description) : '',
      size: c.size,
      module: c.module,
      perm: c.perm ?? undefined,
      plugin: c.plugin ?? undefined,
      fields: c.fields.map((f) => ({
        key: f.key,
        label: t(f.label, f.label),
        kind: f.kind,
        default: f.default as string | number | boolean | undefined,
      })),
      render:
        c.view === 'stat'
          ? (p) => <ContractStat widget={c} config={p.config} />
          : c.view === 'list'
            ? (p) => <ContractList widget={c} config={p.config} />
            : (p) => (
                <ContractCustom
                  widget={c}
                  config={p.config}
                  size={p.size}
                  component={drawers.get(c.name)}
                />
              ),
    }))
    const fromPlugins: WidgetDef[] = pluginWidgets.filter((w) => !w.contract).map((w) => ({
      type: `p:${w.plugin}.${w.id}`,
      label: t(w.label),
      description: w.description ? t(w.description) : '',
      size: w.size ?? 'm',
      module: w.module,
      perm: w.perm,
      plugin: w.plugin,
      fields: w.fields?.map((f) => ({ ...f, label: t(f.label) })),
      render: w.component,
    }))
    return [...builtIn, ...fromContracts, ...fromPlugins]
  }, [t, pluginWidgets, contractWidgets])
}

/** Whether this user may see *def* in this club. */
export function useWidgetAllowed(): (def: WidgetDef) => boolean {
  const modules = useModules()
  const { hasPermission } = useAuth()
  return (def) =>
    (!def.module || modules.canUse(def.module)) && (!def.perm || hasPermission(def.perm))
}

/** One widget, in a plugin's error boundary when it comes from one. */
export function WidgetView({
  def,
  config,
  size,
}: {
  def: WidgetDef
  config: Config
  size: WidgetSize
}) {
  const C = def.render
  const body = <C config={config} size={size} />
  return def.plugin ? <PluginBoundary plugin={def.plugin}>{body}</PluginBoundary> : body
}

// ── Start pages ────────────────────────────────────────────────────────────

const w = (id: string, type: string, size: WidgetSize, config: Config = {}) => ({
  id,
  type,
  size,
  config,
})

/** Dashboard › Verein until someone with the right changes it. */
export const CLUB_HOME = [
  w('vote', 'polls.voteNeeded', 'l'),
  w('members', 'stat.members', 's'),
  w('finance', 'stat.finance', 's'),
  w('events', 'stat.events', 's'),
  w('plugins', 'plugins.stats', 'l'),
  w('upcoming', 'events.upcoming', 'm', { count: 4 }),
  w('posts', 'posts.recent', 'm', { count: 5 }),
]

/** Dashboard › Persönlich until the member changes it. */
export const MY_HOME = [
  w('payments', 'me.payments', 'l'),
  w('summary', 'me.summary', 'l'),
  // Booking's "Heute vor Ort"; left out where Booking is off (see OPTIONAL_HOME).
  w('onsite', 'booking.onsite_today', 'l'),
  w('events', 'me.events', 'l'),
  w('votes', 'me.votes', 'l'),
  w('attendance', 'me.attendance', 'l'),
  w('groups', 'me.groups', 'l'),
  w('plugins', 'plugins.cards', 'l'),
]

/**
 * Widget types on a built-in start page that come from a plugin. They show
 * only while the catalogue offers them to this member, instead of an
 * "this widget is gone" box in clubs without the plugin.
 */
export const OPTIONAL_HOME = new Set(['booking.onsite_today'])

/** The built-in start page without plugin widgets this member can't use. */
export function useDefaultHome(widgets: DashboardWidget[]): DashboardWidget[] {
  const catalogue = useWidgetCatalogue()
  const allowed = useWidgetAllowed()
  return useMemo(
    () =>
      widgets.filter((wd) => {
        if (!OPTIONAL_HOME.has(wd.type)) return true
        const def = catalogue.find((d) => d.type === wd.type)
        return !!def && allowed(def)
      }),
    // allowed is a fresh closure each render; catalogue carries the change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [widgets, catalogue],
  )
}
