import { apiFetch } from '@vollbuild/api-client';
import type { Mailbox, Alias, MailMember, MemberMailResponse } from "@/types";

// ── Mailboxes ──────────────────────────────────────────────────────────────

interface BackendMailbox {
  id: string;
  address: string;
  displayName: string;
  messageCount: number;
  quotaUsed: number;
  quotaTotal: number;
  sendOnly: boolean;
  memberId: number | null;
  memberName: string | null;
  isProvisioned: boolean;
}

function adaptMailbox(b: BackendMailbox): Mailbox {
  return {
    id: String(b.id),
    address: b.address,
    displayName: b.displayName,
    messageCount: b.messageCount,
    quotaUsed: b.quotaUsed,
    quotaTotal: b.quotaTotal,
    sendOnly: b.sendOnly,
    memberId: b.memberId,
    memberName: b.memberName,
    isProvisioned: b.isProvisioned,
  };
}

export async function listMailboxes(): Promise<Mailbox[]> {
  const resp = await apiFetch<{ data: BackendMailbox[] }>("/mail/mailboxes");
  return resp.data.map(adaptMailbox);
}

export async function createMailbox(input: {
  address: string;
  displayName: string;
}): Promise<Mailbox> {
  const b = await apiFetch<BackendMailbox>("/mail/mailboxes", {
    method: "POST",
    body: JSON.stringify({
      address: input.address,
      display_name: input.displayName,
    }),
  });
  return adaptMailbox(b);
}

