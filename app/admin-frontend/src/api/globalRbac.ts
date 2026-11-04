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

export interface UserWithRoles {
  user_id: number
  email: string
  roles: { id: number; name: string }[]
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

export async function assignUserRole(
  userId: number,
  roleId: number,
): Promise<{ user_id: number; role_id: number; role_name: string }> {
  return apiFetch(`/platform/system/users/${userId}/roles`, {
    method: 'POST',
    body: JSON.stringify({ role_id: roleId }),
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
