import { useMemo } from "react";
import { Badge, Button, Group, Paper, Progress, Text, ThemeIcon } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { useT } from "@/locales/i18n";
import {
  IconCalendar,
  IconChartBar,
  IconHeart,
  IconLogout as Leave,
  IconCreditCard,
} from "@tabler/icons-react";
import { useAuth, useNav } from "@/context/AppContext";
import { useEvents, useMyVotes, usePolls } from "@/data/lists";
import { InvoicePill } from "@/components/ui";
import { listMyInvoices, downloadInvoicePdf } from "@/api/finance";
import { formatCHF } from "@/format";
import { useToggleJoinEvent } from "@/screens/private/operations/useEventActions";
import { useModules } from "@/modules/useModules";
import { MyGroupsCard } from "./MyGroupsCard";
import { PluginSlot } from "@/plugins";
import { qk } from "@/data/keys";

/* -- Account Dashboard ------------------------ */
export function AccountDashboardScreen() {
  const { t, i18n } = useT();
  const { currentUser } = useAuth();
  const { polls } = usePolls();
  const { events } = useEvents();
  const myVotes = useMyVotes();
  const { go, goInvoice } = useNav();
  const joinEventMutation = useToggleJoinEvent();
  const modules = useModules();
  const myId = currentUser?.id ?? "";

  const {
    data: invoicesData,
    isLoading: invoicesLoading,
    isError: invoicesError,
  } = useQuery({
    queryKey: qk.invoices.mine,
    queryFn: () => listMyInvoices(),
  });
  const myInvoices = useMemo(
    () => (invoicesData ?? []).filter((inv) => inv.status !== "Paid"),
    [invoicesData],
  );

  const myEvents = events.filter((ev) => ev.attendees.includes(myId));
  const votedPolls = polls.filter((p) => myVotes[p.id] !== undefined);

  return (
    <>
      {/* pending payments banner */}
      {invoicesError && (
        <Paper withBorder shadow="sm" radius="lg" p="md" mb="md" c="red">
          <Text size="sm">{t("common.error", 'Fehler')}</Text>
        </Paper>
      )}
      {invoicesLoading && (
        <Paper withBorder shadow="sm" radius="lg" p="md" mb="md">
          <Text size="sm" c="dimmed">
            {t("common.loading", 'Wird geladen …')}
          </Text>
        </Paper>
      )}
      {myInvoices.length > 0 && (
        <Paper
          withBorder
          shadow="sm"
          radius="lg"
          style={{
            marginBottom: 16,
            border: "1.5px solid rgba(255, 77, 61, 0.25)",
            background: "rgba(255, 77, 61, 0.04)",
          }}
        >
          <Group
            p="md"
            gap="sm"
            style={{
              borderBottom: "1px solid var(--mantine-color-line-0)",
              background: "transparent",
            }}
          >
            <IconCreditCard
              size={16}
              style={{ color: "var(--mantine-color-red-6)" }}
            />
            <Text
              fw={700}
              fz="md"
              style={{ color: "var(--mantine-color-red-7)" }}
            >
              {t("account.pendingPayment", 'Offene Zahlung')}
              {myInvoices.length !== 1 ? "" : ""}
            </Text>
            <span
              style={{
                marginLeft: "auto",
                fontSize: "var(--mantine-font-size-xs)",
                color: "var(--mantine-color-red-7)",
              }}
            >
              {myInvoices.length} {t("account.invoice", 'Rechnung')}
              {myInvoices.length !== 1 ? "s" : ""}
            </span>
          </Group>
          <div>
            {myInvoices.map((inv) => (
              <div
                key={inv.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "10px 16px",
                  borderTop: "1px solid rgba(255, 77, 61, 0.12)",
                  gap: 12,
                }}
              >
                <div>
                  <div
                    style={{
                      fontSize: "var(--mantine-font-size-sm)",
                      fontWeight: 600,
                      color: "var(--mantine-color-ink-8)",
                    }}
                  >
                    {inv.id}
                  </div>
                  <div
                    style={{
                      fontSize: "var(--mantine-font-size-xs)",
                      color: "var(--mantine-color-ink-4)",
                    }}
                  >
                    {t("account.due", 'Fällig')} {inv.due} · CHF{" "}
                    {formatCHF(inv.amount)}
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <InvoicePill status={inv.status} />
                  <Button
                    size="sm"
                    variant="subtle"
                    onClick={() => downloadInvoicePdf(inv.id)}
                  >
                    {t("finance.downloadQrBill", 'QR-Rechnung herunterladen')}
                  </Button>
                  <Button
                    size="sm"
                    variant="default"
                    onClick={() => goInvoice(inv)}
                  >
                    {t("account.view", 'Ansehen')}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </Paper>
      )}

      {/* stats */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: 12,
          marginBottom: 16,
        }}
      >
        {[
          {
            label: t("account.eventsJoined", 'Angemeldete Anlässe'),
            value: myEvents.length,
            icon: <IconCalendar size={20} />,
            color: "blue",
          },
          {
            label: t("account.pollsVoted", 'Abstimmungen'),
            value: Object.keys(myVotes).length,
            icon: <IconChartBar size={20} />,
            color: "green",
          },
          {
            label: t("account.postsLiked", 'Beiträge mit Like'),
            value: 0,
            icon: <IconHeart size={20} />,
            color: "pink",
          },
        ].map((s) => (
          <Paper
            key={s.label}
            withBorder
            p="md"
            style={{ display: "flex", alignItems: "center", gap: 14 }}
          >
            <ThemeIcon size={44} radius="md" variant="light" color={s.color}>
              {s.icon}
            </ThemeIcon>
            <div style={{ minWidth: 0 }}>
              <Text className="stat-value" fz={26} fw={700} lh={1.1}>
                {s.value}
              </Text>
              <Text fz="sm" c="dimmed" mt={2}>
                {s.label}
              </Text>
            </div>
          </Paper>
        ))}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {/* My events */}
        <Paper withBorder shadow="sm" radius="lg">
          <Group
            p="md"
            gap="sm"
            style={{ borderBottom: "1px solid var(--mantine-color-line-0)" }}
          >
            <IconCalendar
              size={16}
              style={{ color: "var(--mantine-color-ink-4)" }}
            />
            <Text fw={700} fz="md">
              {t("common.myEvents", 'Meine Anlässe')}
            </Text>
            <Button
              size="sm"
              variant="subtle"
              style={{ marginLeft: "auto" }}
              onClick={() => go("/app/operations/events")}
            >
              {t("account.browseEvents", 'Anlässe ansehen')}
            </Button>
          </Group>
          {myEvents.length === 0 ? (
            <div
              style={{
                padding: "20px",
                textAlign: "center",
                color: "var(--mantine-color-ink-3)",
                fontSize: "var(--mantine-font-size-sm)",
              }}
            >
              {t(
                "account.noEventsJoined",
                'Du hast dich noch für keinen Anlass angemeldet.',
              )}
            </div>
          ) : (
            myEvents.map((ev) => {
              const d = new Date(ev.date);
              return (
                <div
                  key={ev.id}
                  style={{
                    display: "flex",
                    gap: 12,
                    padding: "10px 16px",
                    borderBottom: "1px solid var(--mantine-color-line-0)",
                    alignItems: "center",
                  }}
                >
                  <div
                    style={{
                      textAlign: "center",
                      minWidth: 40,
                      background: "var(--mantine-color-surface-1)",
                      borderRadius: 8,
                      padding: "6px 0",
                      flexShrink: 0,
                    }}
                  >
                    <div
                      className="num"
                      style={{
                        fontSize: "var(--mantine-font-size-lg)",
                        fontWeight: 700,
                        color: "var(--mantine-color-ink-8)",
                        lineHeight: 1,
                      }}
                    >
                      {d.getDate()}
                    </div>
                    <div
                      style={{
                        fontSize: 9,
                        fontWeight: 600,
                        color: "var(--mantine-color-ink-3)",
                        letterSpacing: "0.06em",
                      }}
                    >
                      {d
                        .toLocaleString(i18n.language, { month: "short" })
                        .toUpperCase()}
                    </div>
                  </div>
                  <div style={{ flex: 1 }}>
                    <div
                      style={{
                        fontSize: "var(--mantine-font-size-sm)",
                        fontWeight: 600,
                        color: "var(--mantine-color-ink-8)",
                      }}
                    >
                      {ev.title}
                    </div>
                    <div
                      style={{
                        fontSize: "var(--mantine-font-size-xs)",
                        color: "var(--mantine-color-ink-4)",
                      }}
                    >
                      {ev.time}
                      {ev.location ? ` · ${ev.location}` : ""}
                    </div>
                  </div>
                  <Badge variant="light" color="green" radius="xl" size="sm">
                    {t("account.attending", 'Teilnehmende')}
                  </Badge>
                  <Button
                    size="sm"
                    variant="subtle"
                    onClick={() =>
                      joinEventMutation.mutate({
                        eventId: ev.id,
                        eventTitle: ev.title,
                        memberId: currentUser?.id ?? "",
                      })
                    }
                  >
                    <Leave size={16} />
                    {t("account.leave", 'Verlassen')}
                  </Button>
                </div>
              );
            })
          )}
        </Paper>

        {/* My votes */}
        <Paper withBorder shadow="sm" radius="lg">
          <Group
            p="md"
            gap="sm"
            style={{ borderBottom: "1px solid var(--mantine-color-line-0)" }}
          >
            <IconChartBar
              size={16}
              style={{ color: "var(--mantine-color-ink-4)" }}
            />
            <Text fw={700} fz="md">
              {t("account.myVotes", 'Meine Abstimmungen')}
            </Text>
            <Button
              size="sm"
              variant="subtle"
              style={{ marginLeft: "auto" }}
              onClick={() => go("/app/operations/polls")}
            >
              {t("account.allPolls", 'Alle Umfragen')}
            </Button>
          </Group>
          {votedPolls.length === 0 ? (
            <div
              style={{
                padding: "20px",
                textAlign: "center",
                color: "var(--mantine-color-ink-3)",
                fontSize: "var(--mantine-font-size-sm)",
              }}
            >
              {t("account.noPollsVoted", 'Du hast noch an keiner Umfrage teilgenommen.')}
            </div>
          ) : (
            votedPolls.map((poll) => {
              const votedIdx = myVotes[poll.id];
              const max =
                poll.options.length > 0
                  ? Math.max(...poll.options.map((o) => o.votes))
                  : 0;
              return (
                <div
                  key={poll.id}
                  style={{
                    padding: "10px 16px",
                    borderBottom: "1px solid var(--mantine-color-line-0)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "flex-start",
                      marginBottom: 8,
                      gap: 10,
                    }}
                  >
                    <div
                      style={{
                        fontSize: "var(--mantine-font-size-sm)",
                        fontWeight: 600,
                        color: "var(--mantine-color-ink-8)",
                      }}
                    >
                      {poll.question}
                    </div>
                    <Badge variant="light" color="green" radius="xl" size="sm">
                      {t("account.voted", 'Abgestimmt')}
                    </Badge>
                  </div>
                  <div
                    style={{ display: "flex", flexDirection: "column", gap: 6 }}
                  >
                    {poll.options.map((opt, i) => {
                      const pct =
                        poll.totalVotes > 0
                          ? Math.round((opt.votes / poll.totalVotes) * 100)
                          : 0;
                      const isMyVote = votedIdx === i;
                      const isWinner = opt.votes === max && max > 0;
                      return (
                        <div key={opt.label}>
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              marginBottom: 3,
                            }}
                          >
                            <span
                              style={{
                                fontSize: "var(--mantine-font-size-sm)",
                                color: isMyVote ? "#6131c4" : "#5e5873",
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
                                    ? "#7441e055"
                                    : "#ebe8f2",
                                transition: "width .4s",
                              },
                            }}
                          />
                        </div>
                      );
                    })}
                  </div>
                  <div
                    style={{
                      fontSize: "var(--mantine-font-size-xs)",
                      color: "#8c86a0",
                      marginTop: 8,
                    }}
                  >
                    {t("account.votes", { count: poll.totalVotes })}
                    {" · "}
                    {poll.closesAt
                      ? t("account.closesOn", {
                          date: new Date(poll.closesAt).toLocaleDateString(
                            i18n.language,
                            {
                              day: "numeric",
                              month: "short",
                              hour: "2-digit",
                              minute: "2-digit",
                            },
                          ),
                        })
                      : t("account.closesInDays", { days: poll.closesIn })}
                  </div>
                </div>
              );
            })
          )}
        </Paper>

        {modules.has("groups") && <MyGroupsCard />}
        <PluginSlot name="account.cards" />

        {/* My likes ? coming soon */}
        <Paper withBorder shadow="sm" radius="lg">
          <Group
            p="md"
            gap="sm"
            style={{ borderBottom: "1px solid var(--mantine-color-gray-3)" }}
          >
            <IconHeart size={16} style={{ color: "#5e5873" }} />
            <Text fw={700} fz="md">
              {t("account.likedPosts", 'Beiträge, die dir gefallen')}
            </Text>
          </Group>
          <div
            style={{
              padding: "24px",
              textAlign: "center",
              color: "#8c86a0",
              fontSize: "var(--mantine-font-size-sm)",
            }}
          >
            {t("account.postsComingSoon", 'Beiträge folgen bald.')}
          </div>
        </Paper>
      </div>
    </>
  );
}
