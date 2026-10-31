import { apiFetch } from '@hubra/api-client';
import { clearLookups } from "./lookups";
import type { Group } from "../types";

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
  is_public: boolean;
  self_join?: boolean;
  parent_group_id: number | null;
  parent_group_name: string | null;
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
    isPublic: b.is_public ?? true,
    selfJoin: b.self_join ?? false,
    parentGroupId: b.parent_group_id ?? null,
    parentGroupName: b.parent_group_name ?? null,
  };
}

export async function listGroups(): Promise<Group[]> {
  const data = await apiFetch<BackendGroup[]>("/groups");
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
  isPublic?: boolean;
  selfJoin?: boolean;
  parentGroupId?: number | null;
}

export async function createGroup(input: GroupCreate): Promise<Group> {
  const body: Record<string, unknown> = { name: input.name };
  if (input.description) body.description = input.description;
  if (input.color) body.color = input.color;
  if (input.leadId !== undefined) body.lead_id = input.leadId;
  if (input.sessions !== undefined) body.sessions = input.sessions;
  if (input.type) body.type = input.type;
  if (input.emailAlias !== undefined) body.email_alias = input.emailAlias;
  if (input.isPublic !== undefined) body.is_public = input.isPublic;
  if (input.selfJoin !== undefined) body.self_join = input.selfJoin;
  if (input.parentGroupId !== undefined) body.parent_group_id = input.parentGroupId;
  const b = await apiFetch<BackendGroup>("/groups/", {
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
  isPublic?: boolean;
  selfJoin?: boolean;
  parentGroupId?: number | null;
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
  if (input.isPublic !== undefined) body.is_public = input.isPublic;
  if (input.selfJoin !== undefined) body.self_join = input.selfJoin;
  if (input.parentGroupId !== undefined) body.parent_group_id = input.parentGroupId;
  const b = await apiFetch<BackendGroup>(`/groups/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  clearLookups();
  return adapt(b);
}

export async function deleteGroup(id: string): Promise<void> {
  await apiFetch(`/groups/${id}`, { method: "DELETE" });
  clearLookups();
}

export async function addGroupMember(
  groupId: string,
  memberId: string,
): Promise<void> {
  await apiFetch(`/groups/${groupId}/members/${memberId}`, { method: "POST" });
}

export async function removeGroupMember(
  groupId: string,
  memberId: string,
): Promise<void> {
  await apiFetch(`/groups/${groupId}/members/${memberId}`, {
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
  return apiFetch<JoinableGroup[]>("/groups/joinable");
}

export async function joinGroup(id: number): Promise<void> {
  await apiFetch(`/groups/${id}/join`, { method: "POST" });
}

export async function leaveGroup(id: number): Promise<void> {
  await apiFetch(`/groups/${id}/leave`, { method: "POST" });
}
