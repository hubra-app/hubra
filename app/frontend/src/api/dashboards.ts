import { apiFetch } from '@hubra/api-client'

export type WidgetSize = 's' | 'm' | 'l'

/** One widget on a dashboard; `type` names a built-in or plugin widget. */
export interface DashboardWidget {
  id: string
  type: string
  /** The size before the grid; still set, from `w`, for older apps. */
  size: WidgetSize
  /** Columns spanned on a wide screen, 2 to 12 (from `size` when missing). */
  w?: number
  /** Rows of the grid it is high, 1 to 24; missing: as tall as its content. */
  h?: number
  config: Record<string, unknown>
}

export interface Dashboard {
  id: number
  name: string
  /** Shared with the club: every member sees it (each only the widgets they may). */
  shared: boolean
  /** Shared with these groups only; empty: the whole club (when shared). */
  groups?: { id: number; name: string }[]
  widgets: DashboardWidget[]
  owner: { id: number; name: string | null }
  mine: boolean
  canEdit: boolean
  updatedAt: string | null
}

export interface DashboardList {
  items: Dashboard[]
  /** The member may share their dashboards with the club. */
  canShare: boolean
  max: number
}

const BASE = '/app/dashboards'

export function listDashboards(): Promise<DashboardList> {
  return apiFetch<DashboardList>(`${BASE}/`)
}

export function createDashboard(name: string, widgets: DashboardWidget[] = []): Promise<Dashboard> {
  return apiFetch<Dashboard>(`${BASE}/`, { method: 'POST', body: JSON.stringify({ name, widgets }) })
}

export function updateDashboard(
  id: number,
  change: { name?: string; widgets?: DashboardWidget[] },
): Promise<Dashboard> {
  return apiFetch<Dashboard>(`${BASE}/${id}`, { method: 'PATCH', body: JSON.stringify(change) })
}

/** Share with the club (no groupIds), with chosen groups, or stop sharing. */
export function shareDashboard(
  id: number,
  shared: boolean,
  groupIds: number[] = [],
): Promise<Dashboard> {
  return apiFetch<Dashboard>(`${BASE}/${id}/sharing`, {
    method: 'PUT',
    body: JSON.stringify({ shared, groupIds }),
  })
}

export function deleteDashboard(id: number): Promise<void> {
  return apiFetch<void>(`${BASE}/${id}`, { method: 'DELETE' })
}

/** A start page: its widgets, or `null` while it shows the built-in layout. */
export interface HomePage {
  widgets: DashboardWidget[] | null
  updatedAt: string | null
  canEdit: boolean
}

export type HomeKind = 'club' | 'me'

export function getHomePages(): Promise<Record<HomeKind, HomePage>> {
  return apiFetch<Record<HomeKind, HomePage>>(`${BASE}/home`)
}

export function saveHomePage(kind: HomeKind, widgets: DashboardWidget[]): Promise<Omit<HomePage, 'canEdit'>> {
  return apiFetch(`${BASE}/home/${kind}`, { method: 'PUT', body: JSON.stringify({ widgets }) })
}

export function resetHomePage(kind: HomeKind): Promise<Omit<HomePage, 'canEdit'>> {
  return apiFetch(`${BASE}/home/${kind}`, { method: 'DELETE' })
}

/** A widget a module or plugin offers as a contract (docs/contracts.md). */
export interface ContractWidget {
  name: string
  /** Stored on dashboards as this type. */
  type: string
  module: string
  plugin: string | null
  /** Translation keys, or plain text. */
  label: string
  description: string
  perm: string | null
  size: WidgetSize
  /** stat and list are drawn by the app; custom by the plugin's own component. */
  view: 'stat' | 'list' | 'custom'
  fields: { key: string; label: string; kind: 'text' | 'number' | 'switch'; default?: unknown }[]
}

/** What a stat widget shows. */
export interface StatWidgetData {
  value: number | string
  sub?: string | null
  path?: string | null
}

/** What a list widget shows. */
export interface ListWidgetData {
  items: { label: string; sub?: string | null; path?: string | null }[]
  total?: number | null
}

/** The contract widgets this member may add here (module on, right held). */
export function listContractWidgets(): Promise<{ items: ContractWidget[] }> {
  return apiFetch(`${BASE}/widgets`)
}

/** What contract widget `name` shows with these settings, read as the member. */
export function getWidgetData<T = unknown>(
  name: string,
  config: Record<string, unknown>,
): Promise<{ data: T }> {
  return apiFetch(`${BASE}/widgets/${encodeURIComponent(name)}/data`, {
    method: 'POST',
    body: JSON.stringify({ config }),
  })
}
