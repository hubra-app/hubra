import { apiFetch } from '@hubra/api-client';
import type { Poll } from "@/types";

interface BackendPollOption {
  id: number;
  label: string;
  vote_count: number;
}

interface BackendPoll {
  id: number;
  question: string;
  options: BackendPollOption[];
  total_votes: number;
  closes_at: string | null;
  status: "open" | "closed";
}

interface BackendPoll {
  id: number;
  question: string;
  options: BackendPollOption[];
  total_votes: number;
  closes_at: string | null;
  status: "open" | "closed";
  created_by_id: number | null;
  is_required: boolean;
  allow_proxy?: boolean;
  auto_close?: boolean;
  max_proxies_per_member?: number;
  required_group_ids: number[] | null;
  required_function_ids: number[] | null;
  my_vote?: number | null;
  may_vote?: boolean;
  group_id?: number | null;
}

function daysLeft(closesAt: string | null): number {
  if (!closesAt) return 7;
  const ms = new Date(closesAt).getTime() - Date.now();
  return Math.max(0, Math.ceil(ms / 86_400_000));
}

function adapt(b: BackendPoll): Poll {
  return {
    id: String(b.id),
    question: b.question,
    options: b.options.map((o) => ({ label: o.label, votes: o.vote_count })),
    totalVotes: b.total_votes,
    closesIn: daysLeft(b.closes_at),
    closesAt: b.closes_at ?? undefined,
    status: b.status,
    createdById: b.created_by_id ? String(b.created_by_id) : undefined,
    isRequired: b.is_required,
    allowProxy: b.allow_proxy ?? false,
    autoClose: b.auto_close ?? false,
    requiredGroupIds: b.required_group_ids ?? undefined,
    requiredFunctionIds: b.required_function_ids ?? undefined,
    myVote: b.my_vote ?? undefined,
    mayVote: b.may_vote ?? true,
    groupId: b.group_id != null ? String(b.group_id) : null,
  };
}

export async function listPolls(): Promise<Poll[]> {
  const data = await apiFetch<BackendPoll[]>("/app/polls");
  return data.map(adapt);
}

export interface PollCreate {
  question: string;
  options: string[];
  closesAt?: string;
  isRequired?: boolean;
  allowProxy?: boolean;
  autoClose?: boolean;
  requiredGroupIds?: number[];
  requiredFunctionIds?: number[];
  /** The group the poll belongs to; empty: the whole club. */
  groupId?: string | null;
}

/** The closing time from a datetime-local field is the club's local time;
 *  sent without a zone, the server read it as UTC (an hour or two late). */
function toInstant(value: string | null | undefined): string | null | undefined {
  if (!value || /(?:[zZ]|[+-]\d\d:?\d\d)$/.test(value)) return value;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toISOString();
}

export async function createPoll(input: PollCreate): Promise<Poll> {
  const b = await apiFetch<BackendPoll>("/app/polls/", {
    method: "POST",
    body: JSON.stringify({
      question: input.question,
      options: input.options.map((label) => ({ label })),
      closes_at: toInstant(input.closesAt) ?? null,
      is_required: input.isRequired ?? false,
      allow_proxy: input.allowProxy ?? false,
      auto_close: input.autoClose ?? false,
      required_group_ids: input.requiredGroupIds ?? null,
      required_function_ids: input.requiredFunctionIds ?? null,
      group_id: input.groupId ? Number(input.groupId) : null,
    }),
  });
  return adapt(b);
}

export interface PollUpdate {
  question?: string;
  options?: string[];
  closesAt?: string | null;
  isRequired?: boolean;
  allowProxy?: boolean;
  autoClose?: boolean;
  requiredGroupIds?: number[] | null;
  requiredFunctionIds?: number[] | null;
  groupId?: string | null;
}

export async function updatePoll(
  id: string,
  input: PollUpdate,
): Promise<Poll> {
  const body: Record<string, unknown> = {};
  if (input.question !== undefined) body.question = input.question;
  if (input.options !== undefined)
    body.options = input.options.map((label) => ({ label }));
  if (input.closesAt !== undefined) body.closes_at = toInstant(input.closesAt);
  if (input.isRequired !== undefined) body.is_required = input.isRequired;
  if (input.allowProxy !== undefined) body.allow_proxy = input.allowProxy;
  if (input.autoClose !== undefined) body.auto_close = input.autoClose;
  if (input.requiredGroupIds !== undefined)
    body.required_group_ids = input.requiredGroupIds;
  if (input.requiredFunctionIds !== undefined)
    body.required_function_ids = input.requiredFunctionIds;
  if (input.groupId !== undefined)
    body.group_id = input.groupId ? Number(input.groupId) : null;

  const b = await apiFetch<BackendPoll>(`/app/polls/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  return adapt(b);
}

export async function castVote(
  pollId: string,
  optionIndex: number,
  onBehalfOf?: number,
): Promise<Poll> {
  const b = await apiFetch<BackendPoll>(`/app/polls/${pollId}/vote`, {
    method: "POST",
    body: JSON.stringify({
      option_index: optionIndex,
      on_behalf_of: onBehalfOf ?? null,
    }),
  });
  return adapt(b);
}

export async function deletePoll(id: string): Promise<void> {
  await apiFetch(`/app/polls/${id}`, { method: "DELETE" });
}

export async function remindPoll(id: string): Promise<{ sent: number }> {
  return apiFetch<{ sent: number }>(`/app/polls/${id}/remind`, {
    method: "POST",
  });
}

export interface ProxyState {
  allow_proxy: boolean;
  max_proxies_per_member: number;
  given_to: { id: number; name: string } | null;
  holding: { id: number; name: string; voted: boolean }[];
}

export async function getProxy(pollId: string): Promise<ProxyState> {
  return apiFetch<ProxyState>(`/app/polls/${pollId}/proxy`);
}

export async function grantProxy(
  pollId: string,
  holderId: number,
): Promise<ProxyState> {
  return apiFetch<ProxyState>(`/app/polls/${pollId}/proxy`, {
    method: "POST",
    body: JSON.stringify({ holder_id: holderId }),
  });
}

export async function revokeProxy(pollId: string): Promise<ProxyState> {
  return apiFetch<ProxyState>(`/app/polls/${pollId}/proxy`, { method: "DELETE" });
}
