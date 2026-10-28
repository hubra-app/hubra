import { apiFetch } from '@hubra/api-client';
import type { MailMember } from "@/types";

// ── Admin: Member Mail ─────────────────────────────────────────────────────

interface BackendMailMember {
  id: string;
  name: string;
  public_email: string;
  mailbox_enabled: boolean;
  forwarding_enabled: boolean;
  retention_days: number | null;
  wildduck_id: string | null;
  mailbox_exists: boolean;
}

function adaptMailMember(b: BackendMailMember): MailMember {
  return {
    id: String(b.id),
    name: b.name,
    publicEmail: b.public_email,
    mailboxEnabled: b.mailbox_enabled,
    forwardingEnabled: b.forwarding_enabled,
    retentionDays: b.retention_days ?? null,
    wildduckId: b.wildduck_id ?? null,
    mailboxExists: b.mailbox_exists,
  };
}

export async function updateMailMember(
  id: string,
  input: {
    forwardingEnabled?: boolean;
    retentionDays?: number | null;
    quotaMb?: number;
  },
): Promise<MailMember> {
  const body: Record<string, unknown> = {};
  if (input.forwardingEnabled !== undefined)
    body.forwarding_enabled = input.forwardingEnabled;
  if (input.retentionDays !== undefined)
    body.retention_days = input.retentionDays;
  if (input.quotaMb !== undefined) body.quota_mb = input.quotaMb;
  const b = await apiFetch<BackendMailMember>(`/mail/members/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  return adaptMailMember(b);
}

export async function verifyMemberEmail(id: string): Promise<void> {
  await apiFetch<{ ok: boolean }>(`/members/${id}/verify-email`, {
    method: "POST",
  });
}

// ── Group Mail (ManagedMailAddress) ───────────────────────────────────────

export interface ManagedMailAddressInfo {
  id: number;
  address: string;
  addressType: string;
  isProtected: boolean;
  forwardingEnabled: boolean;
  isEnabled: boolean;
  isSystem: boolean;
  mailPrefix: string | null;
  displayName: string | null;
  cachedForwardTargets: string[] | null;
  fixedForwardTargets: string[] | null;
  ownerType: string | null;
  ownerId: number | null;
  provisioningStatus: string;
  wildduckUserId?: string | null;
  groupName?: string;
  functionName?: string;
  memberName?: string;
  aliases?: MailAliasInfo[];
  kind?: string | null;
  enabled?: boolean | null;
  forwardEnabled?: boolean | null;
  localPart?: string | null;
  domain?: string | null;
  quotaBytes?: number | null;
  retention?: number | null;
  fromWhitelist?: string[];
  isOutboundAuth?: boolean;
  wildduckId?: string | null;
  syncState?: string | null;
  syncError?: string | null;
  quotaUsed?: number | null;
  quotaTotal?: number | null;
  ownerName?: string | null;
  forwardTargets?: string[];
}

// ── Unified address management ───────────────────────────────────────────────

interface AddressFilters {
  ownerType?: string;
  enabled?: boolean;
  syncState?: string;
  search?: string;
}

async function fetchAddresses(
  path: string,
  params?: AddressFilters,
): Promise<ManagedMailAddressInfo[]> {
  const qs = new URLSearchParams();
  if (params?.ownerType) qs.set("owner_type", params.ownerType);
  if (params?.enabled !== undefined)
    qs.set("enabled", String(params.enabled));
  if (params?.syncState) qs.set("sync_state", params.syncState);
  if (params?.search) qs.set("search", params.search);
  const query = qs.toString() ? `?${qs.toString()}` : "";
  const resp = await apiFetch<{ data: ManagedMailAddressInfo[] }>(
    `${path}${query}`,
  );
  return resp.data;
}

export async function listAddresses(
  params?: AddressFilters,
): Promise<ManagedMailAddressInfo[]> {
  return fetchAddresses("/mail/addresses", params);
}

export async function listAllAddresses(
  params?: AddressFilters,
): Promise<ManagedMailAddressInfo[]> {
  return fetchAddresses("/mail/addresses/all", params);
}

export interface MailAliasInfo {
  id: number;
  primaryMmaId: number | null;
  address: string;
  provisioningStatus: string;
  createdAt: string;
  createdById: number | null;
}

export async function deleteGroupMail(groupId: number): Promise<void> {
  await apiFetch(`/mail/groups/${groupId}`, { method: "DELETE" });
}

export async function deleteFunctionMail(functionId: number): Promise<void> {
  await apiFetch(`/mail/functions/${functionId}`, { method: "DELETE" });
}

export async function deleteMemberMail(memberId: number): Promise<void> {
  await apiFetch(`/mail/members-mail/${memberId}`, { method: "DELETE" });
}

export async function toggleMemberMail(
  memberId: number,
  enabled: boolean,
): Promise<ManagedMailAddressInfo> {
  return apiFetch<ManagedMailAddressInfo>(
    `/mail/members-mail/${memberId}/toggle`,
    {
      method: "PATCH",
      body: JSON.stringify({ enabled }),
    },
  );
}

// ── Group Mail: toggle / prefix / aliases ────────────────────────────────────

export async function toggleGroupMail(
  groupId: number,
  enabled: boolean,
): Promise<ManagedMailAddressInfo> {
  return apiFetch<ManagedMailAddressInfo>(`/mail/groups/${groupId}/toggle`, {
    method: "PATCH",
    body: JSON.stringify({ enabled }),
  });
}

export async function changeGroupMailPrefix(
  groupId: number,
  prefix: string,
): Promise<ManagedMailAddressInfo> {
  return apiFetch<ManagedMailAddressInfo>(`/mail/groups/${groupId}/prefix`, {
    method: "PATCH",
    body: JSON.stringify({ prefix }),
  });
}

export async function listGroupAliases(
  groupId: number,
): Promise<ManagedMailAddressInfo[]> {
  const resp = await apiFetch<{ data: ManagedMailAddressInfo[] }>(
    `/mail/groups/${groupId}/aliases`,
  );
  return resp.data;
}

export async function createGroupAlias(
  groupId: number,
  prefix: string,
): Promise<ManagedMailAddressInfo> {
  return apiFetch<ManagedMailAddressInfo>(`/mail/groups/${groupId}/aliases`, {
    method: "POST",
    body: JSON.stringify({ prefix }),
  });
}

export async function deleteGroupAlias(
  groupId: number,
  aliasId: number,
): Promise<void> {
  await apiFetch(`/mail/groups/${groupId}/aliases/${aliasId}`, {
    method: "DELETE",
  });
}

export async function toggleGroupAlias(
  groupId: number,
  aliasId: number,
  enabled: boolean,
): Promise<ManagedMailAddressInfo> {
  return apiFetch<ManagedMailAddressInfo>(
    `/mail/groups/${groupId}/aliases/${aliasId}/toggle`,
    {
      method: "PATCH",
      body: JSON.stringify({ enabled }),
    },
  );
}

// ── Function Mail: toggle / prefix / aliases ─────────────────────────────────

export async function toggleFunctionMail(
  functionId: number,
  enabled: boolean,
): Promise<ManagedMailAddressInfo> {
  return apiFetch<ManagedMailAddressInfo>(
    `/mail/functions/${functionId}/toggle`,
    {
      method: "PATCH",
      body: JSON.stringify({ enabled }),
    },
  );
}

export async function changeFunctionMailPrefix(
  functionId: number,
  prefix: string,
): Promise<ManagedMailAddressInfo> {
  return apiFetch<ManagedMailAddressInfo>(
    `/mail/functions/${functionId}/prefix`,
    {
      method: "PATCH",
      body: JSON.stringify({ prefix }),
    },
  );
}

export async function listFunctionAliases(
  functionId: number,
): Promise<ManagedMailAddressInfo[]> {
  const resp = await apiFetch<{ data: ManagedMailAddressInfo[] }>(
    `/mail/functions/${functionId}/aliases`,
  );
  return resp.data;
}

export async function createFunctionAlias(
  functionId: number,
  prefix: string,
): Promise<ManagedMailAddressInfo> {
  return apiFetch<ManagedMailAddressInfo>(
    `/mail/functions/${functionId}/aliases`,
    {
      method: "POST",
      body: JSON.stringify({ prefix }),
    },
  );
}

export async function deleteFunctionAlias(
  functionId: number,
  aliasId: number,
): Promise<void> {
  await apiFetch(`/mail/functions/${functionId}/aliases/${aliasId}`, {
    method: "DELETE",
  });
}

export async function toggleFunctionAlias(
  functionId: number,
  aliasId: number,
  enabled: boolean,
): Promise<ManagedMailAddressInfo> {
  return apiFetch<ManagedMailAddressInfo>(
    `/mail/functions/${functionId}/aliases/${aliasId}/toggle`,
    {
      method: "PATCH",
      body: JSON.stringify({ enabled }),
    },
  );
}

// ── System Addresses ─────────────────────────────────────────────────────────

export async function listSystemAddresses(): Promise<ManagedMailAddressInfo[]> {
  const resp = await apiFetch<{ data: ManagedMailAddressInfo[] }>(
    "/mail/system-addresses",
  );
  return resp.data;
}

export async function createSystemAddress(input: {
  address: string;
  addressType: string;
  displayName?: string;
  forwardTargets?: string[];
  isProtected?: boolean;
}): Promise<ManagedMailAddressInfo> {
  return apiFetch<ManagedMailAddressInfo>("/mail/system-addresses", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function deleteSystemAddress(id: number): Promise<void> {
  await apiFetch(`/mail/system-addresses/${id}`, { method: "DELETE" });
}

export async function toggleSystemAddress(
  id: number,
  enabled: boolean,
): Promise<ManagedMailAddressInfo> {
  return apiFetch<ManagedMailAddressInfo>(
    `/mail/system-addresses/${id}/toggle`,
    {
      method: "PATCH",
      body: JSON.stringify({ enabled }),
    },
  );
}

export async function resetSystemAddressPassword(
  id: number,
  password?: string,
): Promise<string> {
  const resp = await apiFetch<{ password: string }>(
    `/mail/system-addresses/${id}/reset-password`,
    {
      method: "POST",
      body: JSON.stringify(password ? { password } : {}),
    },
  );
  return resp.password;
}

export async function updateSystemForwarding(
  addressId: number,
  targets: string[],
): Promise<string[]> {
  const resp = await apiFetch<{ targets: string[] }>(
    `/mail/system-addresses/${addressId}/forwarding`,
    { method: "PUT", body: JSON.stringify({ targets }) },
  );
  return resp.targets;
}

// ── fromWhitelist curation ──────────────────────────────────────────────────

export async function getFromWhitelist(
  addressId: number,
): Promise<{ curated: string[]; effective: string[]; live: string[] | null }> {
  return apiFetch<{
    curated: string[];
    effective: string[];
    live: string[] | null;
  }>(`/mail/addresses/${addressId}/from-whitelist`);
}

export async function updateFromWhitelist(
  addressId: number,
  whitelist: string[],
): Promise<string[]> {
  const resp = await apiFetch<{ whitelist: string[] }>(
    `/mail/addresses/${addressId}/from-whitelist`,
    { method: "PUT", body: JSON.stringify({ whitelist }) },
  );
  return resp.whitelist;
}

// ── Mail Administration (unified) ───────────────────────────────────────────

export async function resolveLocalPart(prefix: string): Promise<string> {
  const resp = await apiFetch<{ localPart: string }>(
    `/mail/resolve-local-part?prefix=${encodeURIComponent(prefix)}`,
  );
  return resp.localPart;
}
