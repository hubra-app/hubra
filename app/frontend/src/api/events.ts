import { apiFetch, apiFetchRaw } from '@hubra/api-client';
import type { ClubEvent, Recurrence } from "@/types";

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
  places_taken?: number;
  pending_count?: number;
  my_status?: string | null;
  group_id?: number | null;
  series_id?: number | null;
  series_date?: string | null;
  recurrence?: BackendRecurrence | null;
}

interface BackendRecurrence {
  start_date?: string;
  until: string;
  interval: number;
  weekdays: number[];
  skip_dates: string[];
}

export type { Recurrence };

function adaptRecurrence(r: BackendRecurrence): Recurrence {
  return {
    startDate: r.start_date,
    until: r.until,
    interval: r.interval,
    weekdays: r.weekdays,
    skipDates: r.skip_dates,
  };
}

function recurrenceBody(r: Recurrence) {
  return {
    until: r.until,
    interval: r.interval,
    weekdays: r.weekdays,
    skip_dates: r.skipDates,
  };
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
    placesTaken: b.places_taken ?? b.registration_count ?? 0,
    pendingCount: b.pending_count ?? 0,
    myStatus: (b.my_status ?? null) as ClubEvent["myStatus"],
    groupId: b.group_id != null ? String(b.group_id) : null,
    seriesId: b.series_id != null ? String(b.series_id) : null,
    seriesDate: b.series_date ?? null,
    recurrence: b.recurrence ? adaptRecurrence(b.recurrence) : null,
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
  /** The group the event is for (its members are expected). */
  groupId?: string | null;
  /** Repeat weekly (new events; edits with scope "following"). */
  recurrence?: Recurrence;
}

