import { apiFetch } from '@hubra/api-client';
import type { ClubFunction } from "../types";

interface BackendFunction {
  id: number;
  name: string;
  description: string | null;
  maxHolders: number;
  grantsRoleId?: number | null;
  grantsRoleIds?: number[];
  perGroup?: boolean;
  holders: {
    memberId: number;
    memberName: string;
    assignedAt: string | null;
    groupId?: number | null;
    groupName?: string | null;
  }[];
}

function adapt(b: BackendFunction): ClubFunction {
  return {
    id: b.id,
    name: b.name,
    description: b.description,
    maxHolders: b.maxHolders,
    grantsRoleId: b.grantsRoleId ?? null,
    grantsRoleIds: b.grantsRoleIds ?? (b.grantsRoleId != null ? [b.grantsRoleId] : []),
    perGroup: b.perGroup ?? false,
    holders: b.holders,
  };
}

export async function listFunctions(): Promise<ClubFunction[]> {
  const data = await apiFetch<BackendFunction[]>("/app/functions/");
  return data.map(adapt);
}

export interface FunctionCreate {
  name: string;
  description?: string;
  maxHolders?: number;
  /** The roles the function gives its holders (Kassier/in: Vorstand and
   *  Kassier/in); [] for none. */
  grantsRoleIds?: number[];
  /** A group function: holders are named per group. */
  perGroup?: boolean;
}

export async function createFunction(
  input: FunctionCreate,
): Promise<ClubFunction> {
  const body: Record<string, unknown> = { name: input.name };
  if (input.description !== undefined) body.description = input.description;
  if (input.maxHolders !== undefined) body.maxHolders = input.maxHolders;
  if (input.grantsRoleIds !== undefined) body.grantsRoleIds = input.grantsRoleIds;
  if (input.perGroup !== undefined) body.perGroup = input.perGroup;
  const b = await apiFetch<BackendFunction>("/app/functions/", {
    method: "POST",
    body: JSON.stringify(body),
  });
  return adapt(b);
}

export interface FunctionUpdate {
  name?: string;
  description?: string;
  maxHolders?: number;
  grantsRoleIds?: number[];
  perGroup?: boolean;
}

export async function updateFunction(
  id: number,
  input: FunctionUpdate,
): Promise<ClubFunction> {
  const body: Record<string, unknown> = {};
  if (input.name !== undefined) body.name = input.name;
  if (input.description !== undefined) body.description = input.description;
  if (input.maxHolders !== undefined) body.maxHolders = input.maxHolders;
  if (input.grantsRoleIds !== undefined) body.grantsRoleIds = input.grantsRoleIds;
  if (input.perGroup !== undefined) body.perGroup = input.perGroup;
  const b = await apiFetch<BackendFunction>(`/app/functions/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  return adapt(b);
}

export async function deleteFunction(id: number): Promise<void> {
  await apiFetch(`/app/functions/${id}`, { method: "DELETE" });
}

/** Name a holder; a group function also needs the group they hold it for. */
export async function assignHolder(
  functionId: number,
  memberId: number,
  groupId?: number | null,
): Promise<void> {
  await apiFetch(`/app/functions/${functionId}/holders`, {
    method: "POST",
    body: JSON.stringify(groupId != null ? { memberId, groupId } : { memberId }),
  });
}

export async function removeHolder(
  functionId: number,
  memberId: number,
  groupId?: number | null,
): Promise<void> {
  const query = groupId != null ? `?groupId=${groupId}` : "";
  await apiFetch(`/app/functions/${functionId}/holders/${memberId}${query}`, {
    method: "DELETE",
  });
}
