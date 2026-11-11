import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button, Group, NumberInput, Paper, SimpleGrid, Stack, Text } from "@mantine/core";
import { DateField } from '@hubra/ui'
import { IconDownload } from "@tabler/icons-react";
import { useT } from "@/locales/i18n";
import { useToast } from "@/context/AppContext";
import { ErrorBanner, LoadingSpinner, StatGrid, StatTile } from "@/components/ui";
import { formatCHF } from "@/format";
import { downloadMemberStats, getMemberStats } from "@/api/members";
import { qk } from "@/data/keys";

const today = () => new Date().toISOString().slice(0, 10);

/** Bars for counts: label, a bar as wide as its share of the largest, the number. */
function Bars({ rows }: { rows: [string, number][] }) {
  const max = Math.max(1, ...rows.map(([, n]) => n));
  return (
    <Stack gap={6}>
      {rows.map(([label, n]) => (
        <Group key={label} gap="sm" wrap="nowrap">
          <Text fz="sm" w={110} truncate>
            {label}
          </Text>
          <div style={{ flex: 1, height: 10, background: "var(--hb-surface-2, var(--mantine-color-gray-1))", borderRadius: 5 }}>
            <div
              style={{
                width: `${(n / max) * 100}%`,
                height: "100%",
                background: "var(--mantine-primary-color-filled)",
                borderRadius: 5,
              }}
            />
          </div>
          <Text fz="sm" fw={600} w={36} ta="right" className="num">
            {n}
          </Text>
        </Group>
      ))}
    </Stack>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Paper withBorder p="lg" radius="md">
      <Text fw={700} mb="md">
        {title}
      </Text>
      {children}
    </Paper>
  );
}

/** Members on a reference day, by age, status, tier and type; joins and
 *  leaves per month; open fees. For the board and subsidy forms. */
export function StatsTab() {
  const { t } = useT();
  const { notify } = useToast();
  const [on, setOn] = useState(today());
  const [year, setYear] = useState(new Date().getFullYear());
  const q = useQuery({
    queryKey: qk.members.stats(on, year),
    queryFn: () => getMemberStats(on, year),
    enabled: /^\d{4}-\d{2}-\d{2}$/.test(on),
  });

  const download = async () => {
    try {
      await downloadMemberStats(on, year);
    } catch (err) {
      notify("error", err instanceof Error ? err.message : String(err));
    }
  };

  const named = (block: Record<string, number>, prefix?: string) =>
    Object.entries(block)
      .sort((a, b) => b[1] - a[1])
      .map(([k, n]) => [k ? (prefix ? t(`${prefix}.${k}`, k) : k) : "–", n] as [string, number]);

  return (
    <Stack gap="md">
      <Group align="flex-end" justify="space-between" wrap="wrap">
        <Group align="flex-end" gap="sm">
          <DateField
            label={t("members.stats.on", "Stichtag")}
            description={t("members.stats.onHint", "Wer an diesem Tag Mitglied war")}
            value={on}
            onChange={(v) => setOn(v)}
          />
          <NumberInput
            w={120}
            label={t("members.stats.year", "Jahr")}
            description={t("members.stats.yearHint", "Ein- und Austritte")}
            value={year}
            min={1900}
            max={new Date().getFullYear() + 1}
            allowDecimal={false}
            onChange={(v) => typeof v === "number" && setYear(v)}
          />
        </Group>
        <Button variant="default" leftSection={<IconDownload size={16} />} onClick={download}>
          {t("members.stats.csv", "Als Tabelle (CSV)")}
        </Button>
      </Group>

      {q.error ? (
        <ErrorBanner message={(q.error as Error).message} onRetry={() => q.refetch()} />
      ) : !q.data ? (
        <LoadingSpinner />
      ) : (
        <>
          <StatGrid columns={q.data.fees ? 4 : 3}>
            <StatTile label={t("members.stats.total", "Mitglieder am Stichtag")} value={q.data.total} />
            <StatTile
              label={t("members.stats.joins", "Eintritte {{year}}", { year: q.data.year })}
              value={q.data.months.reduce((a, m) => a + m.joins, 0)}
            />
            <StatTile
              label={t("members.stats.leaves", "Austritte {{year}}", { year: q.data.year })}
              value={q.data.months.reduce((a, m) => a + m.leaves, 0)}
            />
            {q.data.fees && (
              <StatTile
                label={t("members.stats.openFees", "Offene Rechnungen")}
                value={formatCHF(Number(q.data.fees.openAmount))}
                sub={t("members.stats.overdue", "{{count}} überfällig, {{amount}}", {
                  count: q.data.fees.overdue,
                  amount: formatCHF(Number(q.data.fees.overdueAmount)),
                })}
              />
            )}
          </StatGrid>

          <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
            <Section title={t("members.stats.ages", "Alter am Stichtag")}>
              <Bars rows={q.data.ages.map((a) => [a.bracket, a.count] as [string, number])} />
              {q.data.ageUnknown > 0 && (
                <Text fz="xs" c="dimmed" mt="sm">
                  {t("members.stats.ageUnknown", "Ohne Geburtsdatum: {{count}}", { count: q.data.ageUnknown })}
                </Text>
              )}
            </Section>
            <Section title={t("members.stats.months", "Ein- und Austritte {{year}}", { year: q.data.year })}>
              <Stack gap={4}>
                {q.data.months.map((m) => (
                  <Group key={m.month} gap="sm" wrap="nowrap">
                    <Text fz="sm" w={70} className="num">
                      {m.month.slice(5)}.{m.month.slice(0, 4)}
                    </Text>
                    <Text fz="sm" c={m.joins ? "green" : "dimmed"} w={50} className="num">
                      {m.joins ? `+${m.joins}` : "·"}
                    </Text>
                    <Text fz="sm" c={m.leaves ? "red" : "dimmed"} w={50} className="num">
                      {m.leaves ? `−${m.leaves}` : "·"}
                    </Text>
                  </Group>
                ))}
              </Stack>
            </Section>
            <Section title={t("members.stats.byStatus", "Nach Status")}>
              <Bars rows={named(q.data.byStatus, "status")} />
            </Section>
            <Section title={t("members.stats.byTier", "Nach Stufe")}>
              <Bars rows={named(q.data.byTier)} />
              <Text fz="xs" c="dimmed" mt="sm">
                {t("members.stats.todayNote", "Status und Stufe sind die heutigen.")}
              </Text>
            </Section>
          </SimpleGrid>
        </>
      )}
    </Stack>
  );
}
