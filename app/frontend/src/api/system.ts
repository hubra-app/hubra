import { apiFetch } from '@vollbuild/api-client';

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

export interface ServiceStatus {
  ok: boolean;
  latency_ms: number;
  error?: string;
}

export interface HealthDetail {
  status: string;
  version: string;
  services: Record<string, ServiceStatus>;
}

export async function getHealthDetailed(): Promise<HealthDetail> {
  return apiFetch<HealthDetail>("/health/detailed");
}

export async function getVersion(): Promise<{ version: string }> {
  return apiFetch<{ version: string }>("/version");
}

export async function ping(init?: RequestInit): Promise<{ status: string }> {
  return apiFetch<{ status: string }>("/health", init);
}
