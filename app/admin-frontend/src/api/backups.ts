import { apiFetch } from '@hubra/api-client'

// Backups are the platform's (backups.manage): one global backup of the
// public schema, and one per club that can be restored on its own.
const B = '/manager/platform/backups'

export interface BackupRecord {
  id: string
  created_at: string
  type: string
  status: string
  size_bytes: number | null
  s3_key: string | null
  checksum: string | null
  verified_at: string | null
  verified_ok: boolean | null
  verify_error: string | null
  error_message: string | null
  triggered_by: string | null
  table_count: number | null
  scope: 'global' | 'club'
  tenant_id: number | null
  tenant_slug: string | null
  restored_at: string | null
  restore_error: string | null
  safety_schema: string | null
  /** Encrypted to the backup public key: opening it needs the private key. */
  needs_private_key: boolean
}

export interface BackupConfigStatus {
  s3_configured: boolean
  s3_reachable: boolean
  s3_error: string | null
  encryption_configured: boolean
  /** 'age': public-key backups; 'gpg': the older passphrase. */
  encryption_mode: 'age' | 'gpg' | null
  private_key_on_server: boolean
  endpoint: string
  bucket: string
  region: string
}

export async function listBackups(): Promise<BackupRecord[]> {
  return apiFetch<BackupRecord[]>(`${B}/`)
}

/** Without a club, the global backup (public schema) is made. */
export async function createBackup(
  tenantId?: number,
): Promise<{ task_id: string; status: string }> {
  return apiFetch<{ task_id: string; status: string }>(`${B}/`, {
    method: 'POST',
    body: JSON.stringify(tenantId ? { tenant_id: tenantId } : {}),
  })
}

/**
 * Restore one club from a club backup; `confirm` is the club's address.
 * `privateKey` opens a backup encrypted to the backup public key; the
 * server uses it for this restore only and never stores it.
 */
export async function restoreBackup(
  id: string,
  confirm: string,
  privateKey?: string,
): Promise<{ task_id: string; status: string }> {
  return apiFetch<{ task_id: string; status: string }>(`${B}/${id}/restore`, {
    method: 'POST',
    body: JSON.stringify(privateKey ? { confirm, private_key: privateKey } : { confirm }),
  })
}

export async function getBackupConfig(): Promise<BackupConfigStatus> {
  return apiFetch<BackupConfigStatus>(`${B}/config`)
}

/** Without `privateKey`, a backup that needs one is only checked for being intact. */
export async function verifyBackup(
  id: string,
  privateKey?: string,
): Promise<{ task_id: string; status: string }> {
  return apiFetch<{ task_id: string; status: string }>(`${B}/${id}/verify`, {
    method: 'POST',
    body: JSON.stringify(privateKey ? { private_key: privateKey } : {}),
  })
}

export async function deleteBackup(id: string): Promise<void> {
  await apiFetch(`${B}/${id}`, { method: 'DELETE' })
}
