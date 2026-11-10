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
  /** The module the key belongs to (docs/roles.md); null for core keys. */
  module?: string | null;
}

export async function getSystemPermissions(): Promise<PermissionEntry[]> {
  return apiFetch<PermissionEntry[]>("/app/permissions");
}

// ── Version & Changelog ─────────────────────────────────────────────

export interface ChangelogResponse {
  version: string;
  entries: ChangelogEntry[];
}

/** Who reads the notes: the modules they can use in this club, and whether
 *  they are an admin. Items marked for other modules or for admins only are
 *  left out (`<!-- for: ... -->` in CHANGELOG.md). */
export interface ChangelogReader {
  modules: string[];
  admin: boolean;
}

export async function getChangelog(
  lang?: string,
  reader?: ChangelogReader,
): Promise<ChangelogResponse> {
  const q = new URLSearchParams();
  if (lang) q.set("lang", lang);
  if (reader) {
    q.set("modules", reader.modules.join(","));
    if (reader.admin) q.set("admin", "1");
  }
  const qs = q.toString();
  return apiFetch<ChangelogResponse>(`/global/version/changelog${qs ? `?${qs}` : ""}`);
}

// ── Health ──────────────────────────────────────────────────────────

export async function ping(init?: RequestInit): Promise<{ status: string }> {
  return apiFetch<{ status: string }>("/global/health", init);
}
