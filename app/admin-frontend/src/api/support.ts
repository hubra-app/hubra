import { apiFetch } from '@hubra/api-client'

const S = '/platform/support/cases'

export type CaseKind = 'bug' | 'feature' | 'question'
export type CaseStatus = 'open' | 'planned' | 'in_progress' | 'done' | 'closed'

export interface CaseComment {
  id: number
  body: string
  fromStaff: boolean
  internal: boolean
  createdAt: string
  author: string | null
}

export interface Fingerprint {
  browser?: string
  browserVersion?: string
  os?: string
  osVersion?: string
  deviceType?: 'phone' | 'tablet' | 'desktop'
  screenWidth?: number
  screenHeight?: number
  viewportWidth?: number
  viewportHeight?: number
  language?: string
  theme?: 'light' | 'dark'
  appVersion?: string
}

export interface StaffCase {
  id: number
  kind: CaseKind
  status: CaseStatus
  title: string
  description: string
  steps: string | null
  expected: string | null
  useCase: string | null
  area: string | null
  severity: 'minor' | 'annoying' | 'blocking' | null
  page: string | null
  fingerprint: Fingerprint
  isPublic: boolean
  /** ROADMAP.yaml item the idea is linked to. */
  roadmapItem: string | null
  mergedInto: { id: number; title: string; status: CaseStatus } | null
  votes: number
  commentCount: number
  createdAt: string
  updatedAt: string
  closedAt: string | null
  reporter: { id: number; name: string; email: string } | null
  club: { id: number; name: string; slug: string } | null
  awaitingReply?: boolean
  comments?: CaseComment[]
  merged?: { id: number; title: string; createdAt: string }[]
}

export interface CaseList {
  items: StaffCase[]
  total: number
  page: number
  perPage: number
  openCounts: Record<CaseKind, number>
}

export function listCases(params: {
  kind?: CaseKind | ''
  status?: CaseStatus | 'active' | ''
  area?: string
  q?: string
  page?: number
  perPage?: number
}) {
  const qs = new URLSearchParams()
  if (params.kind) qs.set('kind', params.kind)
  if (params.status) qs.set('status', params.status)
  if (params.area) qs.set('area', params.area)
  if (params.q) qs.set('q', params.q)
  if (params.page) qs.set('page', String(params.page))
  if (params.perPage) qs.set('per_page', String(params.perPage))
  return apiFetch<CaseList>(`${S}?${qs}`)
}

export function getCase(id: number) {
  return apiFetch<StaffCase>(`${S}/${id}`)
}

export function updateCase(
  id: number,
  body: Partial<{
    status: CaseStatus
    isPublic: boolean
    roadmapItem: string | null
    title: string
    description: string
    area: string | null
    notify: boolean
  }>,
) {
  return apiFetch<StaffCase>(`${S}/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
}

export function commentOnCase(id: number, body: string, internal: boolean) {
  return apiFetch<CaseComment>(`${S}/${id}/comments`, {
    method: 'POST',
    body: JSON.stringify({ body, internal }),
  })
}

export function mergeCase(id: number, into: number) {
  return apiFetch<StaffCase>(`${S}/${id}/merge`, {
    method: 'POST',
    body: JSON.stringify({ into }),
  })
}
