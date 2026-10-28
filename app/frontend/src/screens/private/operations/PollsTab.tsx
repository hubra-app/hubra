import { useState } from "react";
import {
  Button,
  TextInput,
  Switch,
  Badge,
  Paper,
  Progress,
  MultiSelect,
  ActionIcon,
  Group,
} from "@mantine/core";
import { useForm } from "@mantine/form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useT } from "@/locales/i18n";
import { IconPlus, IconEdit, IconTrash, IconBell } from "@tabler/icons-react";
import { useToast, useData, useAuth } from "@/context/AppContext";
import {
  Modal,
  Field,
  usePagination,
  Pagination,
  ConfirmModal,
} from "@/components/ui";
import type { Poll } from "@/types";
import {
  createPoll,
  updatePoll,
  castVote as apiCastVote,
  deletePoll as apiDeletePoll,
  remindPoll as apiRemindPoll,
  type PollCreate,
  type PollUpdate,
} from "@/api/polls";
import { listGroups } from "@/api/groups";
import { listFunctions } from "@/api/functions";

/* -- Polls ------------------------------------ */
export function PollsTab() {
  const { notify } = useToast();
  const { polls, setPolls, myVotes, setMyVotes } = useData();
  const { hasPermission } = useAuth();
  const { t, i18n } = useT();
  const queryClient = useQueryClient();
  const { data: groups = [] } = useQuery({
    queryKey: ["groups"],
    queryFn: listGroups,
  });
  const { data: functions = [] } = useQuery({
    queryKey: ["functions"],
    queryFn: listFunctions,
  });
  const canCreate = hasPermission("polls.polls.create");
  const canUpdate = hasPermission("polls.polls.update");
  const canDelete = hasPermission("polls.polls.delete");

  const [addOpen, setAddOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Poll | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [options, setOptions] = useState<string[]>(["", ""]);
  const [isRequired, setIsRequired] = useState(false);
  const [requiredGroupIds, setRequiredGroupIds] = useState<number[]>([]);
  const [requiredFunctionIds, setRequiredFunctionIds] = useState<number[]>([]);
  const [remindingPollId, setRemindingPollId] = useState<string | null>(null);
  const [deletingPollId, setDeletingPollId] = useState<string | null>(null);

  const form = useForm({
    initialValues: { question: "", closesAt: "" },
    validate: {
      question: (v: string) =>
        v.trim().length < 1 ? "Question is required" : null,
    },
  });

  const pg = usePagination(polls, 12);

  const castVoteMutation = useMutation({
    mutationFn: ({ pollId, optIdx }: { pollId: string; optIdx: number }) =>
      apiCastVote(pollId, optIdx),
    onMutate: ({ pollId, optIdx }) => {
      const oldOptIdx = myVotes[pollId];
      setMyVotes((prev) => ({ ...prev, [pollId]: optIdx }));
      return { oldOptIdx };
    },
    onSuccess: (updated, { pollId }) => {
      setPolls((prev) => prev.map((p) => (p.id === pollId ? updated : p)));
      notify("success", "Vote cast", "Your vote has been recorded.");
    },
    onError: (err, { pollId }, ctx) => {
      if (ctx?.oldOptIdx !== undefined) {
        setMyVotes((prev) => ({ ...prev, [pollId]: ctx.oldOptIdx }));
      } else {
        setMyVotes((prev) => {
          const n = { ...prev };
          delete n[pollId];
          return n;
        });
      }
      const msg = err instanceof Error ? err.message : "Could not cast vote.";
      notify("error", "Error", msg);
    },
  });

  const deletePollMutation = useMutation({
    mutationFn: (pollId: string) => apiDeletePoll(pollId),
    onMutate: (pollId) => {
      setDeletingPollId(pollId);
      setPolls((prev) => prev.filter((p) => p.id !== pollId));
    },
    onSettled: () => {
      setDeletingPollId(null);
    },
    onError: () => {
      queryClient.invalidateQueries({ queryKey: ["polls"] });
    },
  });

  const remindPollMutation = useMutation({
    mutationFn: (pollId: string) => apiRemindPoll(pollId),
    onMutate: (pollId) => {
      setRemindingPollId(pollId);
    },
    onSettled: () => {
      setRemindingPollId(null);
    },
    onSuccess: (result) => {
      notify("success", "Reminders sent", `${result.sent} reminder(s) sent.`);
    },
    onError: (err) => {
      const msg =
        err instanceof Error ? err.message : "Could not send reminders.";
      notify("error", "Error", msg);
    },
  });

  const handleVote = (pollId: string, optIdx: number) => {
    castVoteMutation.mutate({ pollId, optIdx });
  };

  const resetForm = () => {
    form.reset();
    setOptions(["", ""]);
    setIsRequired(false);
    setRequiredGroupIds([]);
    setRequiredFunctionIds([]);
  };

  const openAdd = () => {
    resetForm();
    setEditTarget(null);
    setAddOpen(true);
  };

  const openEdit = (poll: Poll) => {
    form.setValues({ question: poll.question, closesAt: poll.closesAt ?? "" });
    setOptions(poll.options.map((o) => o.label));
    setIsRequired(poll.isRequired ?? false);
    setRequiredGroupIds(poll.requiredGroupIds ?? []);
    setRequiredFunctionIds(poll.requiredFunctionIds ?? []);
    setEditTarget(poll);
    setAddOpen(true);
  };

  const savePoll = async () => {
    const question = form.values.question.trim();
    if (!question) return;
    const validOptions = options.filter(Boolean);
    if (validOptions.length < 2) {
      notify("error", "Validation", "At least 2 options are required.");
      return;
    }

    setSaving(true);
    try {
      const payload: PollCreate | PollUpdate = {
        question,
        options: validOptions,
        closesAt: form.values.closesAt || undefined,
        isRequired,
        requiredGroupIds: isRequired ? requiredGroupIds : [],
        requiredFunctionIds: isRequired ? requiredFunctionIds : [],
      };

      if (editTarget) {
        const updated = await updatePoll(editTarget.id, payload as PollUpdate);
        setPolls((prev) =>
          prev.map((p) => (p.id === updated.id ? updated : p)),
        );
        notify("success", "Poll updated", "Changes saved.");
      } else {
        const poll = await createPoll(payload as PollCreate);
        setPolls((prev) => [poll, ...prev]);
        notify("success", "Poll created", "Members can now vote.");
      }
      setAddOpen(false);
      resetForm();
    } catch (err: unknown) {
      notify(
        "error",
        "Error",
        err instanceof Error ? err.message : "Unknown error",
      );
    } finally {
      setSaving(false);
    }
  };

  const addOption = () => setOptions((prev) => [...prev, ""]);
  const removeOption = (idx: number) =>
    setOptions((prev) => prev.filter((_, i) => i !== idx));
  const setOption = (idx: number, val: string) =>
    setOptions((prev) => prev.map((v, i) => (i === idx ? val : v)));

  return (
    <div>
      {canCreate && (
        <Group justify="flex-end" mb={16}>
          <Button variant="filled" onClick={openAdd}>
            <IconPlus size={16} />
            {t("polls.createPoll", "New Poll")}
          </Button>
        </Group>
      )}
      <Paper withBorder shadow="sm" radius="lg" style={{ marginBottom: 0 }}>
        <Pagination {...pg} top />
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))",
            gap: 14,
            padding: 16,
          }}
        >
          {pg.paged.map((poll) => {
            const max = Math.max(...poll.options.map((o) => o.votes));
            const voted = myVotes[poll.id];
            const hasVoted = voted !== undefined;
            return (
              <Paper
                key={poll.id}
                withBorder
                shadow="sm"
                radius="lg"
                style={{ padding: 20 }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                    marginBottom: 10,
                    gap: 10,
                  }}
                >
                  <div
                    style={{
                      fontSize: "var(--mantine-font-size-sm)",
                      fontWeight: 600,
                      color: "#181818",
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                    }}
                  >
                    {poll.question}
                    {poll.isRequired && (
                      <Badge
                        variant="light"
                        color="orange"
                        size="xs"
                        radius="xl"
                      >
                        Required
                      </Badge>
                    )}
                  </div>
                  <div style={{ display: "flex", gap: 5, flexShrink: 0 }}>
                    {hasVoted && (
                      <Badge
                        variant="light"
                        color="green"
                        radius="xl"
                        style={{ fontSize: "var(--mantine-font-size-xs)" }}
                      >
                        {t("polls.voted", "Voted")}
                      </Badge>
                    )}
                  </div>
                </div>
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 10,
                    marginBottom: 14,
                  }}
                >
                  {poll.options.map((opt, i) => {
                    const pct =
                      poll.totalVotes > 0
                        ? Math.round((opt.votes / poll.totalVotes) * 100)
                        : 0;
                    const isWinner = opt.votes === max && max > 0;
                    const isMyVote = voted === i;
                    return (
                      <div key={opt.label}>
                        <button
                          onClick={() => handleVote(poll.id, i)}
                          style={{
                            all: "unset",
                            cursor: "pointer",
                            display: "block",
                            width: "100%",
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              marginBottom: 4,
                            }}
                          >
                            <span
                              style={{
                                fontSize: "var(--mantine-font-size-sm)",
                                color: isMyVote ? "#8a6a00" : "#3a4048",
                                fontWeight: isMyVote ? 600 : 400,
                              }}
                            >
                              {opt.label}
                              {isMyVote ? " ✓" : ""}
                            </span>
                            <span
                              className="num"
                              style={{
                                fontSize: "var(--mantine-font-size-sm)",
                                color: isWinner ? "#8a6a00" : "#6b7480",
                                fontWeight: isWinner ? 700 : 400,
                              }}
                            >
                              {pct}%
                            </span>
                          </div>
                          <Progress
                            value={pct}
                            size="sm"
                            radius="xl"
                            styles={{
                              section: {
                                background: isMyVote
                                  ? "#fece2b"
                                  : isWinner
                                    ? "#fece2b88"
                                    : "#e7eeea",
                                transition: "width .4s",
                              },
                            }}
                          />
                        </button>
                      </div>
                    );
                  })}
                </div>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    borderTop: "1px solid #e3eae6",
                    paddingTop: 12,
                  }}
                >
                  <span
                    style={{
                      fontSize: "var(--mantine-font-size-xs)",
                      color: "#6b7480",
                    }}
                  >
                    <span
                      className="num"
                      style={{ fontWeight: 600, color: "#181818" }}
                    >
                      {poll.totalVotes}
                    </span>{" "}
                    {t("polls.votes", "votes")} &middot;{" "}
                    {poll.closesAt
                      ? `${t("polls.closes", "closes")} ${new Date(
                          poll.closesAt,
                        ).toLocaleDateString(i18n.language, {
                          day: "numeric",
                          month: "short",
                        })}`
                      : `${t("polls.closesIn", "closes in")} ${poll.closesIn}d`}
                  </span>
                  <div
                    style={{ display: "flex", gap: 6, alignItems: "center" }}
                  >
                    <Badge variant="light" color="cyan" radius="xl">
                      {poll.status}
                    </Badge>
                    {poll.isRequired && canUpdate && (
                      <ActionIcon
                        size="md"
                        variant="subtle"
                        onClick={() => remindPollMutation.mutate(poll.id)}
                        loading={remindingPollId === poll.id}
                        aria-label="Remind"
                      >
                        <IconBell size={18} />
                      </ActionIcon>
                    )}
                    {canUpdate && (
                      <ActionIcon
                        size="md"
                        variant="subtle"
                        onClick={() => openEdit(poll)}
                        aria-label="Edit"
                      >
                        <IconEdit size={18} />
                      </ActionIcon>
                    )}
                    {canDelete && (
                      <ActionIcon
                        size="md"
                        variant="subtle"
                        color="red"
                        onClick={() => setDeleteTarget(poll.id)}
                        loading={deletingPollId === poll.id}
                        aria-label="Delete"
                      >
                        <IconTrash size={18} />
                      </ActionIcon>
                    )}
                  </div>
                </div>
              </Paper>
            );
          })}
        </div>
        <Pagination {...pg} />
      </Paper>

      <Modal
        open={addOpen}
        onClose={() => {
          setAddOpen(false);
          resetForm();
        }}
        title={editTarget ? "Edit Poll" : "New Poll"}
        footer={
          <>
            <Button
              variant="default"
              onClick={() => {
                setAddOpen(false);
                resetForm();
              }}
            >
              {t("common.cancel")}
            </Button>
            <Button variant="filled" onClick={savePoll} disabled={saving}>
              {editTarget
                ? t("common.save", "Save")
                : t("polls.createPoll", "Create Poll")}
            </Button>
          </>
        }
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <Field label={t("polls.poll.question", "Question")}>
            <TextInput
              {...form.getInputProps("question")}
              placeholder={t(
                "polls.questionPlaceholder",
                "What should we invest in next?",
              )}
            />
          </Field>

          <Field label={t("polls.options", "Options")}>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {options.map((opt, i) => (
                <div
                  key={opt + "-" + i}
                  style={{ display: "flex", gap: 8, alignItems: "center" }}
                >
                  <TextInput
                    value={opt}
                    onChange={(e) => setOption(i, e.target.value)}
                    placeholder={`Option ${i + 1}`}
                    style={{ flex: 1 }}
                  />
                  {options.length > 2 && (
                    <ActionIcon
                      size="sm"
                      variant="subtle"
                      color="red"
                      onClick={() => removeOption(i)}
                      aria-label="Remove option"
                    >
                      <IconTrash size={14} />
                    </ActionIcon>
                  )}
                </div>
              ))}
              <Button variant="subtle" size="sm" onClick={addOption}>
                + Add option
              </Button>
            </div>
          </Field>

          <Field
            label={t(
              "polls.autoCloseDateOptional",
              "Auto-close date (optional)",
            )}
          >
            <TextInput
              type="datetime-local"
              {...form.getInputProps("closesAt")}
            />
          </Field>

          <Field label="Required poll">
            <Switch
              checked={isRequired}
              onChange={(e) => setIsRequired(e.currentTarget.checked)}
              label="Members must vote on this poll"
            />
          </Field>

          {isRequired && (
            <>
              <Field label="Required for groups">
                <MultiSelect
                  data={groups.map((g) => ({
                    value: String(g.id),
                    label: g.name,
                  }))}
                  value={requiredGroupIds.map(String)}
                  onChange={(vals: string[]) =>
                    setRequiredGroupIds(vals.map(Number))
                  }
                  placeholder="Select groups"
                  clearable
                />
              </Field>
              <Field label="Required for functions">
                <MultiSelect
                  data={functions.map((f) => ({
                    value: String(f.id),
                    label: f.name,
                  }))}
                  value={requiredFunctionIds.map(String)}
                  onChange={(vals: string[]) =>
                    setRequiredFunctionIds(vals.map(Number))
                  }
                  placeholder="Select functions"
                  clearable
                />
              </Field>
            </>
          )}
        </div>
      </Modal>
      <ConfirmModal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title={t("polls.deletePollTitle", "Delete poll?")}
        body={t(
          "polls.deletePollBody",
          "All votes will be permanently removed.",
        )}
        onConfirm={() => {
          if (deleteTarget) deletePollMutation.mutate(deleteTarget);
        }}
      />
    </div>
  );
}
