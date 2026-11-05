import { apiFetch } from '@hubra/api-client'

export type WidgetSize = 's' | 'm' | 'l'

/** One widget on a dashboard; `type` names a built-in or plugin widget. */
export interface DashboardWidget {
  id: string
  type: string
  size: WidgetSize
  config: Record<string, unknown>
}

export interface Dashboard {
  id: number
  name: string
  /** Shared with the club: every member sees it (each only the widgets they may). */
  shared: boolean
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

export function shareDashboard(id: number, shared: boolean): Promise<Dashboard> {
  return apiFetch<Dashboard>(`${BASE}/${id}/sharing`, {
    method: 'PUT',
    body: JSON.stringify({ shared }),
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
