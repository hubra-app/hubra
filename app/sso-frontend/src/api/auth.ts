import { apiFetch } from '@vollbuild/api-client'

export interface PermissionsResponse {
  is_admin: boolean
  is_superadmin: boolean
  permissions: string[]
  global_permissions?: string[]
  global_roles?: string[]
  impersonation: {
    is_impersonating: boolean
    impersonator_id: number
    tenant_slug: string
    reason: string | null
    expires_at: string | null
    restricted_actions: string[]
  } | null
}

export interface TenantChoice {
  slug: string
  name: string
  plan: string
  status: string
}

interface RawAuthResponse {
  mustChangePassword?: boolean
  member?: unknown
  requiresTenantSelection?: boolean
  tenants?: TenantChoice[]
  noTenant?: boolean
  tenant_slug?: string | null
  user?: { email: string; name: string }
}

export async function login(
  email: string,
  password: string,
  keepSignedIn = true,
): Promise<RawAuthResponse> {
  return apiFetch<RawAuthResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password, keepSignedIn }),
  })
}

export async function signup(
  name: string,
  email: string,
  password: string,
  keepSignedIn = true,
): Promise<RawAuthResponse> {
  return apiFetch<RawAuthResponse>('/auth/signup', {
    method: 'POST',
    body: JSON.stringify({ name, email, password, keepSignedIn }),
  })
}

export async function switchTenant(
  tenantSlug: string,
): Promise<RawAuthResponse> {
  return apiFetch<RawAuthResponse>('/auth/switch-tenant', {
    method: 'POST',
    body: JSON.stringify({ tenantSlug }),
  })
}

export async function logout(): Promise<void> {
  await apiFetch('/auth/logout', { method: 'POST' }).catch(() => {})
}

export async function getMyPermissions(
  signal?: AbortSignal,
): Promise<PermissionsResponse> {
  return apiFetch<PermissionsResponse>('/account/permissions', { signal })
}

export async function forgotPassword(email: string): Promise<void> {
  await apiFetch('/auth/forgot-password', {
    method: 'POST',
    body: JSON.stringify({ email }),
  })
}

export async function resetPassword(
  token: string,
  password: string,
): Promise<void> {
  await apiFetch('/auth/reset-password', {
    method: 'POST',
    body: JSON.stringify({ token, password }),
  })
}

export async function verifyEmail(
  token: string,
  signal?: AbortSignal,
): Promise<{ ok: boolean; verified: boolean }> {
  return apiFetch(`/account/verify-email`, {
    method: 'POST',
    body: JSON.stringify({ token }),
    signal,
  })
}
