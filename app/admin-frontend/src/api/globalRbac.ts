import { apiFetch } from '@hubra/api-client'

export interface GlobalRole {
  id: number
  name: string
  description: string | null
  is_system: boolean
  permissions: string[]
}

export interface GlobalPermission {
  id: number
  key: string
  display_name: string
  description: string | null
}

/** A role held by a person; `clubs` is empty when it holds on the whole
 * platform, otherwise it holds on these clubs only. */
export interface UserRole {
  id: number
  name: string
  clubs: { id: number; name: string }[]
}

export interface UserWithRoles {
  user_id: number
  email: string
  roles: UserRole[]
}

export interface UserSearchResult {
  id: number
  email: string
  name: string
}

export async function listGlobalRoles(): Promise<{ roles: GlobalRole[] }> {
  return apiFetch<{ roles: GlobalRole[] }>('/platform/system/global-roles')
}

export async function createGlobalRole(data: {
  name: string
  description?: string
  permissions: string[]
}): Promise<{ role: GlobalRole }> {
  return apiFetch('/platform/system/global-roles', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateGlobalRole(
  id: number,
  data: { description?: string; permissions?: string[] },
): Promise<{ role: GlobalRole }> {
  return apiFetch(`/platform/system/global-roles/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function listGlobalPermissions(): Promise<{ permissions: GlobalPermission[] }> {
  return apiFetch<{ permissions: GlobalPermission[] }>('/platform/system/global-permissions')
}

export async function getUserRoles(userId: number): Promise<UserWithRoles> {
  return apiFetch<UserWithRoles>(`/platform/system/users/${userId}/roles`)
}

/** `tenantIds` limits the role to those clubs; empty for the whole platform. */
export async function assignUserRole(
  userId: number,
  roleId: number,
  tenantIds: number[] = [],
): Promise<{ user_id: number; role_id: number; role_name: string }> {
  return apiFetch(`/platform/system/users/${userId}/roles`, {
    method: 'POST',
    body: JSON.stringify({ role_id: roleId, tenant_ids: tenantIds }),
  })
}

export async function removeUserRole(
  userId: number,
  roleId: number,
): Promise<{ ok: boolean }> {
  return apiFetch(`/platform/system/users/${userId}/roles/${roleId}`, {
    method: 'DELETE',
  })
}

export async function searchUsers(query: string): Promise<{ users: UserSearchResult[] }> {
  return apiFetch<{ users: UserSearchResult[] }>(
    `/platform/system/users/search?q=${encodeURIComponent(query)}`,
  )
}
