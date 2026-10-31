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
  /** Changes with the club's logo; null without one. */
  logo_version?: string | null
}

interface RawAuthResponse {
  mustChangePassword?: boolean
  member?: unknown
  requiresTenantSelection?: boolean
  tenants?: TenantChoice[]
  noTenant?: boolean
  tenant_slug?: string | null
  user?: { email: string; name: string }
  /** Two-factor is on: send a code with this token to /auth/login/mfa. */
  mfaRequired?: boolean
  mfaToken?: string
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

/** Second step of a sign-in with two-factor: an app or recovery code. */
export async function loginMfa(mfaToken: string, code: string): Promise<RawAuthResponse> {
  return apiFetch<RawAuthResponse>('/auth/login/mfa', {
    method: 'POST',
    body: JSON.stringify({ mfaToken, code }),
  })
}

export interface PasskeyInfo {
  id: number
  name: string
  createdAt: string | null
  lastUsedAt: string | null
}

export interface MfaStatus {
  /** A second step is on: the app, a passkey or both. */
  enabled: boolean
  totpEnabled: boolean
  enabledAt: string | null
  passkeys: PasskeyInfo[]
  /** False when the server does not know its SSO address. */
  passkeysAvailable: boolean
  recoveryCodesLeft: number
  /** Platform staff have to turn it on before manage › Platform works. */
  required: boolean
}

export interface TotpSetup {
  secret: string
  uri: string
  qrSvg: string
}

export async function getMfa(): Promise<MfaStatus> {
  return apiFetch<MfaStatus>('/account/mfa')
}

export async function startTotpSetup(currentPassword: string): Promise<TotpSetup> {
  return apiFetch<TotpSetup>('/account/mfa/totp/setup', {
    method: 'POST',
    body: JSON.stringify({ currentPassword }),
  })
}

export async function enableTotp(code: string): Promise<MfaStatus & { recoveryCodes: string[] }> {
  return apiFetch('/account/mfa/totp/enable', {
    method: 'POST',
    body: JSON.stringify({ code }),
  })
}

export async function disableTotp(currentPassword: string): Promise<MfaStatus> {
  return apiFetch<MfaStatus>('/account/mfa/totp/disable', {
    method: 'POST',
    body: JSON.stringify({ currentPassword }),
  })
}

interface PasskeyCeremony {
  options: Record<string, unknown>
  state: string
}

export async function passkeyRegisterOptions(currentPassword: string): Promise<PasskeyCeremony> {
  return apiFetch<PasskeyCeremony>('/account/passkeys/options', {
    method: 'POST',
    body: JSON.stringify({ currentPassword }),
  })
}

export async function addPasskey(
  state: string,
  credential: Record<string, unknown>,
  name: string,
): Promise<MfaStatus & { recoveryCodes: string[] }> {
  return apiFetch('/account/passkeys', {
    method: 'POST',
    body: JSON.stringify({ state, credential, name }),
  })
}

export async function removePasskey(id: number, currentPassword: string): Promise<MfaStatus> {
  return apiFetch<MfaStatus>(`/account/passkeys/${id}/delete`, {
    method: 'POST',
    body: JSON.stringify({ currentPassword }),
  })
}

/** Options for a passkey sign-in; with *mfaToken* only that account's passkeys. */
export async function passkeyLoginOptions(mfaToken?: string): Promise<PasskeyCeremony> {
  return apiFetch<PasskeyCeremony>('/auth/passkey/options', {
    method: 'POST',
    body: JSON.stringify(mfaToken ? { mfaToken } : {}),
  })
}

export async function passkeyLogin(
  state: string,
  credential: Record<string, unknown>,
  opts: { mfaToken?: string; keepSignedIn?: boolean } = {},
): Promise<RawAuthResponse> {
  return apiFetch<RawAuthResponse>('/auth/passkey/login', {
    method: 'POST',
    body: JSON.stringify({ state, credential, ...opts }),
  })
}

export async function renewRecoveryCodes(
  currentPassword: string,
): Promise<MfaStatus & { recoveryCodes: string[] }> {
  return apiFetch('/account/mfa/recovery-codes', {
    method: 'POST',
    body: JSON.stringify({ currentPassword }),
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
  /** False when the club takes new members by invite only. */
  acceptsRequests?: boolean
  /** Changes with the club's logo; null without one. */
  logoVersion?: string | null
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

/** Clubs the signed-in user asked to join that have not answered yet. */
export async function getMyJoinRequests(): Promise<{ requests: { slug: string; name: string }[] }> {
  return apiFetch('/system/join-requests/mine')
}

export interface ClubPage extends ClubListing {
  /** The membership tiers a person can ask for. */
  tiers: { id: number; name: string }[]
  canJoinDirectly: boolean
}

/** One club for its join page (the club app's /apply sends people here). */
export async function getClub(slug: string): Promise<ClubPage> {
  return apiFetch(`/system/clubs/${encodeURIComponent(slug)}`)
}

/** Join a club (platform managers) or ask to join it (everyone else). */
export async function joinClub(
  slug: string,
  wantsTierId?: number,
): Promise<{ status: 'joined' | 'requested'; club: { slug: string; name: string } }> {
  return apiFetch(`/system/clubs/${encodeURIComponent(slug)}/join`, {
    method: 'POST',
    body: JSON.stringify(wantsTierId ? { wantsTierId } : {}),
  })
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
  /** light, dark or auto (like the device). */
  theme: 'light' | 'dark' | 'auto'
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
  /** null: a sign-in to the account itself (this portal), not to a club. */
  club: { slug: string; name: string } | null
  current: boolean
}

export async function getSessions(): Promise<AccountSession[]> {
  return apiFetch<AccountSession[]>('/account/all-sessions')
}

export async function revokeSession(s: AccountSession): Promise<void> {
  const path = s.club
    ? `/account/all-sessions/${encodeURIComponent(s.club.slug)}/${s.id}`
    : `/account/account-sessions/${s.id}`
  await apiFetch(path, { method: 'DELETE' })
}

export async function revokeOtherSessions(): Promise<{ revoked: number }> {
  return apiFetch('/account/all-sessions/revoke-all', { method: 'POST' })
}

/** A club's invite, as the signed-in person sees it before accepting. */
export interface ClubInvite {
  club: { slug: string; name: string }
  /** The address the invite was sent to; only that account can accept. */
  email: string
  invitedBy: string
  emailMatches: boolean
  membership: 'member' | 'pending' | null
}

export async function lookupInvite(token: string): Promise<ClubInvite> {
  return apiFetch('/system/invites/lookup', {
    method: 'POST',
    body: JSON.stringify({ token }),
  })
}

export async function acceptInvite(
  token: string,
): Promise<{ status: 'joined'; club: { slug: string; name: string } }> {
  return apiFetch('/system/invites/accept', {
    method: 'POST',
    body: JSON.stringify({ token }),
  })
}

/** An open invite to the signed-in account's confirmed address. */
export interface MyInvite {
  id: number
  club: { slug: string; name: string }
  invitedBy: string
  expiresAt: string
}

/** Open invites to this account, for when the link got lost on the way. */
export async function getMyInvites(): Promise<{ invites: MyInvite[] }> {
  return apiFetch('/system/invites/mine')
}

export async function acceptMyInvite(
  id: number,
): Promise<{ status: 'joined'; club: { slug: string; name: string } }> {
  return apiFetch(`/system/invites/${id}/accept`, { method: 'POST' })
}

/** One of the person's notifications, from one of their clubs. */
export interface AccountNotification {
  id: number
  kind: 'info' | 'success' | 'warning' | 'member'
  title: string
  msg: string
  time: string
  read: boolean
  /** Club app path it is about, e.g. "/app/operations/posts/3". */
  link: string | null
  club: { slug: string | null; name: string | null }
}

export async function getNotifications(): Promise<{
  data: AccountNotification[]
  meta: { unread: number }
}> {
  return apiFetch('/account/notifications')
}

const notificationPath = (n: AccountNotification) =>
  `/account/notifications/${encodeURIComponent(n.club.slug ?? '-')}/${n.id}`

export async function markNotificationRead(n: AccountNotification): Promise<void> {
  await apiFetch(`${notificationPath(n)}/read`, { method: 'PATCH' })
}

export async function deleteNotification(n: AccountNotification): Promise<void> {
  await apiFetch(notificationPath(n), { method: 'DELETE' })
}

export async function markAllNotificationsRead(): Promise<void> {
  await apiFetch('/account/notifications/read-all', { method: 'POST' })
}

/** Deletes the person's notifications in all clubs; ``readOnly`` keeps unread ones. */
export async function clearNotifications(readOnly = false): Promise<void> {
  await apiFetch(`/account/notifications${readOnly ? '?read=1' : ''}`, { method: 'DELETE' })
}

/** An outside account (Discord) linked to this account. */
export interface LinkedAccount {
  provider: string
  externalId: string
  username: string
  linkedAt: string | null
}

export interface LinkedAccounts {
  providers: { code: string; name: string; available: boolean }[]
  accounts: LinkedAccount[]
}

export async function getLinkedAccounts(): Promise<LinkedAccounts> {
  return apiFetch('/account/linked-accounts/')
}

/** Where to send the browser to sign in on the outside service. */
export async function startLinkAccount(provider: string): Promise<{ url: string }> {
  return apiFetch(`/account/linked-accounts/${provider}/start`, { method: 'POST' })
}

export async function unlinkAccount(provider: string): Promise<void> {
  await apiFetch(`/account/linked-accounts/${provider}`, { method: 'DELETE' })
}
