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
  /** 'owner' or 'admin' where the user runs the club, else null. */
  admin_level?: 'owner' | 'admin' | null
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

export async function verifyEmail(token: string): Promise<{ ok: boolean; verified: boolean }> {
  return apiFetch(`/account/verify-email`, {
    method: 'POST',
    body: JSON.stringify({ token }),
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

export interface ClubRequest {
  id: number
  name: string
  slug: string
  plan: string
  /** 'pending', 'approved' or 'rejected'. */
  status: string
  admin_note: string | null
  created_at: string | null
}

/** The new clubs the signed-in user asked for, newest first. */
export async function getMyClubRequests(): Promise<{ requests: ClubRequest[] }> {
  return apiFetch('/system/tenant-requests/mine')
}

/** Ask the platform for a new club; staff review it. */
export async function requestClub(data: {
  name: string
  slug: string
}): Promise<{ request: ClubRequest }> {
  return apiFetch('/system/tenant-requests', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}
// ── Email verification: the step after sign-in ───────────────────────────────

export interface VerificationStatus {
  email: string
  verified: boolean
  /** True while the person still has to confirm their address. */
  required: boolean
  /** False when the platform can't send mail; then nobody has to verify. */
  mailConfigured: boolean
  /** When the open link was sent, or null if none is open. */
  sentAt: string | null
}

export async function getVerificationStatus(signal?: AbortSignal): Promise<VerificationStatus> {
  return apiFetch<VerificationStatus>('/account/email-verification', { signal })
}

export async function sendVerificationEmail(): Promise<void> {
  await apiFetch('/account/request-email-verification', { method: 'POST' })
}

/** New login and private address; a new link goes out. */
export async function changeEmail(
  email: string,
  currentPassword: string,
): Promise<VerificationStatus> {
  return apiFetch<VerificationStatus>('/account/email', {
    method: 'PATCH',
    body: JSON.stringify({ email, currentPassword }),
  })
}

// ── Account ──────────────────────────────────────────────────────────────────

export interface Profile {
  id: number
  email: string
  emailVerified: boolean
  name: string
  firstName: string
  lastName: string
  avatarColor: string
  profileNote: string | null
  language: string
  isSuperadmin: boolean
  mustChangePassword: boolean
}

export type ProfileUpdate = Partial<
  Pick<Profile, 'name' | 'avatarColor' | 'profileNote' | 'language'>
>

export async function getProfile(): Promise<Profile> {
  return apiFetch<Profile>('/account/profile')
}

export async function updateProfile(updates: ProfileUpdate): Promise<Profile> {
  return apiFetch<Profile>('/account/profile', {
    method: 'PATCH',
    body: JSON.stringify(updates),
  })
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  await apiFetch('/account/password', {
    method: 'POST',
    body: JSON.stringify({ currentPassword, newPassword }),
  })
}

export interface AccountSession {
  id: number
  deviceName: string | null
  browserFamily: string
  platform: string
  ipAddress: string
  createdAt: string | null
  lastActiveAt: string | null
  club: { slug: string; name: string }
  current: boolean
}

export async function getSessions(): Promise<AccountSession[]> {
  return apiFetch<AccountSession[]>('/account/all-sessions')
}

export async function revokeSession(clubSlug: string, id: number): Promise<void> {
  await apiFetch(`/account/all-sessions/${encodeURIComponent(clubSlug)}/${id}`, {
    method: 'DELETE',
  })
}

export async function revokeOtherSessions(): Promise<{ revoked: number }> {
  return apiFetch('/account/all-sessions/revoke-all', { method: 'POST' })
}
