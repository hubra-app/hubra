import { apiFetch } from '@hubra/api-client'

export interface ClubSettings {
  club_name?: string
  /** Members ask to leave and an admin approves (off: they leave at once). */
  leave_requires_approval?: boolean
  /** Notice period from the statutes, in months (0: none). */
  leave_notice_months?: number | null
  /** Leaving takes effect at the end of this period. */
  leave_at?: 'any' | 'month_end' | 'quarter_end' | 'half_year_end' | 'year_end' | null
  /** Off: the club takes new members by invite only. */
  join_requests_open?: boolean
  /** The club's public page on the join portal (off by default). */
  public_page?: boolean
  /** The club's own website, shown on the public page. */
  website?: string | null
  /** How many days an invite link works (1–60). */
  invite_valid_days?: number
  /** Delete former members this many years after they left (1–30); null: off. */
  former_member_retention_years?: number | null
  /** Who needs two-factor sign-in to open the club. */
  mfa_required?: 'off' | 'admins' | 'all'
  club_description?: string
  /** A base64 image data URL; null removes it on save. */
  logo?: string | null
  primary_color?: string | null
  secondary_color?: string | null
  accent_color?: string | null
  timezone?: string
  locale?: string
  date_format?: string
  member_directory_visible?: boolean
  public_group_listing?: boolean
  announcement_banner_text?: string
  announcement_banner_active?: boolean
}

export async function getClubSettings(): Promise<ClubSettings> {
  const data = await apiFetch<{ settings: ClubSettings }>('/app/admin/club-settings')
  return data.settings
}

/** How many members (and admins) still sign in without two-factor. */
export interface ClubMfaOverview {
  membersWithout: number
  adminsWithout: number
}

export async function getClubMfaOverview(): Promise<ClubMfaOverview> {
  const data = await apiFetch<{ mfa: ClubMfaOverview }>('/app/admin/club-settings')
  return data.mfa
}

export async function updateClubSettings(
  patch: Partial<ClubSettings>,
): Promise<ClubSettings> {
  const data = await apiFetch<{ settings: ClubSettings }>('/app/admin/club-settings', {
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
  last_checked_at: string | null
  txt_record: TxtRecord | null
  /** Serving visitors: null (not verified), off, pending, ready or failed. */
  serving_status?: 'off' | 'pending' | 'ready' | 'failed' | null
  serving_since?: string | null
  /** Where to point the domain (CNAME), while the platform serves club domains. */
  cname_target?: string | null
  created_at: string | null
  updated_at: string | null
}

export interface TxtRecord {
  name: string
  value: string
  instructions: string
}

export async function listDomains(): Promise<Domain[]> {
  const data = await apiFetch<{ domains: Domain[] }>('/app/admin/domains')
  return data.domains
}

export async function addDomain(
  domain: string,
): Promise<{ domain: Domain; txt_record: TxtRecord }> {
  return apiFetch('/app/admin/domains', {
    method: 'POST',
    body: JSON.stringify({ domain }),
  })
}

export async function verifyDomain(
  id: number,
): Promise<{ domain: Domain; verified: boolean; error: string | null }> {
  return apiFetch(`/app/admin/domains/${id}/verify`, { method: 'POST' })
}

export async function removeDomain(id: number): Promise<void> {
  await apiFetch(`/app/admin/domains/${id}`, { method: 'DELETE' })
}

export async function setPrimaryDomain(id: number): Promise<{ domain: Domain }> {
  return apiFetch(`/app/admin/domains/${id}/primary`, { method: 'PATCH' })
}

/** The account and address the club's QR invoices are paid to. */
export interface BankSettings {
  iban: string
  street: string
  houseNo: string
  postalCode: string
  city: string
  country: string
  /** A QR-IBAN: invoices get a QR reference the bank import matches. */
  isQrIban: boolean
  /** IBAN, postal code and city are set, so invoices can carry a QR bill. */
  complete: boolean
}

export type BankSettingsInput = Omit<BankSettings, 'isQrIban' | 'complete'>

export function getBankSettings(): Promise<BankSettings> {
  return apiFetch<BankSettings>('/app/admin/bank-settings')
}

export function updateBankSettings(input: BankSettingsInput): Promise<BankSettings> {
  return apiFetch<BankSettings>('/app/admin/bank-settings', {
    method: 'PUT',
    body: JSON.stringify(input),
  })
}

// ── Club backup key ─────────────────────────────────────────────────────────
// Only the public key (age1…) is ever sent; the private key stays with the club.

export interface BackupKeyState {
  public_key: string | null
  set_at: string | null
  set_by: string | null
  /** False while the server still makes the older passphrase backups. */
  backups_use_key: boolean
  /** The newest club backup encrypted to this key, if any. */
  last_backup_with_key: string | null
  /** Only the club's key opens new backups; Hubra cannot restore them. */
  club_only: boolean
}

export function getBackupKey(): Promise<BackupKeyState> {
  return apiFetch<BackupKeyState>('/app/admin/backup-key')
}

export function setBackupKey(publicKey: string): Promise<BackupKeyState> {
  return apiFetch<BackupKeyState>('/app/admin/backup-key', {
    method: 'PUT',
    body: JSON.stringify({ public_key: publicKey }),
  })
}

export function removeBackupKey(): Promise<BackupKeyState> {
  return apiFetch<BackupKeyState>('/app/admin/backup-key', { method: 'DELETE' })
}

/** Turning "only our key" on needs the club's slug as confirmation. */
export function setBackupKeyClubOnly(clubOnly: boolean, confirm?: string): Promise<BackupKeyState> {
  return apiFetch<BackupKeyState>('/app/admin/backup-key', {
    method: 'PATCH',
    body: JSON.stringify({ club_only: clubOnly, confirm }),
  })
}
