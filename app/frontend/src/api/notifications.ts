import { apiFetch } from '@vollbuild/api-client';
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
  const data = await apiFetch<BackendNotification[]>("/notifications/");
  return data.map(adapt);
}

export async function markNotificationRead(id: string): Promise<void> {
  await apiFetch(`/notifications/${id}/read`, { method: "PATCH" });
}

export async function markAllNotificationsRead(): Promise<void> {
  await apiFetch("/notifications/read-all", { method: "POST" });
}
