import { apiFetch } from '@vollbuild/api-client';
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
  required_group_ids: number[] | null;
  required_function_ids: number[] | null;
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
    requiredGroupIds: b.required_group_ids ?? undefined,
    requiredFunctionIds: b.required_function_ids ?? undefined,
  };
}

export async function listPolls(): Promise<Poll[]> {
  const data = await apiFetch<BackendPoll[]>("/polls");
  return data.map(adapt);
}

export interface PollCreate {
  question: string;
  options: string[];
  closesAt?: string;
  isRequired?: boolean;
  requiredGroupIds?: number[];
  requiredFunctionIds?: number[];
}

export async function createPoll(input: PollCreate): Promise<Poll> {
  const b = await apiFetch<BackendPoll>("/polls/", {
    method: "POST",
    body: JSON.stringify({
      question: input.question,
      options: input.options.map((label) => ({ label })),
      closes_at: input.closesAt ?? null,
      is_required: input.isRequired ?? false,
      required_group_ids: input.requiredGroupIds ?? null,
      required_function_ids: input.requiredFunctionIds ?? null,
    }),
  });
  return adapt(b);
}

export interface PollUpdate {
  question?: string;
  options?: string[];
  closesAt?: string | null;
  isRequired?: boolean;
  requiredGroupIds?: number[] | null;
  requiredFunctionIds?: number[] | null;
}

export async function updatePoll(
  id: string,
  input: PollUpdate,
): Promise<Poll> {
  const body: Record<string, unknown> = {};
  if (input.question !== undefined) body.question = input.question;
  if (input.options !== undefined)
    body.options = input.options.map((label) => ({ label }));
  if (input.closesAt !== undefined) body.closes_at = input.closesAt;
  if (input.isRequired !== undefined) body.is_required = input.isRequired;
  if (input.requiredGroupIds !== undefined)
    body.required_group_ids = input.requiredGroupIds;
  if (input.requiredFunctionIds !== undefined)
    body.required_function_ids = input.requiredFunctionIds;

  const b = await apiFetch<BackendPoll>(`/polls/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  return adapt(b);
}

export async function castVote(
  pollId: string,
  optionIndex: number,
): Promise<Poll> {
  const b = await apiFetch<BackendPoll>(`/polls/${pollId}/vote`, {
    method: "POST",
    body: JSON.stringify({ option_index: optionIndex }),
  });
  return adapt(b);
}

export async function deletePoll(id: string): Promise<void> {
  await apiFetch(`/polls/${id}`, { method: "DELETE" });
}

export async function remindPoll(id: string): Promise<{ sent: number }> {
  return apiFetch<{ sent: number }>(`/polls/${id}/remind`, {
    method: "POST",
  });
}
