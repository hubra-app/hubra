import { apiFetch } from '@hubra/api-client';
import { clearLookups } from "./lookups";
import type { Group, GroupVisibility } from "../types";

interface BackendGroup {
  id: number;
  name: string;
  lead_id: number | null;
  lead_name: string | null;
  description: string | null;
  color: string | null;
  icon_name: string | null;
  member_count: number;
  sessions: string | null;
  is_default: boolean;
  type: string;
  email_alias: string | null;
  visibility?: GroupVisibility;
  parent_group_id: number | null;
  parent_group_name: string | null;
  role_ids?: number[];
  roles?: { id: number; name: string }[];
  tier_ids?: number[];
  tiers?: { id: number; name: string }[];
}

function adapt(b: BackendGroup): Group {
  return {
    id: String(b.id),
    name: b.name,
    lead: b.lead_name ?? "",
    leadId: b.lead_id ?? null,
    description: b.description ?? "",
    color: b.color ?? "#7441e0",
    iconName: b.icon_name ?? "Zap",
    members: b.member_count,
    sessions: b.sessions ?? "",
    type: b.type ?? "interest_group",
    emailAlias: b.email_alias ?? "",
    visibility: b.visibility ?? "visible",
    parentGroupId: b.parent_group_id ?? null,
    parentGroupName: b.parent_group_name ?? null,
    isDefault: b.is_default ?? false,
    roleIds: b.role_ids ?? [],
    roles: b.roles ?? [],
    tierIds: b.tier_ids ?? [],
    tiers: b.tiers ?? [],
  };
}

/** Who sends roles, default flag and tiers: the club, not a leader. */
function links(input: GroupCreate | GroupUpdate, body: Record<string, unknown>) {
  if (input.roleIds !== undefined) body.role_ids = input.roleIds;
  if (input.tierIds !== undefined) body.tier_ids = input.tierIds;
  if (input.isDefault !== undefined) body.is_default = input.isDefault;
}

export async function listGroups(): Promise<Group[]> {
  const data = await apiFetch<BackendGroup[]>("/app/groups");
  return data.map(adapt);
}

export interface GroupCreate {
  name: string;
  description?: string;
  leadId?: number;
  color?: string;
  sessions?: string;
  type?: string;
  emailAlias?: string;
  visibility?: GroupVisibility;
  parentGroupId?: number | null;
  /** The roles everyone in the group holds. */
  roleIds?: number[];
  /** Tiers whose members are in the group. */
  tierIds?: number[];
  /** New members join the group. */
  isDefault?: boolean;
}

export async function createGroup(input: GroupCreate): Promise<Group> {
  const body: Record<string, unknown> = { name: input.name };
  if (input.description) body.description = input.description;
  if (input.color) body.color = input.color;
  if (input.leadId !== undefined) body.lead_id = input.leadId;
  if (input.sessions !== undefined) body.sessions = input.sessions;
  if (input.type) body.type = input.type;
  if (input.emailAlias !== undefined) body.email_alias = input.emailAlias;
  if (input.visibility !== undefined) body.visibility = input.visibility;
  if (input.parentGroupId !== undefined) body.parent_group_id = input.parentGroupId;
  links(input, body);
  const b = await apiFetch<BackendGroup>("/app/groups/", {
    method: "POST",
    body: JSON.stringify(body),
  });
  clearLookups();
  return adapt(b);
}

export interface GroupUpdate {
  name?: string;
  description?: string;
  color?: string;
  leadId?: number | null;
  sessions?: string;
  type?: string;
  emailAlias?: string;
  visibility?: GroupVisibility;
  parentGroupId?: number | null;
  roleIds?: number[];
  tierIds?: number[];
  isDefault?: boolean;
}

export async function updateGroup(
  id: string,
  input: GroupUpdate,
): Promise<Group> {
  const body: Record<string, unknown> = {};
  if (input.name !== undefined) body.name = input.name;
  if (input.description !== undefined) body.description = input.description;
  if (input.color !== undefined) body.color = input.color;
  if ("leadId" in input) body.lead_id = input.leadId;
  if (input.sessions !== undefined) body.sessions = input.sessions;
  if (input.type !== undefined) body.type = input.type;
  if (input.emailAlias !== undefined) body.email_alias = input.emailAlias;
  if (input.visibility !== undefined) body.visibility = input.visibility;
  if (input.parentGroupId !== undefined) body.parent_group_id = input.parentGroupId;
  links(input, body);
  const b = await apiFetch<BackendGroup>(`/app/groups/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  clearLookups();
  return adapt(b);
}

export async function deleteGroup(id: string): Promise<void> {
  await apiFetch(`/app/groups/${id}`, { method: "DELETE" });
  clearLookups();
}

export async function addGroupMember(
  groupId: string,
  memberId: string,
): Promise<void> {
  await apiFetch(`/app/groups/${groupId}/members/${memberId}`, { method: "POST" });
}

export async function removeGroupMember(
  groupId: string,
  memberId: string,
): Promise<void> {
  await apiFetch(`/app/groups/${groupId}/members/${memberId}`, {
    method: "DELETE",
  });
}

export interface JoinableGroup {
  id: number;
  name: string;
  description: string | null;
  color: string | null;
  iconName: string | null;
  type: string;
  memberCount: number;
  joined: boolean;
}

export async function listJoinableGroups(): Promise<JoinableGroup[]> {
  return apiFetch<JoinableGroup[]>("/app/groups/joinable");
}

export async function joinGroup(id: number): Promise<void> {
  await apiFetch(`/app/groups/${id}/join`, { method: "POST" });
}

export async function leaveGroup(id: number): Promise<void> {
  await apiFetch(`/app/groups/${id}/leave`, { method: "POST" });
}

export interface GroupFunctionHolder {
  functionId: number;
  functionName: string;
  memberId: number;
  memberName: string | null;
  roleNames: string[];
}

/** The group functions held for this group (Trainer/in: Anna). */
export async function listGroupFunctions(groupId: string): Promise<GroupFunctionHolder[]> {
  const b = await apiFetch<{
    functions?: {
      function_id: number;
      function_name: string;
      member_id: number;
      member_name: string | null;
      role_names: string[];
    }[];
  }>(`/app/groups/${groupId}`);
  return (b.functions ?? []).map((f) => ({
    functionId: f.function_id,
    functionName: f.function_name,
    memberId: f.member_id,
    memberName: f.member_name,
    roleNames: f.role_names,
  }));
}
