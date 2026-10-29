import { apiFetch } from '@hubra/api-client';

export interface SerializedPost {
  id: number;
  title: string;
  summary: string | null;
  body: string;
  created_at: string;
  author_name: string | null;
  author_avatar_color: string | null;
  like_count: number;
  comment_count: number;
}

export interface DashboardSummary {
  stats: {
    activeMembers: number;
    memberDelta: number;
    // null when the member may not see the finance overview
    netMonth: number | null;
    openInvoices: number | null;
    openInvoicesAmount: number | null;
    upcomingEvents: number;
  };
  growth: number[];
  upcomingEvents: {
    id: number;
    title: string;
    date: string;
    time: string | null;
    location: string | null;
    type: string;
    attendee_ids: number[];
  }[];
  posts: SerializedPost[];
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
  return apiFetch<DashboardSummary>("/dashboard/summary");
}
