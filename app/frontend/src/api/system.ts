import { apiFetch } from '@hubra/api-client';

export interface PermissionEntry {
  method: string;
  path: string;
  key: string;
  display_name: string;
  resource: string;
  action: string;
  blueprint: string;
}

export async function getSystemPermissions(): Promise<PermissionEntry[]> {
  return apiFetch<PermissionEntry[]>("/system/permissions");
}

// ── Version & Changelog ─────────────────────────────────────────────

export interface ChangelogEntry {
  version: string;
  date: string | null;
  sections: Record<string, string[]>;
}

export interface ChangelogResponse {
  version: string;
  entries: ChangelogEntry[];
}

export async function getChangelog(): Promise<ChangelogResponse> {
  return apiFetch<ChangelogResponse>("/version/changelog");
}

// ── Health ──────────────────────────────────────────────────────────

export async function ping(init?: RequestInit): Promise<{ status: string }> {
  return apiFetch<{ status: string }>("/health", init);
}
