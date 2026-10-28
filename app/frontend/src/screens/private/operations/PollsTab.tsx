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
import { ProxyPanel } from "./ProxyPanel";

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
  const [allowProxy, setAllowProxy] = useState(false);
  const [requiredGroupIds, setRequiredGroupIds] = useState<number[]>([]);
  const [requiredFunctionIds, setRequiredFunctionIds] = useState<number[]>([]);
  const [remindingPollId, setRemindingPollId] = useState<string | null>(null);
  const [deletingPollId, setDeletingPollId] = useState<string | null>(null);

  const form = useForm({
    initialValues: { question: "", closesAt: "" },
    validate: {
      question: (v: string) =>
        v.trim().length < 1 ? t("validation.questionRequired", "Frage ist erforderlich") : null,
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
      notify("success", t("polls.voteCast", "Stimme abgegeben"), t("polls.voteCastMsg", "Deine Stimme wurde gespeichert."));
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
      const msg = err instanceof Error ? err.message : t("polls.voteFailed", "Die Stimme konnte nicht abgegeben werden.");
      notify("error", t("common.error", "Fehler"), msg);
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
      notify("success", t("polls.remindersSent", "Erinnerungen gesendet"), t("polls.remindersSentMsg", "{{count}} Erinnerungen gesendet.", { count: result.sent }));
    },
    onError: (err) => {
      const msg =
        err instanceof Error ? err.message : t("polls.remindersFailed", "Die Erinnerungen konnten nicht gesendet werden.");
      notify("error", t("common.error", "Fehler"), msg);
    },
  });

  const handleVote = (pollId: string, optIdx: number) => {
    castVoteMutation.mutate({ pollId, optIdx });
  };

  const resetForm = () => {
    form.reset();
    setOptions(["", ""]);
    setIsRequired(false);
    setAllowProxy(false);
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
    setAllowProxy(poll.allowProxy ?? false);
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
      notify("error", t("polls.validation", "Eingabe prüfen"), t("polls.minOptions", "Es braucht mindestens 2 Optionen."));
      return;
    }

    setSaving(true);
    try {
      const payload: PollCreate | PollUpdate = {
        question,
        options: validOptions,
        closesAt: form.values.closesAt || undefined,
        isRequired,
        allowProxy,
        requiredGroupIds: isRequired ? requiredGroupIds : [],
        requiredFunctionIds: isRequired ? requiredFunctionIds : [],
      };

      if (editTarget) {
        const updated = await updatePoll(editTarget.id, payload as PollUpdate);
        setPolls((prev) =>
          prev.map((p) => (p.id === updated.id ? updated : p)),
        );
        notify("success", t("polls.updated", "Umfrage gespeichert"), t("polls.updatedMsg", "Die Änderungen sind gespeichert."));
      } else {
        const poll = await createPoll(payload as PollCreate);
        setPolls((prev) => [poll, ...prev]);
        notify("success", t("polls.created", "Umfrage erstellt"), t("polls.createdMsg", "Die Mitglieder können jetzt abstimmen."));
      }
      setAddOpen(false);
      resetForm();
    } catch (err: unknown) {
      notify(
        "error",
        t("common.error", "Fehler"),
        err instanceof Error ? err.message : t("common.unknownError", "Unbekannter Fehler"),
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
        <Group justify="flex-end" mb={16} className="page-actions">
          <Button variant="filled" onClick={openAdd}>
            <IconPlus size={16} />
            {t("polls.createPoll", 'Neue Umfrage')}
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
                      color: "#1a1625",
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
                        {t("polls.requiredBadge", "Pflicht")}
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
                        {t("polls.voted", 'Abgestimmt')}
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
                                color: isMyVote ? "#6131c4" : "#2e2940",
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
                                color: isWinner ? "#6131c4" : "#5e5873",
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
                                  ? "#7441e0"
                                  : isWinner
                                    ? "#7441e088"
                                    : "#ebe8f2",
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
                    borderTop: "1px solid #e6e3ef",
                    paddingTop: 12,
                  }}
                >
                  <span
                    style={{
                      fontSize: "var(--mantine-font-size-xs)",
                      color: "#5e5873",
                    }}
                  >
                    <span
                      className="num"
                      style={{ fontWeight: 600, color: "#1a1625" }}
                    >
                      {poll.totalVotes}
                    </span>{" "}
                    {t("polls.votes", 'Stimmen')} &middot;{" "}
                    {poll.closesAt
                      ? `${t("polls.closes", 'endet')} ${new Date(
                          poll.closesAt,
                        ).toLocaleDateString(i18n.language, {
                          day: "numeric",
                          month: "short",
                        })}`
                      : `${t("polls.closesIn", 'endet in')} ${poll.closesIn}d`}
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
                        aria-label={t('polls.remind', 'Erinnern')}
                      >
                        <IconBell size={18} />
                      </ActionIcon>
                    )}
                    {canUpdate && (
                      <ActionIcon
                        size="md"
                        variant="subtle"
                        onClick={() => openEdit(poll)}
                        aria-label={t('common.edit', 'Bearbeiten')}
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
                        aria-label={t('common.delete', 'Löschen')}
                      >
                        <IconTrash size={18} />
                      </ActionIcon>
                    )}
                  </div>
                </div>
                {poll.allowProxy && poll.status === "open" && (
                  <ProxyPanel
                    poll={poll}
                    hasVoted={hasVoted}
                    onPollUpdated={(updated) =>
                      setPolls((prev) =>
                        prev.map((p) => (p.id === updated.id ? updated : p)),
                      )
                    }
                  />
                )}
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
        title={editTarget ? t("polls.editTitle", "Umfrage bearbeiten") : t("polls.createPoll", "Neue Umfrage")}
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
                ? t("common.save", 'Speichern')
                : t("polls.createPoll", 'Neue Umfrage')}
            </Button>
          </>
        }
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <Field label={t("polls.poll.question", 'Frage')}>
            <TextInput
              {...form.getInputProps("question")}
              placeholder={t(
                "polls.questionPlaceholder",
                'Worin sollen wir als Nächstes investieren?',
              )}
            />
          </Field>

          <Field label={t("polls.options", 'Optionen')}>
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
                      aria-label={t('polls.removeOption', 'Option entfernen')}
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
              'Automatisch beenden am (optional)',
            )}
          >
            <TextInput
              type="datetime-local"
              {...form.getInputProps("closesAt")}
            />
          </Field>

          <Field label={t("polls.proxy.field", 'Stellvertretung')}>
            <Switch
              checked={allowProxy}
              onChange={(e) => setAllowProxy(e.currentTarget.checked)}
              label={t(
                "polls.proxy.allow",
                'Mitglieder dürfen ihre Stimme einem anderen Mitglied übertragen',
              )}
            />
          </Field>

          <Field label={t('polls.required', 'Pflicht-Umfrage')}>
            <Switch
              checked={isRequired}
              onChange={(e) => setIsRequired(e.currentTarget.checked)}
              label={t('polls.requiredHint', 'Mitglieder müssen an dieser Umfrage teilnehmen')}
            />
          </Field>

          {isRequired && (
            <>
              <Field label={t('polls.requiredGroups', 'Pflicht für Gruppen')}>
                <MultiSelect
                  data={groups.map((g) => ({
                    value: String(g.id),
                    label: g.name,
                  }))}
                  value={requiredGroupIds.map(String)}
                  onChange={(vals: string[]) =>
                    setRequiredGroupIds(vals.map(Number))
                  }
                  placeholder={t('polls.selectGroups', 'Gruppen wählen')}
                  clearable
                />
              </Field>
              <Field label={t('polls.requiredFunctions', 'Pflicht für Funktionen')}>
                <MultiSelect
                  data={functions.map((f) => ({
                    value: String(f.id),
                    label: f.name,
                  }))}
                  value={requiredFunctionIds.map(String)}
                  onChange={(vals: string[]) =>
                    setRequiredFunctionIds(vals.map(Number))
                  }
                  placeholder={t('polls.selectFunctions', 'Funktionen wählen')}
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
        title={t("polls.deletePollTitle", 'Umfrage löschen?')}
        body={t(
          "polls.deletePollBody",
          'Alle Stimmen werden endgültig gelöscht.',
        )}
        onConfirm={() => {
          if (deleteTarget) deletePollMutation.mutate(deleteTarget);
        }}
      />
    </div>
  );
}
