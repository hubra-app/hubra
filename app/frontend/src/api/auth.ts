import { apiFetch } from '@vollbuild/api-client';
import type { Member } from "../types";

interface RawMember {
  id: number;
  first_name: string;
  last_name: string;
  name: string;
  email: string;
  public_email: string | null;
  tier: { name: string } | null;
  roles: { name: string }[];
  status: "active" | "trial" | "inactive" | "suspended";
  tool_hours: number;
  notes: string | null;
  avatar_color: string;
  avatar: string | null;
  profile_note: string | null;
  joined: string | null;
  last_seen: string | null;
  private_email_verified: boolean;
  must_change_password?: boolean;
}

function adaptMember(raw: RawMember): Member {
  return {
    id: String(raw.id),
    firstName: raw.first_name,
    lastName: raw.last_name,
    name: raw.name,
    email: raw.email,
    publicEmail: raw.public_email ?? "",
    tier: (raw.tier?.name ?? "Maker") as Member["tier"],
    roles: raw.roles?.map((r) => r.name) ?? ["Member"],
    status: raw.status,
    toolHours: raw.tool_hours,
    notes: raw.notes ?? "",
    avatarColor: raw.avatar_color,
    avatar: raw.avatar ?? null,
    profileNote: raw.profile_note ?? null,
    groups: [],
    joined: raw.joined ?? "",
    lastSeen: raw.last_seen ?? "",
    privateEmailVerified: raw.private_email_verified,
    mustChangePassword: raw.must_change_password ?? false,
  };
}

interface RawAuthResponse {
  mustChangePassword?: boolean;
  member: RawMember;
}

interface AuthResponse {
  mustChangePassword?: boolean;
  member: Member;
}

export async function login(
  email: string,
  password: string,
  keepSignedIn: boolean = true,
): Promise<AuthResponse> {
  const data = await apiFetch<RawAuthResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password, keepSignedIn }),
  });
  return { ...data, member: adaptMember(data.member) };
}

