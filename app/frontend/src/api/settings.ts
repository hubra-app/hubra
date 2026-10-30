import { apiFetch } from '@hubra/api-client';
import { clearLookups } from "./lookups";
import type { AuditEntry } from "../types";

// ── Settings KV ────────────────────────────────────────────────────────────

export interface SettingEntry {
  key: string;
  value: string | null;
  namespace: string;
  sensitive: boolean;
  required: boolean;
  restricted: boolean;
  validation_type: string | null;
  description: string | null;
  label: string | null;
  is_default: boolean;
  default_value: string | null;
}

export async function listSettings(): Promise<SettingEntry[]> {
  return apiFetch<SettingEntry[]>("/settings");
}

export interface SettingMetadata {
  description?: string | null;
  validation_type?: string | null;
  namespace?: string | null;
  label?: string | null;
  sensitive?: boolean | null;
  required?: boolean | null;
  restricted?: boolean | null;
}

export async function upsertSetting(
  key: string,
  value: string,
  extra?: SettingMetadata,
): Promise<SettingEntry> {
  return apiFetch<SettingEntry>(`/settings/${key}`, {
    method: "PUT",
    body: JSON.stringify({ value, ...extra }),
  });
}

export async function deleteSetting(key: string): Promise<void> {
  await apiFetch(`/settings/${key}`, { method: "DELETE" });
}

// ── Roles ──────────────────────────────────────────────────────────────────

export interface Role {
  id: string;
  name: string;
  isDefault: boolean;
  isAdmin: boolean;
  /** Owner, Admin, Treasurer, Member: can't be renamed or deleted. */
  isSystem: boolean;
  isOwner: boolean;
  /** Members holding it, themselves or through a function. */
  memberCount: number;
  description: string | null;
}

interface BackendRole {
  id: number;
  name: string;
  is_default: boolean;
  is_admin: boolean;
  is_system?: boolean;
  is_owner?: boolean;
  member_count?: number;
  description: string | null;
}

function adaptRole(b: BackendRole): Role {
  return {
    id: String(b.id),
    name: b.name,
    isDefault: b.is_default,
    isAdmin: b.is_admin,
    isSystem: b.is_system ?? false,
    isOwner: b.is_owner ?? false,
    memberCount: b.member_count ?? 0,
    description: b.description,
  };
}

export async function listRoles(): Promise<Role[]> {
  const data = await apiFetch<BackendRole[]>("/roles");
  return data.map(adaptRole);
}

export async function createRole(
  name: string,
  description?: string | null,
): Promise<Role> {
  const b = await apiFetch<BackendRole>("/roles/", {
    method: "POST",
    body: JSON.stringify({ name, description: description ?? null }),
  });
  clearLookups();
  return adaptRole(b);
}

