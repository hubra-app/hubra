import { apiFetch } from '@vollbuild/api-client'

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

export async function login(
  email: string,
  password: string,
  keepSignedIn = true,
): Promise<{ mustChangePassword?: boolean }> {
  return apiFetch<{ mustChangePassword?: boolean }>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password, keepSignedIn }),
  })
}

export async function logout(): Promise<void> {
  await apiFetch('/auth/logout', { method: 'POST' }).catch(() => {})
}