export async function bootstrap(payload: {
  clubName?: string;
  adminName: string;
  adminEmail: string;
  adminPassword: string;
}): Promise<AuthResponse> {
  const data = await apiFetch<RawAuthResponse>("/auth/bootstrap", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return { ...data, member: adaptMember(data.member) };
}

export async function logout(): Promise<void> {
  await apiFetch("/auth/logout", { method: "POST" }).catch(() => {});
}

export async function getAccount(signal?: AbortSignal): Promise<Member> {
  const raw = await apiFetch<RawMember | { noTenant: true }>("/account/", { signal });
  if (raw && typeof raw === "object" && "noTenant" in raw) {
    throw Object.assign(new Error("noTenant"), { status: 200, noTenant: true });
  }
  return adaptMember(raw as RawMember);
}

export async function getMyPermissions(
  signal?: AbortSignal,
): Promise<{
  is_admin: boolean;
  is_superadmin: boolean;
  permissions: string[];
  impersonation: {
    is_impersonating: boolean;
    impersonator_id: number;
    tenant_slug: string;
    reason: string | null;
    expires_at: string | null;
    restricted_actions: string[];
  } | null;
}> {
  return apiFetch<{
    is_admin: boolean;
    is_superadmin: boolean;
    permissions: string[];
    impersonation: {
      is_impersonating: boolean;
      impersonator_id: number;
      tenant_slug: string;
      reason: string | null;
      expires_at: string | null;
      restricted_actions: string[];
    } | null;
  }>("/account/permissions", { signal });
}

export interface MyTenant {
  tenant_id: number | null;
  tenant_slug: string | null;
  tenant_name: string | null;
  member_id: number | null;
}

export async function getMyTenants(
  signal?: AbortSignal,
): Promise<{ tenants: MyTenant[] }> {
  return apiFetch<{ tenants: MyTenant[] }>("/account/my-tenants", { signal });
}

export async function switchTenant(
  tenantSlug: string,
): Promise<unknown> {
  return apiFetch("/auth/switch-tenant", {
    method: "POST",
    body: JSON.stringify({ tenantSlug }),
  });
}

export async function forgotPassword(email: string): Promise<void> {
  await apiFetch("/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function resetPassword(
  token: string,
  password: string,
): Promise<void> {
  await apiFetch("/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ token, password }),
  });
}

export async function changePassword(
  currentPassword: string,
  newPassword: string,
): Promise<void> {
  await apiFetch("/account/change-password", {
    method: "POST",
    body: JSON.stringify({ currentPassword, newPassword }),
  });
}

export async function updateAccount(fields: {
  first_name?: string;
  last_name?: string;
  email?: string;
  avatar?: string;
  avatar_color?: string;
  profile_note?: string;
  language?: string;
}): Promise<Member> {
  const raw = await apiFetch<RawMember>("/account/", {
    method: "PATCH",
    body: JSON.stringify(fields),
  });
  return adaptMember(raw);
}

export async function getMailSettings(): Promise<{
  forwarding_enabled: boolean;
  private_email_verified: boolean;
}> {
  return apiFetch<{
    forwarding_enabled: boolean;
    private_email_verified: boolean;
  }>("/account/mail-settings");
}

export async function requestEmailVerification(): Promise<void> {
  await apiFetch("/account/request-email-verification", { method: "POST" });
}

export async function updateMailSettings(
  forwardingEnabled: boolean,
): Promise<void> {
  await apiFetch("/account/mail-settings", {
    method: "PATCH",
    body: JSON.stringify({ forwarding_enabled: forwardingEnabled }),
  });
}

export async function getMyGroups(): Promise<{ id: string; name: string }[]> {
  const data =
    await apiFetch<{ id: string; name: string }[]>("/account/groups");
  return data;
}

export async function verifyEmail(
  token: string,
): Promise<{ ok: boolean; verified: boolean }> {
  return apiFetch(`/account/verify-email`, {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

export interface SessionInfo {
  id: number;
  deviceId: number;
  deviceName: string | null;
  browserFamily: string;
  platform: string;
  ipAddress: string;
  userAgent: string;
  createReason: string | null;
  createdAt: string | null;
  lastActiveAt: string | null;
  revokedAt: string | null;
  revokedReason: string | null;
  current: boolean;
}

export async function getSessions(
  includeRevoked = false,
): Promise<SessionInfo[]> {
  const query = includeRevoked ? "?include_revoked=1" : "";
  return apiFetch<SessionInfo[]>(`/account/sessions${query}`);
}

export async function revokeSession(sessionId: number): Promise<void> {
  await apiFetch(`/account/sessions/${sessionId}`, { method: "DELETE" });
}

export async function renameSession(
  sessionId: number,
  name: string | null,
): Promise<SessionInfo> {
  return apiFetch<SessionInfo>(`/account/sessions/${sessionId}`, {
    method: "PATCH",
    body: JSON.stringify({ name }),
  });
}

export async function revokeAllSessions(
  includeCurrent = false,
): Promise<{ ok: boolean; revoked: number }> {
  return apiFetch<{ ok: boolean; revoked: number }>(
    "/account/sessions/revoke-all",
    {
      method: "POST",
      body: JSON.stringify({ includeCurrent: includeCurrent }),
    },
  );
}

export interface DeviceInfo {
  id: number;
  name: string | null;
  browserFamily: string;
  platform: string;
  userAgent: string;
  fingerprint: string;
  createdAt: string | null;
  lastSeenAt: string | null;
  activeSessionCount: number;
  lastActiveAt: string | null;
}

export async function getDevices(): Promise<DeviceInfo[]> {
  return apiFetch<DeviceInfo[]>("/account/devices");
}

export async function renameDevice(
  deviceId: number,
  name: string | null,
): Promise<DeviceInfo> {
  return apiFetch<DeviceInfo>(`/account/devices/${deviceId}`, {
    method: "PATCH",
    body: JSON.stringify({ name }),
  });
}

export async function revokeDeviceSessions(
  deviceId: number,
): Promise<{ ok: boolean; revoked: number }> {
  return apiFetch<{ ok: boolean; revoked: number }>(
    `/account/devices/${deviceId}`,
    { method: "DELETE" },
  );
}
