import { apiFetch } from '@vollbuild/api-client';
import type { Code } from "../types";

interface BackendCode {
  id: number;
  name: string;
  code: string;
  description: string | null;
  is_active: boolean;
  created_by: string | null;
  updated_by: string | null;
  created_at: string;
  updated_at: string;
}

function adapt(b: BackendCode): Code {
  return {
    id: String(b.id),
    name: b.name,
    code: b.code,
    description: b.description,
    isActive: b.is_active,
    createdBy: b.created_by,
    updatedBy: b.updated_by,
    createdAt: b.created_at,
    updatedAt: b.updated_at,
  };
}

export async function listCodes(): Promise<Code[]> {
  const data = await apiFetch<BackendCode[]>("/codes/");
  return data.map(adapt);
}

export async function getCode(id: string): Promise<Code> {
  const b = await apiFetch<BackendCode>(`/codes/${id}`);
  return adapt(b);
}

export interface CodeCreate {
  name: string;
  code: string;
  description?: string | null;
}

export async function createCode(input: CodeCreate): Promise<Code> {
  const body: Record<string, unknown> = { name: input.name, code: input.code };
  if (input.description !== undefined) body.description = input.description;
  const b = await apiFetch<BackendCode>("/codes/", {
    method: "POST",
    body: JSON.stringify(body),
  });
  return adapt(b);
}

export interface CodeUpdate {
  name?: string;
  code?: string;
  description?: string | null;
  isActive?: boolean;
}

export async function updateCode(id: string, input: CodeUpdate): Promise<Code> {
  const body: Record<string, unknown> = {};
  if (input.name !== undefined) body.name = input.name;
  if (input.code !== undefined) body.code = input.code;
  if (input.description !== undefined) body.description = input.description;
  if (input.isActive !== undefined) body.is_active = input.isActive;
  const b = await apiFetch<BackendCode>(`/codes/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  return adapt(b);
}

export async function deleteCode(id: string): Promise<void> {
  await apiFetch(`/codes/${id}`, { method: "DELETE" });
}
