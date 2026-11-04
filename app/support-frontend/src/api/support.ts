import { apiFetch, apiFetchRaw } from '@hubra/api-client'
import type { ChangelogEntry, DeviceInfo, RoadmapItem, RoadmapStatus } from '@hubra/ui'

export type CaseKind = 'bug' | 'feature' | 'question'
export type CaseStatus = 'open' | 'planned' | 'in_progress' | 'done' | 'closed'
export type Severity = 'minor' | 'annoying' | 'blocking'

export const AREAS = [
  'members',
  'finance',
  'events',
  'posts',
  'polls',
  'groups',
  'inventory',
  'mail',
  'settings',
  'account',
  'modules',
  'other',
] as const
export type Area = (typeof AREAS)[number]

export interface CaseComment {
  id: number
  body: string
  fromStaff: boolean
  internal: boolean
  createdAt: string
  author: string | null
}

export interface SupportCase {
  id: number
  kind: CaseKind
  status: CaseStatus
  title: string
  description: string
  steps: string | null
  expected: string | null
  useCase: string | null
  area: Area | null
  severity: Severity | null
  page: string | null
  isPublic: boolean
  mergedInto: { id: number; title: string; status: CaseStatus } | null
  votes: number
  commentCount: number
  createdAt: string
  updatedAt: string
  closedAt: string | null
  comments?: CaseComment[]
}

export interface NewCase {
  kind: CaseKind
  title: string
  description: string
  steps?: string
  expected?: string
  useCase?: string
  area?: Area | null
  severity?: Severity | null
  page?: string
  fingerprint?: DeviceInfo
}

export interface Profile {
  id: number
  email: string
  name: string
  firstName: string
  avatarColor: string | null
  isSuperadmin: boolean
}

export function getProfile(signal?: AbortSignal) {
  return apiFetch<Profile>('/global/account/profile', { signal })
}

export function sendCase(body: NewCase) {
  return apiFetch<SupportCase>('/global/support/cases', { method: 'POST', body: JSON.stringify(body) })
}

export function myCases() {
  return apiFetch<SupportCase[]>('/global/support/cases')
}

export function myCase(id: number) {
  return apiFetch<SupportCase>(`/global/support/cases/${id}`)
}

export function replyToCase(id: number, body: string) {
  return apiFetch<CaseComment>(`/global/support/cases/${id}/comments`, {
    method: 'POST',
    body: JSON.stringify({ body }),
  })
}

export interface RoadmapResponse {
  statuses: RoadmapStatus[]
  items: RoadmapItem[]
}

/** Anyone: the one roadmap (planned items and ideas), with vote counts. */
export function publicRoadmap() {
  return apiFetch<RoadmapResponse>('/global/roadmap')
}

/** Signed in: the same list with the person's own votes. */
export function myRoadmap() {
  return apiFetch<RoadmapResponse>('/global/support/roadmap')
}

/** An idea votes by its case id, a planned item by its id. */
export function setVote(item: RoadmapItem, on: boolean) {
  const path =
    item.source === 'idea' && item.caseId != null
      ? `/global/support/roadmap/${item.caseId}/vote`
      : `/global/support/roadmap/items/${encodeURIComponent(item.id)}/vote`
  return apiFetch<{ id: number | string; votes: number; voted: boolean }>(path, {
    method: on ? 'POST' : 'DELETE',
  })
}

export function changelog(lang: string) {
  return apiFetch<{ version: string; entries: ChangelogEntry[] }>(
    `/global/version/changelog?lang=${encodeURIComponent(lang)}`,
  )
}

// ── Privacy requests ──────────────────────────────────────────────────────

export interface DeletionCheck {
  canDelete: boolean
  blockers: { kind: 'club' | 'club_owner' | 'platform'; name: string; slug: string | null }[]
}

export function deletionCheck() {
  return apiFetch<DeletionCheck>('/global/account/deletion')
}

export function deleteAccount(currentPassword: string) {
  return apiFetch<void>('/global/account/deletion', {
    method: 'POST',
    body: JSON.stringify({ currentPassword }),
  })
}

/** The account's data as a JSON file the browser saves. */
export async function downloadExport(): Promise<void> {
  const res = await apiFetchRaw('/global/account/export')
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const blob = await res.blob()
  const name =
    /filename="([^"]+)"/.exec(res.headers.get('Content-Disposition') ?? '')?.[1] ?? 'hubra-konto.json'
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export interface MyClub {
  tenant_id: number
  tenant_slug: string
  tenant_name: string
}

export function myClubs() {
  return apiFetch<{ tenants: MyClub[] }>('/global/account/my-tenants').then((r) => r.tenants ?? [])
}

/** Send a case, for one of the person's clubs when `club` is set. */
export function sendCaseFor(body: NewCase, club: string | null) {
  return apiFetch<SupportCase>('/global/support/cases', {
    method: 'POST',
    body: JSON.stringify(body),
    headers: club ? { 'X-Tenant-Slug': club } : undefined,
  })
}
