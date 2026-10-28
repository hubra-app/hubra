import { apiFetch } from '@hubra/api-client'

export interface ClubSettings {
  club_name?: string
  /** Members ask to leave and an admin approves (off: they leave at once). */
  leave_requires_approval?: boolean
  club_description?: string
  logo?: string
  primary_color?: string
  secondary_color?: string
  accent_color?: string
  timezone?: string
  locale?: string
  date_format?: string
  member_directory_visible?: boolean
  public_group_listing?: boolean
  announcement_banner_text?: string
  announcement_banner_active?: boolean
}

export async function getClubSettings(): Promise<ClubSettings> {
  const data = await apiFetch<{ settings: ClubSettings }>('/admin/club-settings')
  return data.settings
}

export async function updateClubSettings(
  patch: Partial<ClubSettings>,
): Promise<ClubSettings> {
  const data = await apiFetch<{ settings: ClubSettings }>('/admin/club-settings', {
    method: 'PATCH',
    body: JSON.stringify(patch),
  })
  return data.settings
}

export interface Domain {
  id: number
  domain: string
  verified: boolean
  verification_token: string | null
  verification_status: string
  is_primary: boolean
  verified_at: string | null
  created_at: string | null
  updated_at: string | null
}

export async function listDomains(): Promise<Domain[]> {
  const data = await apiFetch<{ domains: Domain[] }>('/admin/domains')
  return data.domains
}

export async function addDomain(
  domain: string,
): Promise<{ domain: Domain; txt_record: { name: string; value: string; instructions: string } }> {
  return apiFetch('/admin/domains', {
    method: 'POST',
    body: JSON.stringify({ domain }),
  })
}

export async function verifyDomain(
  id: number,
): Promise<{ domain: Domain; verified: boolean; error: string | null }> {
  return apiFetch(`/admin/domains/${id}/verify`, { method: 'POST' })
}

export async function removeDomain(id: number): Promise<void> {
  await apiFetch(`/admin/domains/${id}`, { method: 'DELETE' })
}

export async function setPrimaryDomain(id: number): Promise<{ domain: Domain }> {
  return apiFetch(`/admin/domains/${id}/primary`, { method: 'PATCH' })
}