export async function updateRole(
  id: string,
  patch: { name: string; description?: string | null; is_admin?: boolean },
): Promise<Role> {
  const b = await apiFetch<BackendRole>(`/roles/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
  clearLookups();
  return adaptRole(b);
}

export async function deleteRole(id: string): Promise<void> {
  await apiFetch(`/roles/${id}`, { method: "DELETE" });
  clearLookups();
}

export async function getRolePermissions(id: string): Promise<string[]> {
  const data = await apiFetch<{ role_id: number; permissions: string[] }>(
    `/roles/${id}/permissions`,
  );
  return data.permissions;
}

export async function setRolePermissions(
  id: string,
  permissions: string[],
): Promise<string[]> {
  const data = await apiFetch<{ role_id: number; permissions: string[] }>(
    `/roles/${id}/permissions`,
    {
      method: "PUT",
      body: JSON.stringify({ permissions }),
    },
  );
  return data.permissions;
}

// ── Audit Log ──────────────────────────────────────────────────────────────

interface BackendAuditEntry {
  id: number;
  actor_id: number | null;
  actor_name: string | null;
  actor_avatar_color: string | null;
  action: string;
  target_type: string | null;
  target_id: number | null;
  target_label: string | null;
  time: string;
}

export interface AuditEntryDetail {
  id: string;
  actorId: number | null;
  actorName: string | null;
  actorAvatarColor: string;
  action: string;
  targetType: string | null;
  targetId: number | null;
  targetLabel: string | null;
  time: string;
}

function adaptAuditDetail(b: BackendAuditEntry): AuditEntryDetail {
  return {
    id: String(b.id),
    actorId: b.actor_id ?? null,
    actorName: b.actor_name ?? null,
    actorAvatarColor: b.actor_avatar_color ?? "#857f99",
    action: b.action,
    targetType: b.target_type ?? null,
    targetId: b.target_id ?? null,
    targetLabel: b.target_label ?? null,
    time: b.time,
  };
}

export async function getAuditEntry(id: string): Promise<AuditEntryDetail> {
  const b = await apiFetch<BackendAuditEntry>(`/audit/${id}`);
  return adaptAuditDetail(b);
}

function adaptAudit(b: BackendAuditEntry): AuditEntry {
  return {
    id: String(b.id),
    actor: b.actor_name ?? (b.actor_id != null ? String(b.actor_id) : "System"),
    action: b.action.replace(/_/g, " "),
    target: `${b.target_type}: ${b.target_label}`,
    time: b.time,
    avatarColor: b.actor_avatar_color ?? "#857f99",
  };
}

interface AuditLogPage {
  entries: AuditEntry[];
  total: number;
  totalPages: number;
}

export async function listAuditLog(params?: {
  page?: number;
  pageSize?: number;
  action?: string;
}): Promise<AuditLogPage> {
  const qs = new URLSearchParams();
  if (params?.page !== undefined) qs.set("page", String(params.page));
  if (params?.pageSize !== undefined)
    qs.set("pageSize", String(params.pageSize));
  if (params?.action) qs.set("action", params.action);
  const query = qs.toString() ? `?${qs.toString()}` : "";
  const data = await apiFetch<{
    data: BackendAuditEntry[];
    total: number;
    page: number;
    pageSize: number;
    totalPages: number;
  }>(`/audit${query}`);
  return {
    entries: data.data.map(adaptAudit),
    total: data.total,
    totalPages: data.totalPages,
  };
}

// ── Club profile (what every member sees of Settings > Verein) ───────────────

export interface ClubProfile {
  club_name: string | null;
  club_description: string | null;
  logo: string | null;
  primary_color: string | null;
  secondary_color: string | null;
  accent_color: string | null;
  timezone: string | null;
  locale: string | null;
  date_format: string | null;
  /** The announcement banner text while it is switched on, else null. */
  banner: string | null;
}

export async function getClubProfile(): Promise<ClubProfile> {
  return apiFetch<ClubProfile>("/settings/club-profile");
}

// ── Roles held for one group ────────────────────────────────────────────────

export interface RoleScope {
  id: number;
  memberId: string;
  memberName: string;
  groupId: number;
  groupName: string;
}

export async function listRoleScopes(roleId: string): Promise<RoleScope[]> {
  const data = await apiFetch<
    { id: number; member_id: number; member_name: string; group_id: number; group_name: string }[]
  >(`/roles/${roleId}/scopes`);
  return data.map((s) => ({
    id: s.id,
    memberId: String(s.member_id),
    memberName: s.member_name,
    groupId: s.group_id,
    groupName: s.group_name,
  }));
}

export async function addRoleScope(roleId: string, memberId: string, groupId: number): Promise<void> {
  await apiFetch(`/roles/${roleId}/scopes`, {
    method: "POST",
    body: JSON.stringify({ member_id: Number(memberId), group_id: groupId }),
  });
}

export async function removeRoleScope(roleId: string, scopeId: number): Promise<void> {
  await apiFetch(`/roles/${roleId}/scopes/${scopeId}`, { method: "DELETE" });
}
