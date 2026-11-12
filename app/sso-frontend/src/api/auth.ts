import { apiFetch } from '@hubra/api-client'
import { posterSource } from '@/posterSource'

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

/** The browser's time zone: with the language and network it tells a
 * browser that lost its cookies from a new device (no sign-in alert). */
function timeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || ''
  } catch {
    return ''
  }
}

export async function login(
  email: string,
  password: string,
  keepSignedIn = true,
): Promise<RawAuthResponse> {
  return apiFetch<RawAuthResponse>('/global/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password, keepSignedIn, timeZone: timeZone() }),
  })
}

/** Second step of a sign-in with two-factor: an app or recovery code. */
export async function loginMfa(mfaToken: string, code: string): Promise<RawAuthResponse> {
  return apiFetch<RawAuthResponse>('/global/auth/login/mfa', {
    method: 'POST',
    body: JSON.stringify({ mfaToken, code, timeZone: timeZone() }),
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
  /** The person's clubs that ask them for two-factor sign-in. */
  clubsRequiring: { slug: string; name: string }[]
}

export interface TotpSetup {
  secret: string
  uri: string
  qrSvg: string
}

export async function getMfa(): Promise<MfaStatus> {
  return apiFetch<MfaStatus>('/global/account/mfa')
}

export async function startTotpSetup(currentPassword: string): Promise<TotpSetup> {
  return apiFetch<TotpSetup>('/global/account/mfa/totp/setup', {
    method: 'POST',
    body: JSON.stringify({ currentPassword }),
  })
}

export async function enableTotp(code: string): Promise<MfaStatus & { recoveryCodes: string[] }> {
  return apiFetch('/global/account/mfa/totp/enable', {
    method: 'POST',
    body: JSON.stringify({ code }),
  })
}

export async function disableTotp(currentPassword: string): Promise<MfaStatus> {
  return apiFetch<MfaStatus>('/global/account/mfa/totp/disable', {
    method: 'POST',
    body: JSON.stringify({ currentPassword }),
  })
}

interface PasskeyCeremony {
  options: Record<string, unknown>
  state: string
}

export async function passkeyRegisterOptions(currentPassword: string): Promise<PasskeyCeremony> {
  return apiFetch<PasskeyCeremony>('/global/account/passkeys/options', {
    method: 'POST',
    body: JSON.stringify({ currentPassword }),
  })
}

export async function addPasskey(
  state: string,
  credential: Record<string, unknown>,
  name: string,
): Promise<MfaStatus & { recoveryCodes: string[] }> {
  return apiFetch('/global/account/passkeys', {
    method: 'POST',
    body: JSON.stringify({ state, credential, name }),
  })
}

export async function removePasskey(id: number, currentPassword: string): Promise<MfaStatus> {
  return apiFetch<MfaStatus>(`/global/account/passkeys/${id}/delete`, {
    method: 'POST',
    body: JSON.stringify({ currentPassword }),
  })
}

/** Options for a passkey sign-in; with *mfaToken* only that account's passkeys. */
export async function passkeyLoginOptions(mfaToken?: string): Promise<PasskeyCeremony> {
  return apiFetch<PasskeyCeremony>('/global/auth/passkey/options', {
    method: 'POST',
    body: JSON.stringify(mfaToken ? { mfaToken } : {}),
  })
}

export async function passkeyLogin(
  state: string,
  credential: Record<string, unknown>,
  opts: { mfaToken?: string; keepSignedIn?: boolean } = {},
): Promise<RawAuthResponse> {
  return apiFetch<RawAuthResponse>('/global/auth/passkey/login', {
    method: 'POST',
    body: JSON.stringify({ state, credential, ...opts, timeZone: timeZone() }),
  })
}

export async function renewRecoveryCodes(
  currentPassword: string,
): Promise<MfaStatus & { recoveryCodes: string[] }> {
  return apiFetch('/global/account/mfa/recovery-codes', {
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
  return apiFetch<RawAuthResponse>('/global/auth/signup', {
    method: 'POST',
    body: JSON.stringify({ name, email, password, keepSignedIn }),
  })
}

export async function switchTenant(
  tenantSlug: string,
): Promise<RawAuthResponse> {
  return apiFetch<RawAuthResponse>('/global/auth/switch-tenant', {
    method: 'POST',
    body: JSON.stringify({ tenantSlug }),
  })
}

export async function getMyPermissions(
  signal?: AbortSignal,
): Promise<PermissionsResponse> {
  return apiFetch<PermissionsResponse>('/global/account/permissions', { signal })
}

export async function forgotPassword(email: string): Promise<void> {
  await apiFetch('/global/auth/forgot-password', {
    method: 'POST',
    body: JSON.stringify({ email }),
  })
}

export async function resetPassword(
  token: string,
  password: string,
): Promise<void> {
  await apiFetch('/global/auth/reset-password', {
    method: 'POST',
    body: JSON.stringify({ token, password }),
  })
}

export async function verifyEmail(token: string): Promise<{ ok: boolean; verified: boolean }> {
  return apiFetch(`/global/account/verify-email`, {
    method: 'POST',
    body: JSON.stringify({ token }),
  })
}

export async function logout(): Promise<void> {
  await apiFetch('/global/auth/logout', { method: 'POST' }).catch(() => {})
}

/** The clubs the signed-in user belongs to. */
export async function getMyTenants(): Promise<{ tenants: TenantChoice[] }> {
  return apiFetch<{ tenants: TenantChoice[] }>('/global/account/my-tenants')
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
  return apiFetch(`/global/clubs${qs}`)
}

/** Clubs the signed-in user asked to join that have not answered yet. */
export async function getMyJoinRequests(): Promise<{ requests: { slug: string; name: string }[] }> {
  return apiFetch('/global/join-requests/mine')
}

export interface ClubPage extends ClubListing {
  /** The membership tiers a person can ask for. */
  tiers: { id: number; name: string }[]
  canJoinDirectly: boolean
}

/** One club for its join page (the club app's /apply sends people here). */
export async function getClub(slug: string): Promise<ClubPage> {
  posterSource(slug) // keep a poster's ?src= for the request to join
  return apiFetch(`/global/clubs/${encodeURIComponent(slug)}`)
}

/** Join a club (platform managers) or ask to join it (everyone else). */
export async function joinClub(
  slug: string,
  wantsTierId?: number,
): Promise<{ status: 'joined' | 'requested'; club: { slug: string; name: string } }> {
  // The join poster the person came from, if any.
  const source = posterSource(slug)
  return apiFetch(`/global/clubs/${encodeURIComponent(slug)}/join`, {
    method: 'POST',
    body: JSON.stringify({ ...(wantsTierId ? { wantsTierId } : {}), ...(source ? { source } : {}) }),
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
  return apiFetch('/global/tenant-requests/mine')
}

/** Ask the platform for a new club; staff review it. */
export async function requestClub(data: {
  name: string
  slug: string
}): Promise<{ request: ClubRequest }> {
  return apiFetch('/platform/system/tenant-requests', {
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
  return apiFetch<VerificationStatus>('/global/account/email-verification', { signal })
}

export async function sendVerificationEmail(): Promise<void> {
  await apiFetch('/global/account/request-email-verification', { method: 'POST' })
}

/** New login and private address; a new link goes out. */
export async function changeEmail(
  email: string,
  currentPassword: string,
): Promise<VerificationStatus> {
  return apiFetch<VerificationStatus>('/global/account/email', {
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
  /** female, male, diverse, or null when not given. */
  gender: 'female' | 'male' | 'diverse' | null
  /** YYYY-MM-DD */
  birthday: string | null
  phone: string | null
  mobile: string | null
  address: {
    street: string | null
    houseNo: string | null
    postalCode: string | null
    city: string | null
    /** Two-letter code, e.g. CH. */
    country: string
  }
  language: string
  /** light, dark or auto (like the device). */
  theme: 'light' | 'dark' | 'auto'
  isSuperadmin: boolean
  mustChangePassword: boolean
}

export type ProfileUpdate = Partial<
  Pick<
    Profile,
    | 'name'
    | 'firstName'
    | 'lastName'
    | 'avatarColor'
    | 'profileNote'
    | 'language'
    | 'gender'
    | 'birthday'
    | 'phone'
    | 'mobile'
  > & { address: Partial<Profile['address']> }
>

export async function getProfile(): Promise<Profile> {
  return apiFetch<Profile>('/global/account/profile')
}

export async function updateProfile(updates: ProfileUpdate): Promise<Profile> {
  return apiFetch<Profile>('/global/account/profile', {
    method: 'PATCH',
    body: JSON.stringify(updates),
  })
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  await apiFetch('/global/account/password', {
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
  /** The clubs opened from this sign-in; signing it out ends them too. */
  clubs?: { slug: string; name: string }[]
  current: boolean
}

export async function getSessions(): Promise<AccountSession[]> {
  return apiFetch<AccountSession[]>('/global/account/all-sessions')
}

export async function revokeSession(s: AccountSession): Promise<void> {
  const path = s.club
    ? `/global/account/all-sessions/${encodeURIComponent(s.club.slug)}/${s.id}`
    : `/global/account/account-sessions/${s.id}`
  await apiFetch(path, { method: 'DELETE' })
}

export async function revokeOtherSessions(): Promise<{ revoked: number }> {
  return apiFetch('/global/account/all-sessions/revoke-all', { method: 'POST' })
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
  return apiFetch('/global/invites/lookup', {
    method: 'POST',
    body: JSON.stringify({ token }),
  })
}

export async function acceptInvite(
  token: string,
): Promise<{ status: 'joined'; club: { slug: string; name: string } }> {
  return apiFetch('/global/invites/accept', {
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
  return apiFetch('/global/invites/mine')
}

export async function acceptMyInvite(
  id: number,
): Promise<{ status: 'joined'; club: { slug: string; name: string } }> {
  return apiFetch(`/global/invites/${id}/accept`, { method: 'POST' })
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
  return apiFetch('/global/account/notifications')
}

const notificationPath = (n: AccountNotification) =>
  `/global/account/notifications/${encodeURIComponent(n.club.slug ?? '-')}/${n.id}`

export async function markNotificationRead(n: AccountNotification): Promise<void> {
  await apiFetch(`${notificationPath(n)}/read`, { method: 'PATCH' })
}

export async function deleteNotification(n: AccountNotification): Promise<void> {
  await apiFetch(notificationPath(n), { method: 'DELETE' })
}

export async function markAllNotificationsRead(): Promise<void> {
  await apiFetch('/global/account/notifications/read-all', { method: 'POST' })
}

/** Deletes the person's notifications in all clubs; ``readOnly`` keeps unread ones. */
export async function clearNotifications(readOnly = false): Promise<void> {
  await apiFetch(`/global/account/notifications${readOnly ? '?read=1' : ''}`, { method: 'DELETE' })
}

/** An outside account (Discord) linked to this account. */
export interface LinkedAccount {
  provider: string
  externalId: string
  username: string
  linkedAt: string | null
  /** Discord: Linked Roles allowed */
  linkedRoles?: boolean
}

export interface LinkedAccounts {
  providers: { code: string; name: string; available: boolean }[]
  accounts: LinkedAccount[]
}

export async function getLinkedAccounts(): Promise<LinkedAccounts> {
  return apiFetch('/global/account/linked-accounts/')
}

/** Where to send the browser to sign in on the outside service. */
export async function startLinkAccount(provider: string): Promise<{ url: string }> {
  return apiFetch(`/global/account/linked-accounts/${provider}/start`, { method: 'POST' })
}

export async function unlinkAccount(provider: string): Promise<void> {
  await apiFetch(`/global/account/linked-accounts/${provider}`, { method: 'DELETE' })
}

// ── Confirming a platform action (manage's step-up) ─────────────────────────

export interface StepUpStatus {
  /** Until when this sign-in counts as confirmed, or null. */
  sudoUntil: string | null
  /** The account has a passkey (and passkeys work here). */
  passkey: boolean
  /** The account has the authenticator app on. */
  code: boolean
}

export async function getStepUpStatus(signal?: AbortSignal): Promise<StepUpStatus> {
  return apiFetch<StepUpStatus>('/global/account/step-up', { signal })
}

/** A challenge tied to this account and this sign-in. */
export async function stepUpPasskeyOptions(): Promise<PasskeyCeremony> {
  return apiFetch<PasskeyCeremony>('/global/account/step-up/passkey/options', {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

export async function stepUpWithPasskey(
  state: string,
  credential: Record<string, unknown>,
): Promise<{ sudoUntil: string }> {
  return apiFetch('/global/account/step-up/passkey', {
    method: 'POST',
    body: JSON.stringify({ state, credential }),
  })
}

// ── Apps (OAuth, docs/oauth.md) ─────────────────────────────────────────────

export interface OAuthApp {
  name: string
  description: string
  clientUri: string | null
  /** Registered by Hubra's admins; false for an app that registered itself. */
  verified: boolean
  /** registered (Hubra), club (a club's own website or forum), dynamic. */
  kind?: 'registered' | 'club' | 'dynamic'
  /** Where the app gets the person back to. */
  redirectHost: string | null
}

export interface OAuthProblem {
  error: string
  message: string
  /** Set when the error may go back to the app. */
  redirect?: string
}

export interface OAuthClubChoice {
  slug: string
  name: string
  isAdmin: boolean
  available: boolean
  reason: 'MEMBERS_OFF' | 'AI_OFF' | 'MFA_SETUP_FIRST' | null
}

export interface OAuthConsent {
  problem?: OAuthProblem
  client: OAuthApp
  /** access: the app reads Hubra for the person; identity: Sign in with
   * Hubra only (OpenID Connect, docs/oidc.md). */
  mode: 'access' | 'identity'
  /** What the app wants to use: the Hubra API or the Claude connector. */
  resource: 'api' | 'mcp' | null
  scopes: ('read' | 'write')[]
  /** OpenID Connect: openid, profile, email, club. */
  oidc: string[]
  /** Allowed before with the same details: answered at once. */
  remembered: boolean
  /** A club's own sign-in app: its club, and whether the person may sign in. */
  club: { slug: string; name: string; available: boolean; reason: string | null } | null
  user: { name: string; email: string }
  clubs: OAuthClubChoice[]
  platform: { available: boolean; reason: string | null } | null
  days: { club: number[]; platform: number[]; defaultClub: number; defaultPlatform: number }
}

export async function getOAuthConsent(params: Record<string, string>): Promise<OAuthConsent> {
  return apiFetch<OAuthConsent>(`/global/oauth/authorize?${new URLSearchParams(params)}`)
}

export async function answerOAuthConsent(body: {
  params: Record<string, string>
  allow: boolean
  club?: string
  platform?: boolean
  days?: number
}): Promise<{ redirect?: string; problem?: OAuthProblem }> {
  return apiFetch('/global/oauth/authorize', { method: 'POST', body: JSON.stringify(body) })
}

export interface OAuthGrant {
  id: number
  kind: 'member' | 'platform' | 'identity'
  /** Sign in with Hubra only: the app knows who you are, reads nothing. */
  signIn?: boolean
  /** What a sign-in shares: profile, email, club. */
  claims?: string[]
  app: OAuthApp | null
  club: { slug: string; name: string } | null
  resourceKind: 'api' | 'mcp' | null
  canWrite: boolean
  createdAt: string | null
  expiresAt: string | null
  lastUsedAt: string | null
}

export async function getOAuthGrants(): Promise<{ items: OAuthGrant[] }> {
  return apiFetch('/global/oauth/grants')
}

export async function endOAuthGrant(id: number): Promise<void> {
  await apiFetch(`/global/oauth/grants/${id}`, { method: 'DELETE' })
}

/** Discord direct messages to the account outside a club. */
export interface DiscordDms {
  /** The platform has a bot and the account linked Discord. */
  available: boolean
  /** Mutes every Hubra direct message, the clubs' ones too. */
  muted: boolean
  kinds: { sign_in: boolean; requests: boolean }
}

export async function getDiscordDms(): Promise<DiscordDms> {
  return apiFetch<DiscordDms>('/global/account/discord-dms')
}

export async function setDiscordDms(
  change: { muted?: boolean; kinds?: Partial<DiscordDms['kinds']> },
): Promise<DiscordDms> {
  return apiFetch<DiscordDms>('/global/account/discord-dms', {
    method: 'PUT',
    body: JSON.stringify(change),
  })
}

/** "This wasn't me" from a new-device alert: ends every session. */
export async function notMe(token: string): Promise<{ ok: boolean; ended: number }> {
  return apiFetch('/global/auth/not-me', {
    method: 'POST',
    body: JSON.stringify({ token }),
  })
}

// ── What the person wants to be notified about, per club ────────────────────

export type NotifyTopic =
  | 'posts'
  | 'events'
  | 'polls'
  | 'event_reminders'
  | 'poll_reminders'
  | 'my_events'
  | 'bookings'
  | 'waitlist'
  | 'my_polls'
  | 'tasks'
  | 'requests'
  | 'payments'
  | 'membership'
  | 'qualifications'
  | 'digest'

/** bell, push, mail, or a connected app's key (e.g. discord). */
export type NotifyChannel = string

export interface ClubNotifySettings {
  club: { slug: string | null; name: string | null; logoVersion?: string | null }
  /** Per topic and channel; a channel the topic does not have is missing. */
  topics: Partial<Record<NotifyTopic, Record<NotifyChannel, boolean>>>
  /** Connected apps that deliver notifications in this club. */
  apps: { key: string; name: string }[]
  digest: boolean
  /** The account's "mute all direct messages" (every club). */
  muted: boolean
}

export async function getNotifySettings(): Promise<{ data: ClubNotifySettings[] }> {
  return apiFetch('/global/account/notifications/settings')
}

export async function setNotifySettings(
  slug: string | null,
  change: Partial<Record<NotifyTopic, Record<NotifyChannel, boolean>>> | { muted: boolean },
): Promise<ClubNotifySettings> {
  return apiFetch(`/global/account/notifications/settings/${encodeURIComponent(slug ?? '-')}`, {
    method: 'PUT',
    body: JSON.stringify(change),
  })
}

// ── The member badge ─────────────────────────────────────────────────────────

export interface BadgeMembership {
  club: { slug: string; name: string; logoVersion?: string | null }
  tier: { name: string; color: string | null } | null
  /** regular, honorary, passive or trial. */
  membershipType: string
  /** active, trial, inactive or suspended. */
  status: string
  joined: string | null
  until: string | null
}

/** One badge per person: the number is the same in every club. */
export interface MemberBadge {
  code: string
  /** The badge number as a QR code (SVG markup). */
  qrSvg: string
  name: string
  avatarColor: string
  since: string | null
  memberships: BadgeMembership[]
  /** The platform has Google Wallet set up: offer "Add to Google Wallet". */
  googleWallet?: boolean
}

export async function getBadge(): Promise<MemberBadge> {
  return apiFetch<MemberBadge>('/global/account/badge')
}

/** Writes the badge's pass to Google Wallet; the link saves it on the phone. */
export async function addBadgeToGoogleWallet(): Promise<{ url: string }> {
  return apiFetch<{ url: string }>('/global/account/badge/google-wallet', { method: 'POST' })
}

// ── One calendar for every club ─────────────────────────────────────────────

/** The personal calendar URLs: every club's events, or those signed up for. */
export interface AccountCalendar {
  all: string
  mine: string
}

export async function getAccountCalendar(): Promise<AccountCalendar> {
  return apiFetch<AccountCalendar>('/global/account/calendar')
}

/** New calendar URLs; the old ones stop working. */
export async function renewAccountCalendar(): Promise<AccountCalendar> {
  return apiFetch<AccountCalendar>('/global/account/calendar/renew', { method: 'POST' })
}
