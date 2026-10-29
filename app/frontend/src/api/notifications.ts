import { apiFetch } from '@hubra/api-client';
import type { Notification } from "@/types";

interface BackendNotification {
  id: number;
  kind: "info" | "success" | "warning" | "member";
  title: string;
  msg: string;
  time: string;
  read: boolean;
}

function adapt(b: BackendNotification): Notification {
  return {
    id: String(b.id),
    kind: b.kind,
    title: b.title,
    msg: b.msg,
    time: b.time,
    read: b.read,
  };
}

export async function listNotifications(): Promise<Notification[]> {
  // The API answers { data, meta: { unread } }, not a bare list.
  const { data } = await apiFetch<{ data: BackendNotification[] }>("/notifications/");
  return data.map(adapt);
}

export async function markAllNotificationsRead(): Promise<void> {
  await apiFetch("/notifications/read-all", { method: "POST" });
}

export async function deleteNotification(id: string): Promise<void> {
  await apiFetch(`/notifications/${encodeURIComponent(id)}`, { method: "DELETE" });
}