export async function updateMailbox(
  id: string,
  input: { displayName?: string },
): Promise<Mailbox> {
  const b = await apiFetch<BackendMailbox>(`/mail/mailboxes/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ display_name: input.displayName }),
  });
  return adaptMailbox(b);
}

export async function deleteMailbox(id: string): Promise<void> {
  await apiFetch(`/mail/mailboxes/${id}`, { method: "DELETE" });
}

// ── Aliases ────────────────────────────────────────────────────────────────

interface BackendAlias {
  id: string;
  address: string;
  type: "Alias" | "Forward" | "Distribution";
  deliversTo: string[];
  enabled: boolean;
  groupId: number | null;
  groupName: string | null;
  isMainAlias?: boolean;
}

function adaptAlias(b: BackendAlias): Alias {
  return {
    id: String(b.id),
    address: b.address,
    type: b.type,
    deliversTo: b.deliversTo,
    enabled: b.enabled,
    groupId: b.groupId ?? null,
    groupName: b.groupName ?? null,
    isMainAlias: b.isMainAlias ?? false,
  };
}

export async function listAliases(groupId?: number): Promise<Alias[]> {
  const query = groupId !== undefined ? `?groupId=${groupId}` : "";
  const resp = await apiFetch<{ data: BackendAlias[] }>(
    `/mail/aliases${query}`,
  );
  return resp.data.map(adaptAlias);
}

export async function createAlias(input: {
  address: string;
  type: string;
  deliversTo: string[];
  groupId?: number | null;
}): Promise<Alias> {
  const b = await apiFetch<BackendAlias>("/mail/aliases", {
    method: "POST",
    body: JSON.stringify({
      address: input.address,
      type: input.type,
      delivers_to: input.deliversTo,
      groupId: input.groupId ?? null,
    }),
  });
  return adaptAlias(b);
}

export async function updateAlias(
  id: string,
  input: { enabled?: boolean; deliversTo?: string[] },
): Promise<Alias> {
  const body: Record<string, unknown> = {};
  if (input.enabled !== undefined) body.enabled = input.enabled;
  if (input.deliversTo !== undefined) body.delivers_to = input.deliversTo;
  const b = await apiFetch<BackendAlias>(`/mail/aliases/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  return adaptAlias(b);
}

export async function deleteAlias(id: string): Promise<void> {
  await apiFetch(`/mail/aliases/${id}`, { method: "DELETE" });
}

export async function sendTestEmail(to: string): Promise<void> {
  await apiFetch("/mail/test", {
    method: "POST",
    body: JSON.stringify({ to }),
  });
}

// ── Member Mail ────────────────────────────────────────────────────────────

export async function getMemberMail(): Promise<MemberMailResponse> {
  return apiFetch<MemberMailResponse>("/members/me/mail");
}

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

export async function listMailMembers(): Promise<MailMember[]> {
  const resp = await apiFetch<{ data: BackendMailMember[] }>("/mail/members");
  return resp.data.map(adaptMailMember);
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

export async function provisionMemberMail(id: string): Promise<void> {
  await apiFetch<{ ok: boolean }>(`/members/${id}/provision`, {
    method: "POST",
  });
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

export async function listAddresses(params?: {
  ownerType?: string;
  enabled?: boolean;
  syncState?: string;
  search?: string;
}): Promise<ManagedMailAddressInfo[]> {
  const qs = new URLSearchParams();
  if (params?.ownerType) qs.set("owner_type", params.ownerType);
  if (params?.enabled !== undefined)
    qs.set("enabled", String(params.enabled));
  if (params?.syncState) qs.set("sync_state", params.syncState);
  if (params?.search) qs.set("search", params.search);
  const query = qs.toString() ? `?${qs.toString()}` : "";
  const resp = await apiFetch<{ data: ManagedMailAddressInfo[] }>(
    `/mail/addresses${query}`,
  );
  return resp.data;
}

export async function listAllAddresses(params?: {
  ownerType?: string;
  enabled?: boolean;
  syncState?: string;
  search?: string;
}): Promise<ManagedMailAddressInfo[]> {
  const qs = new URLSearchParams();
  if (params?.ownerType) qs.set("owner_type", params.ownerType);
  if (params?.enabled !== undefined)
    qs.set("enabled", String(params.enabled));
  if (params?.syncState) qs.set("sync_state", params.syncState);
  if (params?.search) qs.set("search", params.search);
  const query = qs.toString() ? `?${qs.toString()}` : "";
  const resp = await apiFetch<{ data: ManagedMailAddressInfo[] }>(
    `/mail/addresses/all${query}`,
  );
  return resp.data;
}

export async function listSelectableAddresses(): Promise<
  { id: number; address: string; ownerType: string }[]
> {
  return apiFetch(`/mail/addresses/selectable`);
}

export async function getAddress(
  id: number,
): Promise<ManagedMailAddressInfo> {
  return apiFetch<ManagedMailAddressInfo>(`/mail/addresses/${id}`);
}

export async function toggleAddress(
  id: number,
  enabled: boolean,
): Promise<ManagedMailAddressInfo> {
  return apiFetch<ManagedMailAddressInfo>(
    `/mail/addresses/${id}/toggle`,
    { method: "PATCH", body: JSON.stringify({ enabled }) },
  );
}

export async function changeAddressPrefix(
  id: number,
  prefix: string,
): Promise<ManagedMailAddressInfo> {
  return apiFetch<ManagedMailAddressInfo>(
    `/mail/addresses/${id}/prefix`,
    { method: "PATCH", body: JSON.stringify({ prefix }) },
  );
}

export async function updateAddress(
  id: number,
  fields: {
    forwardingEnabled?: boolean;
    retentionMs?: number | null;
    quotaBytes?: number;
  },
): Promise<ManagedMailAddressInfo> {
  const body: Record<string, unknown> = {};
  if (fields.forwardingEnabled !== undefined)
    body.forwardingEnabled = fields.forwardingEnabled;
  if (fields.retentionMs !== undefined) body.retentionMs = fields.retentionMs;
  if (fields.quotaBytes !== undefined) body.quotaBytes = fields.quotaBytes;
  return apiFetch<ManagedMailAddressInfo>(`/mail/addresses/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function listAddressAliases(
  id: number,
): Promise<ManagedMailAddressInfo[]> {
  const resp = await apiFetch<{ data: ManagedMailAddressInfo[] }>(
    `/mail/addresses/${id}/aliases`,
  );
  return resp.data;
}

export async function createAddressAlias(
  id: number,
  prefix: string,
): Promise<ManagedMailAddressInfo> {
  return apiFetch<ManagedMailAddressInfo>(
    `/mail/addresses/${id}/aliases`,
    { method: "POST", body: JSON.stringify({ prefix }) },
  );
}

export async function deleteAddressAlias(
  id: number,
  aliasId: number,
): Promise<void> {
  await apiFetch(`/mail/addresses/${id}/aliases/${aliasId}`, {
    method: "DELETE",
  });
}

export async function toggleAddressAlias(
  id: number,
  aliasId: number,
  enabled: boolean,
): Promise<ManagedMailAddressInfo> {
  return apiFetch<ManagedMailAddressInfo>(
    `/mail/addresses/${id}/aliases/${aliasId}/toggle`,
    { method: "PATCH", body: JSON.stringify({ enabled }) },
  );
}

export interface MailAliasInfo {
  id: number;
  primaryMmaId: number | null;
  address: string;
  provisioningStatus: string;
  createdAt: string;
  createdById: number | null;
}

export async function listGroupMail(): Promise<ManagedMailAddressInfo[]> {
  const resp = await apiFetch<{ data: ManagedMailAddressInfo[] }>(
    "/mail/groups",
  );
  return resp.data;
}

export async function createGroupMail(
  groupId: number,
  prefix: string,
): Promise<ManagedMailAddressInfo> {
  return apiFetch<ManagedMailAddressInfo>(`/mail/groups/${groupId}`, {
    method: "POST",
    body: JSON.stringify({ prefix }),
  });
}

export async function deleteGroupMail(groupId: number): Promise<void> {
  await apiFetch(`/mail/groups/${groupId}`, { method: "DELETE" });
}

// ── Function Mail (ManagedMailAddress) ──────────────────────────────────────

export async function listFunctionMail(): Promise<ManagedMailAddressInfo[]> {
  const resp = await apiFetch<{ data: ManagedMailAddressInfo[] }>(
    "/mail/functions",
  );
  return resp.data;
}

export async function createFunctionMail(
  functionId: number,
  prefix: string,
): Promise<ManagedMailAddressInfo> {
  return apiFetch<ManagedMailAddressInfo>(`/mail/functions/${functionId}`, {
    method: "POST",
    body: JSON.stringify({ prefix }),
  });
}

export async function deleteFunctionMail(functionId: number): Promise<void> {
  await apiFetch(`/mail/functions/${functionId}`, { method: "DELETE" });
}

// ── Member Mail (ManagedMailAddress) ──────────────────────────────────────────

export async function listMemberMailMma(): Promise<ManagedMailAddressInfo[]> {
  const resp = await apiFetch<{ data: ManagedMailAddressInfo[] }>(
    "/mail/members-mail",
  );
  return resp.data;
}

export async function createMemberMail(
  memberId: number,
  prefix: string,
): Promise<ManagedMailAddressInfo> {
  return apiFetch<ManagedMailAddressInfo>(`/mail/members-mail/${memberId}`, {
    method: "POST",
    body: JSON.stringify({ prefix }),
  });
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

// ── System address forwarding targets ──────────────────────────────────────

export async function getSystemForwarding(
  addressId: number,
): Promise<string[]> {
  const resp = await apiFetch<{ targets: string[] }>(
    `/mail/system-addresses/${addressId}/forwarding`,
  );
  return resp.targets;
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

export interface WildDuckLiveEntry {
  id: string;
  type: "mailbox" | "alias";
  address: string;
  name: string;
  disabled: boolean;
  targets: string[];
  quotaUsed: number | null;
  quotaTotal: number | null;
  managed: boolean;
  mmaId: number | null;
  kind: string | null;
  linkedId: number | null;
  ownerName: string | null;
}

export async function listWildDuckLive(): Promise<WildDuckLiveEntry[]> {
  const resp = await apiFetch<{ data: WildDuckLiveEntry[] }>(
    "/mail/wildduck-live",
  );
  return resp.data;
}

export async function deleteWildDuckOrphan(
  type: "mailbox" | "alias",
  id: string,
): Promise<void> {
  await apiFetch(`/mail/wildduck-live/${type}/${id}`, { method: "DELETE" });
}

export async function triggerReconcile(): Promise<{
  ok: boolean;
  task: string;
}> {
  return apiFetch<{ ok: boolean; task: string }>("/mail/reconcile", {
    method: "POST",
  });
}
