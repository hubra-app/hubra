import { apiFetch } from '@hubra/api-client';
import type { ChangelogEntry } from '@hubra/ui';

export type { ChangelogEntry, RoadmapItem } from '@hubra/ui';

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
  return apiFetch<PermissionEntry[]>("/app/permissions");
}

// ── Version & Changelog ─────────────────────────────────────────────

export interface ChangelogResponse {
  version: string;
  entries: ChangelogEntry[];
}

export async function getChangelog(lang?: string): Promise<ChangelogResponse> {
  const q = lang ? `?lang=${encodeURIComponent(lang)}` : "";
  return apiFetch<ChangelogResponse>(`/global/version/changelog${q}`);
}

// ── Health ──────────────────────────────────────────────────────────

export async function ping(init?: RequestInit): Promise<{ status: string }> {
  return apiFetch<{ status: string }>("/global/health", init);
}
