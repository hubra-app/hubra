import { apiFetch } from '@hubra/api-client'

// Backups dump the whole database, so they are the platform's (backups.manage).
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
}

export interface BackupConfigStatus {
  s3_configured: boolean
  s3_reachable: boolean
  s3_error: string | null
  encryption_configured: boolean
  endpoint: string
  bucket: string
  region: string
}

export async function listBackups(): Promise<BackupRecord[]> {
  return apiFetch<BackupRecord[]>(`${B}/`)
}

export async function createBackup(): Promise<{ task_id: string; status: string }> {
  return apiFetch<{ task_id: string; status: string }>(`${B}/`, {
    method: 'POST',
  })
}

export async function getBackupConfig(): Promise<BackupConfigStatus> {
  return apiFetch<BackupConfigStatus>(`${B}/config`)
}

export async function verifyBackup(id: string): Promise<{ task_id: string; status: string }> {
  return apiFetch<{ task_id: string; status: string }>(`${B}/${id}/verify`, {
    method: 'POST',
  })
}

export async function deleteBackup(id: string): Promise<void> {
  await apiFetch(`${B}/${id}`, { method: 'DELETE' })
}