/** For a date of a series: just this one, or it and all later ones. */
export type SeriesScope = "this" | "following";

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
  if (input.groupId !== undefined)
    body.group_id = input.groupId ? Number(input.groupId) : null;
  if (input.recurrence) body.recurrence = recurrenceBody(input.recurrence);

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
  scope: SeriesScope = "this",
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
  if (input.groupId !== undefined)
    body.group_id = input.groupId ? Number(input.groupId) : null;
  if (input.recurrence) body.recurrence = recurrenceBody(input.recurrence);

  const suffix = scope === "following" ? "?scope=following" : "";
  const b = await apiFetch<BackendEvent>(`/events/${id}${suffix}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  return adapt(b);
}

export async function deleteEvent(
  id: string,
  scope: SeriesScope = "this",
): Promise<void> {
  const suffix = scope === "following" ? "?scope=following" : "";
  await apiFetch(`/events/${id}${suffix}`, { method: "DELETE" });
}

// The signed-in member signs up or gives up their place. This goes through
// registration (capacity, waitlist, deadlines) and needs only the member's
// own "register" right; /attendees/<id> is the organisers' list. The member
// id stays in the signature for the callers; the server takes the signed-in
// member.
export async function joinEvent(
  eventId: string,
  memberId: string,
): Promise<string> {
  void memberId;
  // "registered", "approved", "waitlisted", or "pending" (needs approval).
  const reg = await apiFetch<{ status: string }>(`/events/${eventId}/register`, {
    method: "POST",
    body: JSON.stringify({}),
  });
  return reg.status;
}

export async function leaveEvent(
  eventId: string,
  memberId: string,
): Promise<void> {
  void memberId;
  await apiFetch(`/events/${eventId}/cancel-registration`, {
    method: "POST",
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

interface BackendRegistration {
  id: number;
  event_id: number;
  member_id: number;
  member_name: string | null;
  status: string;
  registered_at: string;
  cancelled_at: string | null;
  attended_at: string | null;
  notes: string | null;
  guests: number;
}

function adaptRegistration(r: BackendRegistration): EventRegistration {
  return {
    id: r.id,
    eventId: r.event_id,
    memberId: r.member_id,
    memberName: r.member_name,
    status: r.status,
    registeredAt: r.registered_at,
    cancelledAt: r.cancelled_at,
    attendedAt: r.attended_at,
    notes: r.notes,
    guests: r.guests,
  };
}

/** Organisers: an event's sign-ups, e.g. those waiting for approval. */
export async function listRegistrations(
  eventId: string,
  status?: string,
): Promise<EventRegistration[]> {
  const suffix = status ? `?status=${encodeURIComponent(status)}` : "";
  const data = await apiFetch<BackendRegistration[]>(
    `/events/${eventId}/registrations${suffix}`,
  );
  return data.map(adaptRegistration);
}

/** Organisers: approve or decline a sign-up that waits for approval. */
export async function decideRegistration(
  eventId: string,
  memberId: number,
  decision: "approve" | "decline",
): Promise<EventRegistration> {
  const r = await apiFetch<BackendRegistration>(
    `/events/${eventId}/registrations/${memberId}/${decision}`,
    { method: "POST" },
  );
  return adaptRegistration(r);
}

export async function getCalendarFeedUrl(): Promise<string> {
  const data = await apiFetch<{ url: string }>("/events/calendar/feed");
  return data.url;
}

// ── Attendance ───────────────────────────────────────────────────────────────

export type AttendanceStatus = "present" | "excused" | "absent";

export interface RollEntry {
  memberId: number;
  memberName: string;
  /** The member's sign-up, if any. */
  registrationStatus: string | null;
  /** What was recorded; null when nothing yet. */
  status: AttendanceStatus | null;
}

interface BackendRollEntry {
  member_id: number;
  member_name: string;
  registration_status: string | null;
  status: AttendanceStatus | null;
}

const adaptRoll = (rows: BackendRollEntry[]): RollEntry[] =>
  rows.map((r) => ({
    memberId: r.member_id,
    memberName: r.member_name,
    registrationStatus: r.registration_status,
    status: r.status,
  }));

/** The roll of one event: the group's members and whoever signed up. */
export async function getRoll(eventId: string): Promise<RollEntry[]> {
  return adaptRoll(
    await apiFetch<BackendRollEntry[]>(`/events/${eventId}/attendance`),
  );
}

export async function saveRoll(
  eventId: string,
  entries: { memberId: number; status: AttendanceStatus | null }[],
): Promise<RollEntry[]> {
  return adaptRoll(
    await apiFetch<BackendRollEntry[]>(`/events/${eventId}/attendance`, {
      method: "PUT",
      body: JSON.stringify({
        entries: entries.map((e) => ({ member_id: e.memberId, status: e.status })),
      }),
    }),
  );
}

export interface AttendanceSummary {
  present: number;
  excused: number;
  absent: number;
  expected: number;
  /** present / expected, or null when nobody was expected. */
  rate: number | null;
}

export interface AttendanceOverview {
  from: string;
  to: string;
  events: {
    id: number;
    title: string;
    date: string;
    time: string | null;
    groupId: number | null;
    seriesId: number | null;
    recorded: boolean;
    present: number;
  }[];
  members: (AttendanceSummary & {
    memberId: number;
    name: string;
    birthday: string | null;
    /** Per event id; events the member was not expected at are missing. */
    statuses: Record<string, AttendanceStatus>;
  })[];
  total: AttendanceSummary;
}

export interface AttendanceFilter {
  from: string;
  to: string;
  groupId?: string;
  category?: string;
}

function overviewPath(f: AttendanceFilter, csv = false) {
  const qs = new URLSearchParams({ from: f.from, to: f.to });
  if (f.category) qs.set("category", f.category);
  if (csv) qs.set("format", "csv");
  return f.groupId
    ? `/events/attendance/groups/${f.groupId}?${qs}`
    : `/events/attendance?${qs}`;
}

/** Attendance per member over the events of a period. */
export async function getAttendanceOverview(
  f: AttendanceFilter,
): Promise<AttendanceOverview> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const b = await apiFetch<any>(overviewPath(f));
  return {
    from: b.from,
    to: b.to,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    events: b.events.map((e: any) => ({
      id: e.id,
      title: e.title,
      date: e.date,
      time: e.time,
      groupId: e.group_id,
      seriesId: e.series_id,
      recorded: e.recorded,
      present: e.present,
    })),
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    members: b.members.map((m: any) => ({
      memberId: m.member_id,
      name: m.name,
      birthday: m.birthday,
      statuses: m.statuses,
      present: m.present,
      excused: m.excused,
      absent: m.absent,
      expected: m.expected,
      rate: m.rate,
    })),
    total: b.total,
  };
}

/** The same as a sheet (semicolons, for Excel and J+S). */
export async function downloadAttendanceCSV(f: AttendanceFilter): Promise<void> {
  const res = await apiFetchRaw(overviewPath(f, true));
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `anwesenheit-${f.from}-${f.to}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}
