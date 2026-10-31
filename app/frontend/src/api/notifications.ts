import { apiFetch } from '@hubra/api-client';
import type { Notification } from "@/types";

interface BackendNotification {
  id: number;
  kind: "info" | "success" | "warning" | "member";
  title: string;
  msg: string;
  time: string;
  read: boolean;
  link?: string | null;
}

export interface NotificationList {
  items: Notification[];
  /** All unread ones, also those past the newest 100 the list holds. */
  unread: number;
}

function adapt(b: BackendNotification): Notification {
  return {
    id: String(b.id),
    kind: b.kind,
    title: b.title,
    msg: b.msg,
    time: b.time,
    read: b.read,
    link: b.link ?? null,
  };
}

export async function listNotifications(): Promise<NotificationList> {
  const { data, meta } = await apiFetch<{
    data: BackendNotification[];
    meta?: { unread?: number };
  }>("/notifications/");
  const items = data.map(adapt);
  return { items, unread: meta?.unread ?? items.filter((n) => !n.read).length };
}

export async function markNotificationRead(id: string): Promise<void> {
  await apiFetch(`/notifications/${encodeURIComponent(id)}/read`, { method: "PATCH" });
}

export async function markAllNotificationsRead(): Promise<void> {
  await apiFetch("/notifications/read-all", { method: "POST" });
}

export async function deleteNotification(id: string): Promise<void> {
  await apiFetch(`/notifications/${encodeURIComponent(id)}`, { method: "DELETE" });
}

/** Delete the member's own notifications; ``readOnly`` keeps the unread ones. */
export async function clearNotifications(readOnly = false): Promise<void> {
  await apiFetch(`/notifications/${readOnly ? "?read=1" : ""}`, { method: "DELETE" });
}
