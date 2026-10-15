import { apiFetch } from '@vollbuild/api-client';
import type { ClubEvent } from "@/types";

interface BackendEvent {
  id: number;
  title: string;
  date: string;
  time: string | null;
  location: string | null;
  type: "Workshop" | "Social" | "Certification" | "Meeting";
  attendee_ids: number[];
  description: string | null;
  meeting_url: string | null;
  end_date: string | null;
  all_day: boolean;
  category: string;
  max_attendees: number | null;
  requires_approval: boolean;
  is_public: boolean;
  cover_image_url: string | null;
  color: string | null;
  registration_count: number;
}

function adapt(b: BackendEvent): ClubEvent {
  return {
    id: String(b.id),
    title: b.title,
    date: b.date,
    time: b.time ?? "",
    location: b.location ?? "",
    type: b.type,
    attendees: b.attendee_ids.map(String),
    description: b.description ?? "",
    meetingUrl: b.meeting_url ?? "",
    endDate: b.end_date ?? "",
    allDay: b.all_day ?? false,
    category: b.category ?? "general",
    maxAttendees: b.max_attendees ?? null,
    requiresApproval: b.requires_approval ?? false,
    isPublic: b.is_public ?? false,
    coverImageUrl: b.cover_image_url ?? null,
    color: b.color ?? null,
    registrationCount: b.registration_count ?? 0,
  };
}

export async function listEvents(
  params?: { from?: string; to?: string; type?: string; category?: string },
): Promise<ClubEvent[]> {
  const qs = new URLSearchParams();
  if (params?.from) qs.set("from", params.from);
  if (params?.to) qs.set("to", params.to);
  if (params?.type) qs.set("type", params.type);
  if (params?.category) qs.set("category", params.category);
  const suffix = qs.toString() ? `?${qs}` : "";
  const data = await apiFetch<BackendEvent[]>(`/events${suffix}`);
  return data.map(adapt);
}

export interface EventCreate {
  title: string;
  date: string;
  time?: string;
  location?: string;
  type: string;
  description?: string;
  meetingUrl?: string;
  endDate?: string;
  allDay?: boolean;
  category?: string;
  maxAttendees?: number | null;
  requiresApproval?: boolean;
  isPublic?: boolean;
  coverImageUrl?: string;
  color?: string;
}

export async function createEvent(input: EventCreate): Promise<ClubEvent> {
  const body: Record<string, unknown> = {
    title: input.title,
    date: input.date,
    type: input.type,
  };
  if (input.time !== undefined) body.time = input.time;
  if (input.location !== undefined) body.location = input.location;
  if (input.description !== undefined) body.description = input.description;
  if (input.meetingUrl !== undefined) body.meeting_url = input.meetingUrl;
  if (input.endDate !== undefined) body.end_date = input.endDate;
  if (input.allDay !== undefined) body.all_day = input.allDay;
  if (input.category !== undefined) body.category = input.category;
  if (input.maxAttendees !== undefined) body.max_attendees = input.maxAttendees;
  if (input.requiresApproval !== undefined) body.requires_approval = input.requiresApproval;
  if (input.isPublic !== undefined) body.is_public = input.isPublic;
  if (input.coverImageUrl !== undefined) body.cover_image_url = input.coverImageUrl;
  if (input.color !== undefined) body.color = input.color;

  const b = await apiFetch<BackendEvent>("/events/", {
    method: "POST",
    body: JSON.stringify(body),
  });
  return adapt(b);
}

export type EventUpdate = Partial<EventCreate>;

export async function updateEvent(
  id: string,
  input: EventUpdate,
): Promise<ClubEvent> {
  const body: Record<string, unknown> = {};
  if (input.title !== undefined) body.title = input.title;
  if (input.date !== undefined) body.date = input.date;
  if (input.time !== undefined) body.time = input.time;
  if (input.location !== undefined) body.location = input.location;
  if (input.type !== undefined) body.type = input.type;
  if (input.description !== undefined) body.description = input.description;
  if (input.meetingUrl !== undefined) body.meeting_url = input.meetingUrl;
  if (input.endDate !== undefined) body.end_date = input.endDate;
  if (input.allDay !== undefined) body.all_day = input.allDay;
  if (input.category !== undefined) body.category = input.category;
  if (input.maxAttendees !== undefined) body.max_attendees = input.maxAttendees;
  if (input.requiresApproval !== undefined) body.requires_approval = input.requiresApproval;
  if (input.isPublic !== undefined) body.is_public = input.isPublic;
  if (input.coverImageUrl !== undefined) body.cover_image_url = input.coverImageUrl;
  if (input.color !== undefined) body.color = input.color;

  const b = await apiFetch<BackendEvent>(`/events/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  return adapt(b);
}

export async function deleteEvent(id: string): Promise<void> {
  await apiFetch(`/events/${id}`, { method: "DELETE" });
}

export async function joinEvent(
  eventId: string,
  memberId: string,
): Promise<void> {
  await apiFetch(`/events/${eventId}/attendees/${memberId}`, {
    method: "POST",
  });
}

export async function leaveEvent(
  eventId: string,
  memberId: string,
): Promise<void> {
  await apiFetch(`/events/${eventId}/attendees/${memberId}`, {
    method: "DELETE",
  });
}

export interface EventRegistration {
  id: number;
  eventId: number;
  memberId: number;
  memberName: string | null;
  status: string;
  registeredAt: string;
  cancelledAt: string | null;
  attendedAt: string | null;
  notes: string | null;
  guests: number;
}
