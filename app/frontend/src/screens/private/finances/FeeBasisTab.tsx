import { useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useDebouncedValue } from '@mantine/hooks'
import {
  Badge,
  Button,
  Group,
  NumberInput,
  Paper,
  Radio,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core'
import { useT } from '@/locales/i18n'
import { useAuth, useNav } from '@/context/AppContext'
import { getModules, type ModuleInfo } from '@/api/modules'
import { getFeeBasis, type FeeBasis, type FeeBasisSource } from '@/api/finance'
import { localizeModule } from '@/modules/labels'
import { formatCHF, formatDate } from '@/format'
import { qk } from '@/data/keys'
import { useSaveSettings } from '@/screens/private/finances/useSaveSettings'

const SOURCES: FeeBasisSource[] = ['recurring', 'last_year', 'budget', 'manual']

const INTERVAL_KEYS: Record<string, string> = {
  monthly: 'monthly',
  quarterly: 'quarterly',
  half_yearly: 'halfYearly',
  yearly: 'yearly',
}

function saved(module: ModuleInfo | undefined) {
  const config = module?.config ?? {}
  const num = (v: unknown) => (typeof v === 'number' ? v : undefined)
  return {
    source: ((config.fee_basis_source as string) || 'manual') as FeeBasisSource,
    extra: num(config.fee_basis_extra) ?? 0,
    manual: num(config.fee_basis_manual),
  }
}

const cellRight = { textAlign: 'right' as const }

/* ── Finanzen › Beitragsgrundlage: how the yearly expenses that percentage
   and formula tiers share among members come together ── */
export function FeeBasisTab() {
  const { hasPermission } = useAuth()
  const { data: finance } = useQuery({
    queryKey: qk.modules,
    queryFn: getModules,
    select: (list) => list.map(localizeModule).find((m) => m.code === 'finance'),
  })
  if (!finance) return null
  return (
    <FeeBasisForm
      key={JSON.stringify(finance.config)}
      module={finance}
      canWrite={hasPermission('modules.modules.write')}
    />
  )
}

function FeeBasisForm({ module, canWrite }: { module: ModuleInfo; canWrite: boolean }) {
  const { t } = useT()
  const { go } = useNav()
  const [save, busy] = useSaveSettings(module)
  const initial = saved(module)
  const [source, setSource] = useState<FeeBasisSource>(initial.source)
  const [extra, setExtra] = useState<number>(initial.extra)
  const [manual, setManual] = useState<number | undefined>(initial.manual)

  const [preview] = useDebouncedValue({ source, extra, manual }, 300)
  const { data } = useQuery({
    // "Bisher" depends on what is saved, so that is part of the key.
    queryKey: qk.feeBasis(JSON.stringify({ preview, initial })),
    queryFn: () => getFeeBasis(preview),
    placeholderData: keepPreviousData,
  })
  // Before a number is typed, "manual" shows the old setting's value.
  const manualValue = manual ?? data?.manual
  const dirty =
    source !== initial.source ||
    extra !== initial.extra ||
    (manual !== undefined && manual !== initial.manual)

  const sourceText: Record<FeeBasisSource, [string, string]> = {
    recurring: [
      t('finance.feeBasis.source.recurring', 'Wiederkehrende Ausgaben'),
      t(
        'finance.feeBasis.source.recurringHint',
        'Alle laufenden wiederkehrenden Ausgaben, die zu den Jahresausgaben zählen, auf ein Jahr gerechnet.',
      ),
    ],
    last_year: [
      t('finance.feeBasis.source.lastYear', 'Ausgaben des Vorjahres'),
      t(
        'finance.feeBasis.source.lastYearHint',
        'Die bestätigten Ausgaben des letzten vollen Beitragsjahres.',
      ),
    ],
    budget: [
      t('finance.feeBasis.source.budget', 'Budget'),
      t(
        'finance.feeBasis.source.budgetHint',
        'Die Ausgaben im genehmigten Budget des laufenden Jahres (Plugin Budgets).',
      ),
    ],
    manual: [
      t('finance.feeBasis.source.manual', 'Fester Betrag'),
      t('finance.feeBasis.source.manualHint', 'Ein Betrag, den du selbst festlegst.'),
    ],
  }

  return (
    <Stack gap={20}>
      <Paper withBorder p="lg">
        <Title order={3} mb={4}>
          {t('finance.feeBasis.title', 'Jährliche Ausgaben')}
        </Title>
        <Text size="sm" c="dimmed" mb="md" maw={640}>
          {t(
            'finance.feeBasis.intro',
            'Prozent- und Formel-Stufen verteilen die jährlichen Ausgaben des Vereins auf die Mitglieder. Hier legst du fest, woher diese Summe kommt.',
          )}
        </Text>
        <Radio.Group
          value={source}
          onChange={(v) => setSource(v as FeeBasisSource)}
          label={t('finance.feeBasis.sourceLabel', 'Die Summe kommt aus')}
        >
          <Stack gap="sm" mt="xs">
            {SOURCES.map((code) => {
              const available = !data || data.sources.includes(code)
              return (
                <Radio
                  key={code}
                  value={code}
                  label={sourceText[code][0]}
                  description={
                    available
                      ? sourceText[code][1]
                      : t(
                          'finance.feeBasis.source.needsBudgets',
                          'Braucht das Plugin Budgets.',
                        )
                  }
                  disabled={!canWrite || !available}
                />
              )
            })}
          </Stack>
        </Radio.Group>
        <Group mt="lg" gap="md" align="flex-end" wrap="wrap">
          {source === 'manual' ? (
            <NumberInput
              label={t('finance.feeBasis.manual', 'Jährliche Ausgaben (CHF)')}
              value={manualValue ?? ''}
              onChange={(v) => setManual(typeof v === 'number' ? v : 0)}
              min={0}
              decimalScale={2}
              thousandSeparator="’"
              disabled={!canWrite}
              w={240}
            />
          ) : (
            <NumberInput
              label={t('finance.feeBasis.extra', 'Zusätzliche Kosten pro Jahr (CHF)')}
              description={t(
                'finance.feeBasis.extraHint',
                'Für Kosten, die nicht darin enthalten sind, etwa Reparaturen.',
              )}
              value={extra}
              onChange={(v) => setExtra(typeof v === 'number' ? v : 0)}
              min={0}
              decimalScale={2}
              thousandSeparator="’"
              disabled={!canWrite}
              w={300}
            />
          )}
          {canWrite && (
            <Group gap="sm" ml="auto">
              {dirty && (
                <Button
                  variant="default"
                  onClick={() => {
                    setSource(initial.source)
                    setExtra(initial.extra)
                    setManual(initial.manual)
                  }}
                >
                  {t('finance.feeBasis.reset', 'Zurücksetzen')}
                </Button>
              )}
              <Button
                loading={busy}
                disabled={!dirty}
                onClick={() =>
                  save({
                    fee_basis_source: source,
                    fee_basis_extra: extra,
                    fee_basis_manual: manualValue ?? null,
                  })
                }
              >
                {t('common.save', 'Speichern')}
              </Button>
            </Group>
          )}
        </Group>
      </Paper>

      {data && <Breakdown data={data} />}
      {data && data.tiers.length > 0 && <TierEffects data={data} changed={dirty} />}
      {data && data.tiers.length === 0 && (
        <Text size="sm" c="dimmed">
          {t(
            'finance.feeBasis.noTiers',
            'Noch keine Stufe mit Prozent oder Formel. Stufen mit festem Betrag hängen nicht von dieser Summe ab.',
          )}{' '}
          <Button variant="subtle" size="compact-sm" onClick={() => go('/app/members/tiers')}>
            {t('finance.feeBasis.openTiers', 'Stufen öffnen')}
          </Button>
        </Text>
      )}
    </Stack>
  )
}

function Breakdown({ data }: { data: FeeBasis }) {
  const { t } = useT()
  const interval = (code?: string) =>
    code ? t(`finance.recurring.${INTERVAL_KEYS[code] ?? code}`) : ''

  let heading = t('finance.feeBasis.breakdown', 'So setzt sich die Summe zusammen')
  if (data.period?.from && data.period.to) {
    heading += ` · ${formatDate(data.period.from)} – ${formatDate(data.period.to)}`
  } else if (data.period?.year) {
    heading += ` · ${data.period.year}`
  }

  const empty =
    data.source === 'manual'
      ? t('finance.feeBasis.manualNoLines', 'Ein fester Betrag hat keine Aufteilung.')
      : data.note === 'NO_BUDGET'
        ? t('finance.feeBasis.noBudget', 'Für dieses Jahr gibt es kein genehmigtes Budget.')
        : t('finance.feeBasis.noLines', 'Keine Ausgaben gefunden.')

  return (
    <Paper withBorder shadow="sm" radius="lg">
      <Group p="md" gap="sm" style={{ borderBottom: '1px solid var(--hb-border)' }}>
        <Text fw={700} fz="md">
          {heading}
        </Text>
      </Group>
      <div style={{ overflowX: 'auto' }}>
        <Table className="responsive-table">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{t('finance.summary.category', 'Kategorie')}</Table.Th>
              <Table.Th style={cellRight}>{t('finance.feeBasis.share', 'Anteil')}</Table.Th>
              <Table.Th style={cellRight}>{t('finance.feeBasis.perYear', 'Pro Jahr')}</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {data.lines.length === 0 && (
              <Table.Tr>
                <Table.Td
                  colSpan={3}
                  style={{
                    textAlign: 'center',
                    color: 'var(--hb-text-3)',
                    padding: 24,
                    fontSize: 'var(--mantine-font-size-sm)',
                  }}
                >
                  {empty}
                </Table.Td>
              </Table.Tr>
            )}
            {data.lines.map((line) => (
              <Table.Tr key={line.categoryId ?? `none-${line.name}`}>
                <Table.Td data-label={t('finance.summary.category', 'Kategorie')}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span
                      style={{
                        width: 10,
                        height: 10,
                        borderRadius: 3,
                        flexShrink: 0,
                        background: line.color ?? 'var(--hb-text-3)',
                      }}
                    />
                    <span>{line.name ?? t('finance.summary.uncategorized', 'Ohne Kategorie')}</span>
                  </div>
                  {line.items.length > 0 && (
                    <div style={{ color: 'var(--hb-text-3)', fontSize: 'var(--mantine-font-size-xs)', marginTop: 2 }}>
                      {line.items
                        .map((item) =>
                          item.interval && item.amount !== undefined
                            ? `${item.description} (${formatCHF(item.amount)} ${interval(item.interval).toLowerCase()})`
                            : item.description,
                        )
                        .join(' · ')}
                    </div>
                  )}
                  <div
                    style={{
                      marginTop: 4,
                      height: 4,
                      width: `${Math.max(line.share * 100, 1)}%`,
                      background: line.color ?? 'var(--hb-text-3)',
                      borderRadius: 2,
                    }}
                  />
                </Table.Td>
                <Table.Td data-label={t('finance.feeBasis.share', 'Anteil')} style={cellRight}>
                  <span className="num">{Math.round(line.share * 100)} %</span>
                </Table.Td>
                <Table.Td data-label={t('finance.feeBasis.perYear', 'Pro Jahr')} style={cellRight}>
                  <span className="num">{formatCHF(line.amount)}</span>
                </Table.Td>
              </Table.Tr>
            ))}
            {data.extra > 0 && (
              <Table.Tr>
                <Table.Td data-label={t('finance.summary.category', 'Kategorie')}>
                  {t('finance.feeBasis.extraLine', 'Zusätzliche Kosten')}
                </Table.Td>
                <Table.Td data-label={t('finance.feeBasis.share', 'Anteil')} style={cellRight}>
                  <span className="num">
                    {data.total ? Math.round((data.extra / data.total) * 100) : 0} %
                  </span>
                </Table.Td>
                <Table.Td data-label={t('finance.feeBasis.perYear', 'Pro Jahr')} style={cellRight}>
                  <span className="num">{formatCHF(data.extra)}</span>
                </Table.Td>
              </Table.Tr>
            )}
          </Table.Tbody>
          <Table.Tfoot>
            <Table.Tr style={{ fontWeight: 700 }}>
              <Table.Td colSpan={2}>{t('finance.feeBasis.total', 'Jährliche Ausgaben')}</Table.Td>
              <Table.Td style={cellRight}>
                <span className="num" data-testid="fee-basis-total">
                  {formatCHF(data.total)}
                </span>
              </Table.Td>
            </Table.Tr>
          </Table.Tfoot>
        </Table>
      </div>
    </Paper>
  )
}

function TierEffects({ data, changed }: { data: FeeBasis; changed: boolean }) {
  const { t } = useT()
  return (
    <Paper withBorder shadow="sm" radius="lg">
      <div style={{ padding: 'var(--mantine-spacing-md)', borderBottom: '1px solid var(--hb-border)' }}>
        <Text fw={700} fz="md">
          {t('finance.feeBasis.tiersTitle', 'Was das für die Stufen heisst')}
        </Text>
        <Text size="xs" c="dimmed">
          {t('finance.feeBasis.tiersHint', 'Beitrag pro Mitglied und Jahr, ohne Kürzungen bei Eintritt.')}
        </Text>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <Table className="responsive-table">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{t('finance.feeBasis.tier', 'Stufe')}</Table.Th>
              <Table.Th style={cellRight}>{t('finance.feeBasis.members', 'Mitglieder')}</Table.Th>
              {changed && (
                <Table.Th style={cellRight}>{t('finance.feeBasis.now', 'Bisher')}</Table.Th>
              )}
              <Table.Th style={cellRight}>
                {changed ? t('finance.feeBasis.new', 'Neu') : t('finance.feeBasis.perYear', 'Pro Jahr')}
              </Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {data.tiers.map((tier) => (
              <Table.Tr key={tier.id}>
                <Table.Td data-label={t('finance.feeBasis.tier', 'Stufe')}>
                  <Group gap={8} wrap="nowrap">
                    <span>{tier.name}</span>
                    <Badge size="xs" variant="light">
                      {t(`tiers.type.${tier.priceType}`)}
                    </Badge>
                  </Group>
                </Table.Td>
                <Table.Td data-label={t('finance.feeBasis.members', 'Mitglieder')} style={cellRight}>
                  <span className="num">{tier.members}</span>
                </Table.Td>
                {changed && (
                  <Table.Td data-label={t('finance.feeBasis.now', 'Bisher')} style={cellRight}>
                    <span className="num" style={{ color: 'var(--hb-text-3)' }}>
                      {formatCHF(tier.yearlyNow)}
                    </span>
                  </Table.Td>
                )}
                <Table.Td
                  data-label={changed ? t('finance.feeBasis.new', 'Neu') : t('finance.feeBasis.perYear', 'Pro Jahr')}
                  style={cellRight}
                >
                  <span className="num" style={{ fontWeight: 700 }}>
                    {formatCHF(tier.yearly)}
                  </span>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </div>
    </Paper>
  )
}
