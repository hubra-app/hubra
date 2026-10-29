import { Badge, Button, Group, Text, UnstyledButton } from "@mantine/core";
import { EVENT_TYPE_COLORS } from "@/constants";
import { useQuery } from "@tanstack/react-query";
import { useT } from "@/locales/i18n";
import { useNav, useData } from "@/context/AppContext";
import { StatTile, Card, StatGrid, Avatar } from "@/components/ui";
import { getDashboardSummary } from "@/api/dashboard";
import { listEvents } from "@/api/events";
import { listPolls } from "@/api/polls";
import { formatCHFCompact } from "@/format";

function fmtNet(n: number): string {
  const sign = n >= 0 ? "+" : "\u2212";
  return `${sign}CHF ${formatCHFCompact(Math.abs(n))}`;
}

export function GlobalOverviewScreen() {
  const { t, i18n } = useT();
  const { go } = useNav();
  const { myVotes } = useData();
  const {
    data: summary,
    isLoading: summaryLoading,
    isError: summaryError,
  } = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: () => getDashboardSummary(),
  });
  const { data: events = [] } = useQuery({
    queryKey: ["events"],
    queryFn: () => listEvents(),
  });
  const { data: polls = [] } = useQuery({
    queryKey: ["polls"],
    queryFn: listPolls,
  });
  // The server leaves out club money totals for members without finance access.
  const showMoney = summary?.stats.netMonth !== null;

  const today = new Date();

  const requiredPolls = polls.filter(
    (p) => p.status === "open" && myVotes[p.id] === undefined,
  );

  const upcomingEvents = [...events]
    .filter((ev) => ev.date >= today.toISOString().slice(0, 10))
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(0, 4);

  const nextEventTitle = upcomingEvents[0]?.title ?? "";

  return (
    <div>
      <Group justify="flex-end" mb="md" className="page-actions">
        <Button variant="default" onClick={() => go("/app/operations/events")}>
          {t("dashboard.buttons.newEvent")}
        </Button>
        <Button variant="filled" onClick={() => go("/app/members")}>
          {t("common.addMember")}
        </Button>
      </Group>

      {summaryError && (
        <Card style={{ marginBottom: 16, borderColor: "red" }}>
          <Text c="red" size="sm">
            {t("common.error", 'Fehler')}
          </Text>
        </Card>
      )}
      {summaryLoading && (
        <Card style={{ marginBottom: 16 }}>
          <Text c="dimmed" size="sm">
            {t("common.loading", 'Wird geladen …')}
          </Text>
        </Card>
      )}

      {requiredPolls.length > 0 && (
        <Card
          style={{
            marginBottom: 16,
            border: "1.5px solid var(--mantine-color-acc-4)",
            background: "rgba(116, 65, 224, 0.08)",
          }}
        >
          <Card.Header style={{ background: "transparent" }}>
            <span style={{ fontSize: "var(--mantine-font-size-md)" }}>
              {"\uD83D\uDDF3"}
            </span>
            <Text
              fw={700}
              fz="md"
              style={{ color: "var(--mantine-color-acc-7)" }}
            >
              {t("dashboard.voteNeeded.title")}
            </Text>
            <span
              style={{
                marginLeft: "auto",
                fontSize: "var(--mantine-font-size-xs)",
                color: "var(--mantine-color-acc-7)",
              }}
            >
              {t("dashboard.voteNeeded.pollsRequire", {
                count: requiredPolls.length,
              })}
            </span>
          </Card.Header>
          <div>
            {requiredPolls.map((poll) => (
              <div
                key={poll.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "10px 16px",
                  borderTop: "1px solid rgba(116, 65, 224, 0.25)",
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
                    {poll.question}
                  </div>
                  <div
                    style={{
                      fontSize: "var(--mantine-font-size-xs)",
                      color: "var(--mantine-color-acc-7)",
                    }}
                  >
                    {poll.closesAt
                      ? t("dashboard.voteNeeded.closesOn", {
                          date: new Date(poll.closesAt).toLocaleDateString(
                            i18n.language,
                            { day: "numeric", month: "short" },
                          ),
                        })
                      : t("dashboard.voteNeeded.closesIn", {
                          days: poll.closesIn,
                        })}
                    {" \u00b7 "}
                    {t("dashboard.voteNeeded.options", {
                      count: poll.options.length,
                    })}
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="filled"
                  onClick={() => go("/app/operations/polls")}
                >
                  {t("dashboard.voteNeeded.vote")} →
                </Button>
              </div>
            ))}
          </div>
        </Card>
      )}

      <StatGrid columns={showMoney ? 4 : 2}>
        <StatTile
          label={t("dashboard.activeMembers")}
          value={
            summary?.stats ? String(summary.stats.activeMembers) : "\u2014"
          }
          sub={
            summary?.stats
              ? `+${summary.stats.memberDelta} ${t(
                  "dashboard.thisMonth",
                ).toLowerCase()}`
              : t("common.loading", 'Wird geladen …')
          }
          onClick={() => go("/app/members")}
        />
        {showMoney && (
          <>
            <StatTile
              label={t("dashboard.netThisMonth")}
              value={
                summary?.stats ? fmtNet(summary.stats.netMonth ?? 0) : "\u2014"
              }
              sub={t("dashboard.incomeMinusExpenses")}
              accent="#1f9d57"
              onClick={() => go("/app/finance")}
            />
            <StatTile
              label={t("common.openInvoices")}
              value={
                summary?.stats ? String(summary.stats.openInvoices) : "\u2014"
              }
              sub={
                summary?.stats && (summary.stats.openInvoices ?? 0) > 0
                  ? t("dashboard.outstanding", {
                      count: summary.stats.openInvoices,
                    })
                  : t("dashboard.allPaid")
              }
              accent="#6131c4"
              onClick={() => go("/app/finance/invoices")}
            />
          </>
        )}
        <StatTile
          label={t("dashboard.upcomingEventsLabel")}
          value={
            summary?.stats ? String(summary.stats.upcomingEvents) : "\u2014"
          }
          sub={
            nextEventTitle
              ? t("dashboard.nextEvent", { title: nextEventTitle })
              : t("dashboard.noneScheduled")
          }
          accent="#2596be"
          onClick={() => go("/app/operations/events")}
        />
      </StatGrid>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
          gap: 16,
        }}
      >
        <Card>
          <Card.Header title={t("dashboard.upcomingEvents.title")}>
            <Button
              size="sm"
              variant="subtle"
              style={{ marginLeft: "auto" }}
              onClick={() => go("/app/operations/events")}
            >
              {t("dashboard.viewAll")}
            </Button>
          </Card.Header>
          <div style={{ padding: "8px 0" }}>
            {upcomingEvents.length === 0 ? (
              <div
                style={{
                  padding: "20px",
                  textAlign: "center",
                  color: "var(--mantine-color-ink-3)",
                  fontSize: "var(--mantine-font-size-sm)",
                }}
              >
                {t("dashboard.noUpcomingEvents")}
              </div>
            ) : (
              upcomingEvents.map((ev) => {
                const d = new Date(ev.date);
                const day = d.getDate();
                const mon = d
                  .toLocaleString(i18n.language, { month: "short" })
                  .toUpperCase();
                return (
                  <UnstyledButton
                    key={ev.id}
                    style={{
                      display: "flex",
                      gap: 12,
                      padding: "10px 16px",
                      borderBottom: "1px solid var(--mantine-color-line-0)",
                      alignItems: "flex-start",
                      width: "100%",
                    }}
                    onClick={() => go("/app/operations/events")}
                  >
                    <div
                      style={{
                        textAlign: "center",
                        minWidth: 40,
                        flexShrink: 0,
                      }}
                    >
                      <div
                        className="num"
                        style={{
                          fontSize: "var(--mantine-font-size-xl)",
                          fontWeight: 700,
                          color: "var(--mantine-color-ink-8)",
                          lineHeight: 1,
                        }}
                      >
                        {day}
                      </div>
                      <div
                        style={{
                          fontSize: "var(--mantine-font-size-xs)",
                          fontWeight: 600,
                          color: "var(--mantine-color-ink-3)",
                          letterSpacing: "0.08em",
                        }}
                      >
                        {mon}
                      </div>
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div
                        style={{
                          fontSize: "var(--mantine-font-size-sm)",
                          fontWeight: 600,
                          color: "var(--mantine-color-ink-8)",
                          marginBottom: 2,
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
                        {ev.location ? ` \u00b7 ${ev.location}` : ""}
                      </div>
                    </div>
                    <Badge
                      variant="light"
                      styles={{
                        root: {
                          borderColor: EVENT_TYPE_COLORS[ev.type] + "66",
                          color: EVENT_TYPE_COLORS[ev.type],
                          backgroundColor: EVENT_TYPE_COLORS[ev.type] + "1a",
                          flexShrink: 0,
                        },
                      }}
                    >
                      {ev.type}
                    </Badge>
                  </UnstyledButton>
                );
              })
            )}
          </div>
        </Card>

        <Card>
          <Card.Header title={t("dashboard.recentPosts.title")}>
            <Button
              size="sm"
              variant="subtle"
              style={{ marginLeft: "auto" }}
              onClick={() => go("/app/operations/posts")}
            >
              {t("dashboard.viewAll")}
            </Button>
          </Card.Header>
          <div style={{ padding: "8px 0" }}>
            {!summary?.posts || summary.posts.length === 0 ? (
              <div
                style={{
                  padding: "20px",
                  textAlign: "center",
                  color: "var(--mantine-color-ink-3)",
                  fontSize: "var(--mantine-font-size-sm)",
                }}
              >
                {t("dashboard.recentPostsCard.noPosts")}
              </div>
            ) : (
              summary.posts.slice(0, 5).map((post) => (
                <UnstyledButton
                  key={post.id}
                  style={{
                    display: "flex",
                    gap: 10,
                    padding: "10px 16px",
                    borderBottom: "1px solid var(--mantine-color-line-0)",
                    alignItems: "center",
                    width: "100%",
                  }}
                  onClick={() => go(`/app/operations/posts/${post.id}`)}
                >
                  <Avatar
                    name={post.author_name ?? t("account.unknownAuthor")}
                    color={
                      post.author_avatar_color ?? "var(--mantine-color-acc-4)"
                    }
                    size={32}
                  />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        fontSize: "var(--mantine-font-size-sm)",
                        fontWeight: 600,
                        color: "var(--mantine-color-ink-8)",
                        marginBottom: 2,
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                      }}
                    >
                      {post.title}
                    </div>
                    <div
                      style={{
                        fontSize: "var(--mantine-font-size-xs)",
                        color: "var(--mantine-color-ink-4)",
                      }}
                    >
                      {post.author_name ?? t("account.unknownAuthor")}
                      {" \u00b7 "}
                      {post.like_count}{" "}
                      {t("events.likes", 'Likes').toLowerCase()}
                      {" \u00b7 "}
                      {post.comment_count}{" "}
                      {t("events.comments", 'Kommentare').toLowerCase()}
                    </div>
                  </div>
                </UnstyledButton>
              ))
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
