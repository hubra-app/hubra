import { apiFetch } from '@hubra/api-client'

export interface PermissionsResponse {
  is_admin: boolean
  is_superadmin: boolean
  permissions: string[]
  global_permissions: string[]
  global_roles: string[]
  impersonation: {
    is_impersonating: boolean
    impersonator_id: number
    tenant_slug: string
    reason: string | null
    expires_at: string | null
    restricted_actions: string[]
  } | null
}

export async function getMyPermissions(
  signal?: AbortSignal,
): Promise<PermissionsResponse> {
  return apiFetch<PermissionsResponse>('/account/permissions', { signal })
}

export async function logout(): Promise<void> {
  await apiFetch('/auth/logout', { method: 'POST' }).catch(() => {})
}

/** The signed-in person, for the user card in the shell. */
export interface Profile {
  id: number
  email: string
  name: string
  avatarColor: string
  language: string
  isSuperadmin: boolean
}

export async function getProfile(signal?: AbortSignal): Promise<Profile> {
  return apiFetch<Profile>('/account/profile', { signal })
}
