import { apiFetch } from '@hubra/api-client';
import type { ClubFunction } from "../types";

interface BackendFunction {
  id: number;
  name: string;
  description: string | null;
  maxHolders: number;
  grantsRoleId?: number | null;
  holders: {
    memberId: number;
    memberName: string;
    assignedAt: string | null;
  }[];
}

function adapt(b: BackendFunction): ClubFunction {
  return {
    id: b.id,
    name: b.name,
    description: b.description,
    maxHolders: b.maxHolders,
    grantsRoleId: b.grantsRoleId ?? null,
    holders: b.holders,
  };
}

export async function listFunctions(): Promise<ClubFunction[]> {
  const data = await apiFetch<BackendFunction[]>("/functions/");
  return data.map(adapt);
}

export interface FunctionCreate {
  name: string;
  description?: string;
  maxHolders?: number;
  /** The role the function gives its holders; null for none. */
  grantsRoleId?: number | null;
}

export async function createFunction(
  input: FunctionCreate,
): Promise<ClubFunction> {
  const body: Record<string, unknown> = { name: input.name };
  if (input.description !== undefined) body.description = input.description;
  if (input.maxHolders !== undefined) body.maxHolders = input.maxHolders;
  if (input.grantsRoleId !== undefined) body.grantsRoleId = input.grantsRoleId;
  const b = await apiFetch<BackendFunction>("/functions/", {
    method: "POST",
    body: JSON.stringify(body),
  });
  return adapt(b);
}

export interface FunctionUpdate {
  name?: string;
  description?: string;
  maxHolders?: number;
  grantsRoleId?: number | null;
}

export async function updateFunction(
  id: number,
  input: FunctionUpdate,
): Promise<ClubFunction> {
  const body: Record<string, unknown> = {};
  if (input.name !== undefined) body.name = input.name;
  if (input.description !== undefined) body.description = input.description;
  if (input.maxHolders !== undefined) body.maxHolders = input.maxHolders;
  if (input.grantsRoleId !== undefined) body.grantsRoleId = input.grantsRoleId;
  const b = await apiFetch<BackendFunction>(`/functions/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  return adapt(b);
}

export async function deleteFunction(id: number): Promise<void> {
  await apiFetch(`/functions/${id}`, { method: "DELETE" });
}

export async function assignHolder(
  functionId: number,
  memberId: number,
): Promise<void> {
  await apiFetch(`/functions/${functionId}/holders`, {
    method: "POST",
    body: JSON.stringify({ memberId }),
  });
}

export async function removeHolder(
  functionId: number,
  memberId: number,
): Promise<void> {
  await apiFetch(`/functions/${functionId}/holders/${memberId}`, {
    method: "DELETE",
  });
}
