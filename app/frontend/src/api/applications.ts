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
  source?: string | null;
}

function adapt(b: BackendApplication): Application {
  return {
    id: String(b.id),
    name: b.name,
    email: b.email,
    wantsTier: b.wants_tier_name ?? String(b.wants_tier_id ?? ""),
    appliedAt: b.applied_at,
    avatarColor: b.avatar_color,
    source: b.source ?? null,
  };
}

export async function listApplications(): Promise<Application[]> {
  const data = await apiFetch<BackendApplication[]>("/app/applications");
  return data.map(adapt);
}

export async function approveApplication(
  id: string,
  tierId: number,
  role: string,
): Promise<{ invited: boolean }> {
  // 202 { invited: true }: the applicant had no account and got an invite.
  const res = await apiFetch<{ invited?: boolean }>(
    `/app/applications/${id}/approve`,
    {
      method: "POST",
      body: JSON.stringify({ tierId, role }),
    },
  );
  return { invited: !!res?.invited };
}

export async function declineApplication(id: string): Promise<void> {
  await apiFetch(`/app/applications/${id}/decline`, { method: "POST" });
}

// ── Posters: a QR code to the join or trial page, with a source tag ─────────

export type PosterKind = "join" | "trial";

export interface PosterLink {
  url: string;
  /** The QR code of *url* (SVG markup from the backend). */
  qrSvg: string;
  source: string | null;
  club: { name: string; slug: string };
}

export function getPoster(kind: PosterKind, source: string): Promise<PosterLink> {
  const q = new URLSearchParams({ kind, source });
  return apiFetch<PosterLink>(`/app/applications/poster?${q}`);
}

export interface SourceCount {
  source: string;
  join: number;
  trial: number;
}

/** Requests to join and trial bookings per poster tag, last 12 months. */
export function listSignupSources(): Promise<SourceCount[]> {
  return apiFetch<SourceCount[]>("/app/applications/sources");
}
