import { apiFetch } from '@hubra/api-client';
import type { Application } from "@/types";

interface BackendApplication {
  id: number;
  name: string;
  email: string;
  wants_tier_id: number | null;
  wants_tier_name: string | null;
  applied_at: string;
  avatar_color: string;
}

function adapt(b: BackendApplication): Application {
  return {
    id: String(b.id),
    name: b.name,
    email: b.email,
    wantsTier: b.wants_tier_name ?? String(b.wants_tier_id ?? ""),
    appliedAt: b.applied_at,
    avatarColor: b.avatar_color,
  };
}

export async function listApplications(): Promise<Application[]> {
  const data = await apiFetch<BackendApplication[]>("/applications");
  return data.map(adapt);
}

export async function approveApplication(
  id: string,
  tierId: number,
  role: string,
): Promise<void> {
  await apiFetch(`/applications/${id}/approve`, {
    method: "POST",
    body: JSON.stringify({ tierId, role }),
  });
}

export async function declineApplication(id: string): Promise<void> {
  await apiFetch(`/applications/${id}/decline`, { method: "POST" });
}
