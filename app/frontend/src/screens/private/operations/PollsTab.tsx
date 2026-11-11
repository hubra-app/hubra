import { useState } from "react";
import {
  Button,
  TextInput,
  Switch,
  Paper,
  MultiSelect,
  ActionIcon,
  Group,
  SimpleGrid,
  Alert,
  Text,
} from "@mantine/core";
import { useForm } from "@mantine/form";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useT } from "@/locales/i18n";
import { IconPlus, IconTrash } from "@tabler/icons-react";
import { useToast, useAuth } from "@/context/AppContext";
import { qk } from "@/data/keys";
import { useListCache, useMyVotes, usePolls } from "@/data/lists";
import {
  Modal,
  Field,
  usePagination,
  Pagination,
  ConfirmModal,
  useLinkedId,
  LinkedEntryBar,
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
import { GroupField } from "./ContentGroupFields";
import { useContentGroups } from "./contentGroups";
import { listFunctions } from "@/api/functions";
import { ProxyPanel } from "./ProxyPanel";
import { PollCard } from "./PollCard";
import { FilterBar } from "@hubra/ui";
import { filterLabels } from "@/components/filterLabels";
import { toLocalInput } from "./localInput";

/* -- Polls ------------------------------------ */

export function PollsTab() {
  const { notify } = useToast();
  const { polls } = usePolls();
  const myVotes = useMyVotes();
  const pollCache = useListCache<Poll>(qk.polls);
  const { currentUser, hasPermission } = useAuth();
  const { t } = useT();
  // Club-wide, or through a role for one group (that group's polls).
  const createScope = useContentGroups("polls.polls.create");
  const updateScope = useContentGroups("polls.polls.update");
  const canCreate = createScope.canAny;
  const canUpdate = updateScope.canAny;
  // Whoever asked the question runs the poll, and a role for its group
  // (the API checks the same).
  const runs = (poll: Poll) =>
    hasPermission("polls.polls.update", poll.groupId ?? undefined) ||
    (currentUser != null && poll.createdById === String(currentUser.id));
  // Only the poll form needs them (and members may not read functions).
  const { data: groups = [] } = useQuery({
    queryKey: qk.groups.all,
    queryFn: listGroups,
    enabled: canCreate || canUpdate,
  });
  const { data: functions = [] } = useQuery({
    queryKey: qk.functions,
    queryFn: listFunctions,
    enabled: canCreate || canUpdate,
  });
  const canDelete = (poll: Poll) =>
    hasPermission("polls.polls.delete", poll.groupId ?? undefined);

  const [addOpen, setAddOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Poll | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [options, setOptions] = useState<string[]>(["", ""]);
  const [isRequired, setIsRequired] = useState(false);
  const [allowProxy, setAllowProxy] = useState(false);
  const [autoClose, setAutoClose] = useState(false);
  const [requiredGroupIds, setRequiredGroupIds] = useState<number[]>([]);
  const [requiredFunctionIds, setRequiredFunctionIds] = useState<number[]>([]);
  const [groupId, setGroupId] = useState("");
  const [remindingPollId, setRemindingPollId] = useState<string | null>(null);
  const [deletingPollId, setDeletingPollId] = useState<string | null>(null);

  const form = useForm({
    initialValues: { question: "", closesAt: "" },
    validate: {
      question: (v: string) =>
        v.trim().length < 1 ? t("validation.questionRequired", "Frage ist erforderlich") : null,
    },
  });

  // ?poll=<id> (from a notification) shows just that poll.
  const linked = useLinkedId("poll");
  const [status, setStatus] = useState<"open" | "closed" | "all">("open");
  const [search, setSearch] = useState("");
  const needsMe = (p: Poll) => p.status === "open" && p.mayVote !== false && myVotes[p.id] === undefined;
  const shownPolls = linked.id
    ? polls.filter((p) => p.id === linked.id)
    : polls
        .filter((p) => (status === "all" || p.status === status))
        .filter((p) => !search.trim() || p.question.toLowerCase().includes(search.trim().toLowerCase()))
        // What still needs the member's vote first, then what closes soonest.
        .sort(
          (a, b) =>
            Number(needsMe(b)) - Number(needsMe(a)) ||
            (a.closesAt ?? "9999").localeCompare(b.closesAt ?? "9999"),
        );
  const openCount = polls.filter((p) => p.status === "open").length;
  const pg = usePagination(shownPolls, 12);

  const castVoteMutation = useMutation({
    mutationFn: ({ pollId, optIdx }: { pollId: string; optIdx: number }) =>
      apiCastVote(pollId, optIdx),
    onMutate: ({ pollId, optIdx }) => {
      const oldOptIdx = myVotes[pollId];
      pollCache.patch(pollId, (p) => ({ ...p, myVote: optIdx }));
      return { oldOptIdx };
    },
    onSuccess: (updated) => {
      pollCache.replace(updated);
      notify("success", t("polls.voteCast", "Stimme abgegeben"), t("polls.voteCastMsg", "Deine Stimme wurde gespeichert."));
    },
    onError: (err, { pollId }, ctx) => {
      pollCache.patch(pollId, (p) => ({ ...p, myVote: ctx?.oldOptIdx }));
      const msg = err instanceof Error ? err.message : t("polls.voteFailed", "Die Stimme konnte nicht abgegeben werden.");
      notify("error", t("common.error", "Fehler"), msg);
    },
  });

  const deletePollMutation = useMutation({
    mutationFn: (pollId: string) => apiDeletePoll(pollId),
    onMutate: (pollId) => {
      setDeletingPollId(pollId);
      pollCache.remove(pollId);
    },
    onSettled: () => {
      setDeletingPollId(null);
    },
    onError: (err) => {
      pollCache.invalidate();
      const msg = err instanceof Error ? err.message : t("polls.deleteFailed", "Die Umfrage konnte nicht gelöscht werden.");
      notify("error", t("common.error", "Fehler"), msg);
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
    setAutoClose(false);
    setRequiredGroupIds([]);
    setRequiredFunctionIds([]);
    setGroupId(createScope.defaultGroup);
  };

  const openAdd = () => {
    resetForm();
    setEditTarget(null);
    setAddOpen(true);
  };

  const openEdit = (poll: Poll) => {
    form.setValues({ question: poll.question, closesAt: toLocalInput(poll.closesAt) });
    setOptions(poll.options.map((o) => o.label));
    setIsRequired(poll.isRequired ?? false);
    setAllowProxy(poll.allowProxy ?? false);
    setAutoClose(poll.autoClose ?? false);
    setRequiredGroupIds(poll.requiredGroupIds ?? []);
    setRequiredFunctionIds(poll.requiredFunctionIds ?? []);
    setGroupId(poll.groupId ?? "");
    setEditTarget(poll);
    setAddOpen(true);
  };

  const savePoll = async () => {
    if (form.validate().hasErrors) return;
    const question = form.values.question.trim();
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
        // An emptied date on edit clears the deadline; a missing key keeps it.
        closesAt: form.values.closesAt
          ? new Date(form.values.closesAt).toISOString()
          : editTarget
            ? null
            : undefined,
        isRequired,
        allowProxy,
        autoClose: isRequired && autoClose,
        requiredGroupIds: isRequired ? requiredGroupIds : [],
        requiredFunctionIds: isRequired ? requiredFunctionIds : [],
        groupId: groupId || null,
      };

      if (editTarget) {
        const updated = await updatePoll(editTarget.id, payload as PollUpdate);
        pollCache.replace(updated);
        notify("success", t("polls.updated", "Umfrage gespeichert"), t("polls.updatedMsg", "Die Änderungen sind gespeichert."));
      } else {
        const poll = await createPoll(payload as PollCreate);
        pollCache.prepend(poll);
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
      {linked.id && (
        <LinkedEntryBar
          label={
            shownPolls.length
              ? t("polls.linkedOne", "Du siehst die Umfrage aus deiner Benachrichtigung.")
              : t("polls.linkedGone", "Diese Umfrage gibt es nicht mehr.")
          }
          onShowAll={linked.clear}
        />
      )}
      <Paper withBorder style={{ marginBottom: 0 }}>
        {!linked.id && (
          <FilterBar
            padded
            search={search}
            onSearchChange={setSearch}
            searchPlaceholder={t("polls.search", "Umfragen durchsuchen …")}
            labels={filterLabels()}
            groups={[
              {
                key: "status",
                label: t("polls.filter.status", "Status"),
                value: status,
                defaultValue: "open",
                options: [
                  { value: "open", label: t("polls.filter.open", "Offen ({{count}})", { count: openCount }) },
                  { value: "closed", label: t("polls.statusClosed", "Beendet") },
                  { value: "all", label: t("common.all", "Alle") },
                ],
                onChange: (v) => setStatus(v as "open" | "closed" | "all"),
              },
            ]}
          />
        )}
        {pg.total > pg.perPage && <Pagination {...pg} top />}
        {pg.paged.length === 0 && (
          <div
            style={{ padding: '48px', textAlign: 'center', color: 'var(--hb-text-3)' }}
          >
            <div style={{ fontSize: 'var(--mantine-font-size-sm)', fontWeight: 500 }}>
              {polls.length > 0
                ? status === "open"
                  ? t('polls.noneOpen', 'Gerade läuft keine Umfrage.')
                  : t('polls.noMatch', 'Keine Umfragen gefunden.')
                : t('polls.empty', 'Noch keine Umfragen.')}
            </div>
            <div style={{ fontSize: 'var(--mantine-font-size-sm)', marginTop: 4, display: polls.length > 0 ? 'none' : undefined }}>
              {canCreate
                ? t('polls.emptyHint', 'Frag den Verein nach seiner Meinung, zum Beispiel zum nächsten Ausflug oder zu einem Termin.')
                : t('polls.emptyMember', 'Sobald der Vorstand eine Umfrage startet, kannst du hier abstimmen.')}
            </div>
          </div>
        )}
        <div
          style={{
            display: pg.paged.length === 0 ? "none" : "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(min(340px, 100%), 1fr))",
            gap: 14,
            padding: 16,
          }}
        >
          {pg.paged.map((poll) => {
            const voted = myVotes[poll.id];
            return (
              <PollCard
                key={poll.id}
                poll={poll}
                voted={voted}
                groupName={createScope.groupName(poll.groupId)}
                runs={runs(poll)}
                voting={castVoteMutation.isPending}
                onVote={(i) => handleVote(poll.id, i)}
                onRemind={poll.isRequired && runs(poll) && poll.status === "open" ? () => remindPollMutation.mutate(poll.id) : undefined}
                reminding={remindingPollId === poll.id}
                onEdit={runs(poll) ? () => openEdit(poll) : undefined}
                onDelete={canDelete(poll) && deletingPollId !== poll.id ? () => setDeleteTarget(poll.id) : undefined}
              >
                {poll.allowProxy && poll.status === "open" && poll.mayVote !== false && (
                  <ProxyPanel
                    poll={poll}
                    hasVoted={voted !== undefined}
                    onPollUpdated={(updated) => pollCache.replace(updated)}
                  />
                )}
              </PollCard>
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
        wide
        title={editTarget ? t("polls.editTitle", "Umfrage bearbeiten") : t("polls.createPoll", "Neue Umfrage")}
        subtitle={editTarget?.question}
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
          {!editTarget && (
            <Alert variant="light" color="violet" p="sm">
              <div style={{ display: "flex", gap: 12, alignItems: "center", justifyContent: "space-between", flexWrap: "wrap" }}>
                <Text size="sm">
                  {t(
                    "polls.resolutionHint",
                    "Ein Beschluss des Vorstands auf dem Zirkularweg? Die Vorlage setzt Ja, Nein und Enthaltung, macht die Umfrage zur Pflicht und schliesst sie, sobald alle abgestimmt haben.",
                  )}
                </Text>
                <Button
                  size="xs"
                  variant="light"
                  color="violet"
                  onClick={() => {
                    setOptions([
                      t("polls.resolutionYes", "Ja"),
                      t("polls.resolutionNo", "Nein"),
                      t("polls.resolutionAbstain", "Enthaltung"),
                    ]);
                    setIsRequired(true);
                    setAutoClose(true);
                  }}
                >
                  {t("polls.resolutionTemplate", "Als Umlaufbeschluss")}
                </Button>
              </div>
            </Alert>
          )}
          <Field label={t("polls.poll.question", 'Frage')}>
            <TextInput
              {...form.getInputProps("question")}
              placeholder={t(
                "polls.questionPlaceholder",
                'Worin sollen wir als Nächstes investieren?',
              )}
            />
          </Field>

          <GroupField
            scope={editTarget ? updateScope : createScope}
            value={groupId}
            onChange={setGroupId}
            hint={t(
              "content.groupHint",
              "Wer eine Rolle für diese Gruppe hat, kann den Eintrag verwalten. Sichtbar bleibt er für alle.",
            )}
          />
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
                {t('polls.addOption', '+ Option hinzufügen')}
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

          <SimpleGrid cols={{ base: 1, sm: 2 }} spacing={12}>
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
          </SimpleGrid>

          {isRequired && (
            <SimpleGrid cols={{ base: 1, sm: 2 }} spacing={12}>
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
            </SimpleGrid>
          )}
          {isRequired && (
            <Switch
              checked={autoClose}
              onChange={(e) => setAutoClose(e.currentTarget.checked)}
              disabled={!requiredGroupIds.length && !requiredFunctionIds.length}
              label={t("polls.autoClose", "Schliessen, sobald alle abgestimmt haben")}
              description={t(
                "polls.autoCloseHint",
                "Für die gewählten Gruppen und Funktionen. Das Ergebnis steht dann gleich fest, auch vor dem Enddatum.",
              )}
            />
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
