import { apiFetch } from '@hubra/api-client'

export interface PermissionsResponse {
  is_admin: boolean
  is_superadmin: boolean
  permissions: string[]
  global_permissions?: string[]
  global_roles?: string[]
  /** Club the session is scoped to (set after login or switch-tenant). */
  tenant_slug?: string | null
  impersonation: {
    is_impersonating: boolean
    impersonator_id: number
    tenant_slug: string
    reason: string | null
    expires_at: string | null
    restricted_actions: string[]
  } | null
}

// Shape of AuthService.find_user_tenants on the backend.
export interface TenantChoice {
  tenant_id: number
  tenant_slug: string
  tenant_name: string
  member_id: number | null
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

export async function logout(): Promise<void> {
  await apiFetch('/auth/logout', { method: 'POST' }).catch(() => {})
}

/** The clubs the signed-in user belongs to. */
export async function getMyTenants(): Promise<{ tenants: TenantChoice[] }> {
  return apiFetch<{ tenants: TenantChoice[] }>('/account/my-tenants')
}

export interface ClubListing {
  slug: string
  name: string
  /** 'member', 'pending' (asked to join, not yet approved) or null. */
  membership: 'member' | 'pending' | null
}

/**
 * Active clubs matching `search`. Ordinary users get results only for a
 * search of 2+ characters; platform managers see every club.
 */
export async function findClubs(
  search: string,
): Promise<{ clubs: ClubListing[]; canJoinDirectly: boolean }> {
  const qs = search ? `?search=${encodeURIComponent(search)}` : ''
  return apiFetch(`/system/clubs${qs}`)
}

/** Join a club (platform managers) or ask to join it (everyone else). */
export async function joinClub(
  slug: string,
): Promise<{ status: 'joined' | 'requested'; club: { slug: string; name: string } }> {
  return apiFetch(`/system/clubs/${encodeURIComponent(slug)}/join`, { method: 'POST' })
}
