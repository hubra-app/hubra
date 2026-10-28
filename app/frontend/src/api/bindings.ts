import { apiFetch } from '@vollbuild/api-client';

export interface InternalKey {
  id: number;
  key: string;
  allow_multiple: boolean;
  is_protected: boolean;
  label: string | null;
  has_value: boolean;
  masked_value: string | null;
  sensitive: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface Binding {
  id: number;
  type: string;
  source_id: string;
  source_attribute: string;
  key_id: number;
  key_name: string | null;
  allow_multiple: boolean;
  validator: string;
  is_protected: boolean;
  enabled: boolean;
  validation_status: string;
  validation_error: string | null;
  source_label: string | null;
  resolved_value: string | null;
  resolved_sensitive: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface RegistryEntry {
  type: string;
  attributes: { name: string; label: string }[];
}

export async function listKeys(): Promise<InternalKey[]> {
  return apiFetch<InternalKey[]>("/bindings/keys");
}

export async function createKey(data: {
  key: string;
  allow_multiple?: boolean;
  is_protected?: boolean;
  label?: string | null;
}): Promise<InternalKey> {
  return apiFetch<InternalKey>("/bindings/keys", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateKey(
  id: number,
  data: {
    label?: string | null;
    allow_multiple?: boolean;
    is_protected?: boolean;
  },
): Promise<InternalKey> {
  return apiFetch<InternalKey>(`/bindings/keys/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteKey(id: number): Promise<void> {
  await apiFetch(`/bindings/keys/${id}`, { method: "DELETE" });
}

export async function listBindings(params?: {
  key_id?: number;
  type?: string;
}): Promise<Binding[]> {
  const qs = new URLSearchParams();
  if (params?.key_id !== undefined) qs.set("key_id", String(params.key_id));
  if (params?.type) qs.set("type", params.type);
  const query = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch<Binding[]>(`/bindings/${query}`);
}

export async function createBinding(data: {
  type: string;
  source_id: string;
  source_attribute: string;
  key_id: number;
  validator?: string;
  enabled?: boolean;
  is_protected?: boolean;
}): Promise<Binding> {
  return apiFetch<Binding>("/bindings/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateBinding(
  id: number,
  data: {
    type?: string;
    source_id?: string;
    source_attribute?: string;
    key_id?: number;
    validator?: string;
    enabled?: boolean;
    is_protected?: boolean;
  },
): Promise<Binding> {
  return apiFetch<Binding>(`/bindings/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteBinding(id: number): Promise<void> {
  await apiFetch(`/bindings/${id}`, { method: "DELETE" });
}

export async function toggleBinding(
  id: number,
  enabled: boolean,
): Promise<Binding> {
  return apiFetch<Binding>(`/bindings/${id}/toggle`, {
    method: "POST",
    body: JSON.stringify({ enabled }),
  });
}

export async function getRegistry(): Promise<RegistryEntry[]> {
  return apiFetch<RegistryEntry[]>("/bindings/registry");
}

export async function getValidators(): Promise<string[]> {
  return apiFetch<string[]>("/bindings/validators");
}

export interface BindingSource {
  id: string;
  label: string;
  preview: Record<string, string | boolean | null>;
  aliases?: { id: number; address: string }[];
}

export async function getSources(type: string): Promise<BindingSource[]> {
  return apiFetch<BindingSource[]>(
    `/bindings/sources?type=${encodeURIComponent(type)}`,
  );
}

export interface BindingPreview {
  value: string | null;
  masked: boolean;
  sensitive: boolean;
}

export async function previewBindingValue(
  type: string,
  sourceId: string,
  sourceAttribute: string,
): Promise<BindingPreview> {
  const qs = new URLSearchParams({
    type,
    source_id: sourceId,
    source_attribute: sourceAttribute,
  });
  return apiFetch<BindingPreview>(`/bindings/preview?${qs.toString()}`);
}
