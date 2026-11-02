import { apiFetch } from '@hubra/api-client';
import type { ChangelogEntry, RoadmapItem, RoadmapStatus } from '@hubra/ui';

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
  return apiFetch<PermissionEntry[]>("/system/permissions");
}

// ── Version & Changelog ─────────────────────────────────────────────

export interface ChangelogResponse {
  version: string;
  entries: ChangelogEntry[];
}

export async function getChangelog(): Promise<ChangelogResponse> {
  return apiFetch<ChangelogResponse>("/version/changelog");
}

export interface RoadmapResponse {
  statuses: RoadmapStatus[];
  items: RoadmapItem[];
}

export async function getRoadmap(): Promise<RoadmapResponse> {
  return apiFetch<RoadmapResponse>("/version/roadmap");
}

// ── Health ──────────────────────────────────────────────────────────

export async function ping(init?: RequestInit): Promise<{ status: string }> {
  return apiFetch<{ status: string }>("/health", init);
}
