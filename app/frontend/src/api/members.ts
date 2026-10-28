import { apiFetch, apiFetchRaw } from '@hubra/api-client';
import { getLookups } from "@/api/lookups";
import type { Member } from "@/types";

interface BackendMember {
  id: number;
  first_name: string;
  last_name: string;
  name: string;
  email: string;
  public_email: string | null;
  tier: { id: number; name: string; color: string | null } | null;
  roles: { id: number; name: string }[];
  group_ids: number[];
  joined: string | null;
  last_seen: string | null;
  status: "active" | "trial" | "inactive" | "suspended";
  is_disabled?: boolean;
  club_username: string | null;
  must_change_password: boolean;
  tool_hours: number;
  notes: string | null;
  avatar_color: string;
  private_email_verified: boolean;
  phone: string | null;
  mobile: string | null;
  birthday: string | null;
  membership_type: string;
  membership_until: string | null;
  emergency_contact: { name?: string; phone?: string; relation?: string } | null;
  custom_fields: Record<string, unknown> | null;
  deleted_at: string | null;
}

interface PagedResponse {
  data: BackendMember[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

function adapt(
  b: BackendMember,
  groupsById: Map<number, { name: string }>,
): Member {
  return {
    id: String(b.id),
    firstName: b.first_name,
    lastName: b.last_name,
    name: b.name,
    email: b.email,
    publicEmail: b.public_email ?? "",
    tier: b.tier?.name ?? "Maker",
    groups: b.group_ids.map((id) => groupsById.get(id)?.name ?? String(id)),
    roles: b.roles?.map((r) => r.name) ?? ["Member"],
    joined: b.joined ?? "",
    lastSeen: b.last_seen ?? "",
    status: b.status,
    isDisabled: b.is_disabled,
    clubUsername: b.club_username,
    mustChangePassword: b.must_change_password,
    toolHours: b.tool_hours,
    notes: b.notes ?? "",
    avatarColor: b.avatar_color,
    privateEmailVerified: b.private_email_verified,
    phone: b.phone ?? "",
    mobile: b.mobile ?? "",
    birthday: b.birthday ?? "",
    membershipType: b.membership_type ?? "regular",
    membershipUntil: b.membership_until ?? "",
    emergencyContact: b.emergency_contact ?? null,
    customFields: b.custom_fields ?? null,
  };
}

export interface MemberFilters {
  search?: string;
  tier?: string;
  status?: string;
  membershipType?: string;
  group?: string;
  sort?: string;
  page?: number;
  pageSize?: number;
  archived?: boolean;
  includeDeleted?: boolean;
}

export async function listMembers(
  filters: MemberFilters = {},
): Promise<{ members: Member[]; total: number }> {
  const params = new URLSearchParams();
  if (filters.search) params.set("search", filters.search);
  if (filters.tier && filters.tier !== "All") params.set("tier", filters.tier);
  if (filters.status && filters.status !== "All")
    params.set("status", filters.status);
  if (filters.membershipType && filters.membershipType !== "All")
    params.set("membership_type", filters.membershipType);
  if (filters.group && filters.group !== "All") params.set("group", filters.group);
  if (filters.sort) params.set("sort", filters.sort);
  if (filters.page) params.set("page", String(filters.page));
  if (filters.pageSize) params.set("pageSize", String(filters.pageSize));
  if (filters.archived) params.set("archived", "1");
  if (filters.includeDeleted) params.set("include_deleted", "1");

  const [resp, lookups] = await Promise.all([
    apiFetch<PagedResponse>(`/members?${params}`),
    getLookups(),
  ]);
  return {
    members: resp.data.map((b) => adapt(b, lookups.groups)),
    total: resp.total,
  };
}

export async function getMember(id: string): Promise<Member> {
  const [b, lookups] = await Promise.all([
    apiFetch<BackendMember>(`/members/${id}`),
    getLookups(),
  ]);
  return adapt(b, lookups.groups);
}

/**
 * Inviting someone: the club never creates or changes an account. The person
 * gets a personal link, signs in or signs up with this address and accepts;
 * the name only greets them in the mail.
 */
export interface MemberInvite {
  email: string;
  firstName?: string;
  lastName?: string;
  tierName?: string;
  groupNames?: string[];
  status?: string;
  membershipType?: string;
  notes?: string;
}

export async function inviteMember(
  input: MemberInvite,
): Promise<{ invited: true; email: string }> {
  const lookups = await getLookups();
  const body: Record<string, unknown> = {
    email: input.email,
    status: input.status ?? "trial",
  };
  if (input.firstName) body.first_name = input.firstName;
  if (input.lastName) body.last_name = input.lastName;
  if (input.tierName) body.tier_id = lookups.tiersByName.get(input.tierName);
  if (input.groupNames?.length)
    body.group_ids = input.groupNames
      .map((n) => lookups.groupsByName.get(n))
      .filter(Boolean);
  if (input.membershipType) body.membership_type = input.membershipType;
  if (input.notes) body.notes = input.notes;
  return apiFetch<{ invited: true; email: string }>("/members/", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** What a club can change: its own data about the member, never the account. */
export interface MemberUpdate {
  status?: string;
  tierName?: string;
  roleNames?: string[];
  groupNames?: string[];
  notes?: string;
  clubUsername?: string | null;
  membershipType?: string;
  membershipUntil?: string;
  customFields?: Record<string, unknown> | null;
}

export async function updateMember(
  id: string,
  input: MemberUpdate,
): Promise<Member> {
  const lookups = await getLookups();
  const body: Record<string, unknown> = {};
  if (input.status) body.status = input.status;
  if (input.tierName !== undefined)
    body.tier_id = lookups.tiersByName.get(input.tierName) ?? null;
  if (input.roleNames !== undefined)
    body.role_ids = input.roleNames
      .map((n) => lookups.rolesByName.get(n))
      .filter(Boolean) as number[];
  if (input.groupNames !== undefined)
    body.group_ids = input.groupNames
      .map((n) => lookups.groupsByName.get(n))
      .filter(Boolean);
  if (input.notes !== undefined) body.notes = input.notes;
  if (input.clubUsername !== undefined) body.club_username = input.clubUsername;
  if (input.membershipType !== undefined)
    body.membership_type = input.membershipType;
  if (input.membershipUntil !== undefined)
    body.membership_until = input.membershipUntil;
  if (input.customFields !== undefined) body.custom_fields = input.customFields;

  const b = await apiFetch<BackendMember>(`/members/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  return adapt(b, lookups.groups);
}

export async function archiveMember(id: string): Promise<void> {
  await apiFetch(`/members/${id}/archive`, { method: "POST" });
}

export async function unarchiveMember(id: string): Promise<Member> {
  const [b, lookups] = await Promise.all([
    apiFetch<BackendMember>(`/members/${id}/unarchive`, { method: "POST" }),
    getLookups(),
  ]);
  return adapt(b, lookups.groups);
}

export async function hardDeleteMember(id: string): Promise<void> {
  await apiFetch(`/members/${id}`, { method: "DELETE" });
}

export async function disableMember(id: string): Promise<Member> {
  const [b, lookups] = await Promise.all([
    apiFetch<BackendMember>(`/members/${id}/disable`, { method: "POST" }),
    getLookups(),
  ]);
  return adapt(b, lookups.groups);
}

export async function enableMember(id: string): Promise<Member> {
  const [b, lookups] = await Promise.all([
    apiFetch<BackendMember>(`/members/${id}/enable`, { method: "POST" }),
    getLookups(),
  ]);
  return adapt(b, lookups.groups);
}

export async function listTierMembers(
  tierId: string,
  search?: string,
): Promise<Member[]> {
  const params = new URLSearchParams();
  if (search) params.set("search", search);
  const [resp, lookups] = await Promise.all([
    apiFetch<{ data: BackendMember[] }>(`/tiers/${tierId}/members?${params}`),
    getLookups(),
  ]);
  return resp.data.map((b) => adapt(b, lookups.groups));
}

export async function listGroupMembers(
  groupId: string,
  search?: string,
): Promise<Member[]> {
  const params = new URLSearchParams();
  if (search) params.set("search", search);
  const [resp, lookups] = await Promise.all([
    apiFetch<{ data: BackendMember[] }>(`/groups/${groupId}/members?${params}`),
    getLookups(),
  ]);
  return resp.data.map((b) => adapt(b, lookups.groups));
}

export async function exportMembersCSV(fields?: string[]): Promise<void> {
  const params = new URLSearchParams();
  if (fields?.length) params.set("fields", fields.join(","));
  const query = params.toString() ? `?${params}` : "";
  const res = await apiFetchRaw(`/members/export${query}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "members.csv";
  a.click();
  URL.revokeObjectURL(url);
}

// ── Leaving the club ──────────────────────────────────────────────────────────

export interface LeaveState {
  /** The club approves requests to leave (club setting). */
  requiresApproval: boolean;
  /** Set while this member's request waits for a club admin. */
  requestedAt: string | null;
}

export interface LeaveRequest {
  id: string;
  name: string;
  email: string;
  avatarColor: string;
  requestedAt: string;
}

export function getMyLeave(): Promise<LeaveState> {
  return apiFetch<LeaveState>("/members/me/leave");
}

export function leaveClub(): Promise<{ status: "left" | "requested" } & Partial<LeaveState>> {
  return apiFetch("/members/me/leave", { method: "POST" });
}

export function withdrawLeaveRequest(): Promise<LeaveState> {
  return apiFetch<LeaveState>("/members/me/leave", { method: "DELETE" });
}

export async function listLeaveRequests(): Promise<LeaveRequest[]> {
  const rows = await apiFetch<(Omit<LeaveRequest, "id"> & { id: number })[]>(
    "/members/leave-requests",
  );
  return rows.map((r) => ({ ...r, id: String(r.id) }));
}

export async function approveLeave(id: string): Promise<void> {
  await apiFetch(`/members/${id}/leave/approve`, { method: "POST" });
}

export async function declineLeave(id: string): Promise<void> {
  await apiFetch(`/members/${id}/leave/decline`, { method: "POST" });
}
