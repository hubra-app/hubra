import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Badge,
  Button,
  Group,
  Modal,
  NumberInput,
  Paper,
  Progress,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from '@mantine/core'
import { IconAdjustments } from '@tabler/icons-react'
import { useAdmin } from '@/context/AdminContext'
import { tr } from '@/lang'
import { planLabel } from '@/labels'
import {
  getTenantLimits,
  setTenantLimits,
  type LimitKind,
  type LimitRow,
  type TenantLimits as Limits,
} from '@/api/tenants'

const KINDS: LimitKind[] = ['members', 'mail_month', 'storage_mb']

const LABEL: Record<LimitKind, () => string> = {
  members: () => tr('Mitglieder', 'Members'),
  mail_month: () => tr('Mails diesen Monat', 'Mails this month'),
  storage_mb: () => tr('Speicher', 'Storage'),
}

const unit = (kind: LimitKind, n: number) =>
  kind === 'storage_mb' ? `${n.toLocaleString('de-CH')} MB` : n.toLocaleString('de-CH')

const COLOR = { ok: 'acc', warning: 'orange', over: 'red' } as const

type Mode = 'plan' | 'custom' | 'none'

function LimitMeter({ kind, row }: { kind: LimitKind; row: LimitRow }) {
  return (
    <Stack gap={6}>
      <Group justify="space-between" gap={6} wrap="nowrap">
        <Text size="sm" fw={600}>
          {LABEL[kind]()}
        </Text>
        {row.level !== 'ok' && (
          <Badge size="sm" variant="light" color={COLOR[row.level]}>
            {row.level === 'over' ? tr('Erreicht', 'Reached') : tr('Fast erreicht', 'Almost reached')}
          </Badge>
        )}
      </Group>
      <Progress
        value={row.limit ? Math.min(100, row.percent ?? 0) : 0}
        color={COLOR[row.level]}
        size="md"
        radius="xl"
        aria-label={LABEL[kind]()}
      />
      <Text size="sm">
        {row.limit == null
          ? tr(`${unit(kind, row.used)}, kein Limit`, `${unit(kind, row.used)}, no limit`)
          : tr(
              `${unit(kind, row.used)} von ${unit(kind, row.limit)} (${row.percent} %)`,
              `${unit(kind, row.used)} of ${unit(kind, row.limit)} (${row.percent} %)`,
            )}
      </Text>
      <Text size="xs" c="dimmed">
        {row.custom
          ? tr('Eigenes Limit für diesen Verein', 'Own limit for this club')
          : tr('Vom Tarif', 'From the plan')}
      </Text>
    </Stack>
  )
}

/**
 * The club's members, mails this month and storage against its limits, and
 * its own limits on top of the plan's (Settings › Plans & prices).
 */
export function TenantLimits({ tenantId }: { tenantId: number }) {
  const { notify } = useAdmin()
  const queryClient = useQueryClient()
  const { data } = useQuery({
    queryKey: ['tenant-limits', tenantId],
    queryFn: () => getTenantLimits(tenantId),
  })
  const [editing, setEditing] = useState(false)

  if (!data) return null
  const anyLimit = KINDS.some((k) => data.limits[k].limit != null)

  return (
    <Paper withBorder p="lg" mb={20}>
      <Group justify="space-between" mb={4} wrap="nowrap">
        <Title order={3}>{tr('Limits', 'Limits')}</Title>
        <Button
          size="xs"
          variant="light"
          leftSection={<IconAdjustments size={16} />}
          onClick={() => setEditing(true)}
        >
          {tr('Anpassen', 'Adjust')}
        </Button>
      </Group>
      <Text size="sm" c="dimmed" mb={16}>
        {anyLimit
          ? tr(
              `Tarif ${planLabel(data.plan, tr)}. Ab ${data.warn_percent} % und bei 100 % bekommen die Inhaber eine Meldung. Ist das Mitgliederlimit erreicht, kommt niemand Neues dazu; Mails und Speicher werden nur gemeldet.`,
              `${planLabel(data.plan, tr)} plan. The owners are told at ${data.warn_percent} % and at 100 %. At the member limit nobody new can join; mail and storage are only reported.`,
            )
          : tr(
              `Tarif ${planLabel(data.plan, tr)}, ohne Limits. Limits pro Tarif unter Einstellungen › Tarife & Preise.`,
              `${planLabel(data.plan, tr)} plan, no limits. Limits per plan are under Settings › Plans & prices.`,
            )}
      </Text>
      <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="lg">
        {KINDS.map((k) => (
          <LimitMeter key={k} kind={k} row={data.limits[k]} />
        ))}
      </SimpleGrid>
      {editing && (
        <LimitsModal
          data={data}
          onClose={() => setEditing(false)}
          onSave={async (values) => {
            try {
              const fresh = await setTenantLimits(tenantId, values)
              queryClient.setQueryData(['tenant-limits', tenantId], fresh)
              notify('success', tr('Limits gespeichert', 'Limits saved'))
              setEditing(false)
            } catch (err) {
              notify(
                'error',
                tr('Speichern fehlgeschlagen', 'Could not save'),
                err instanceof Error ? err.message : undefined,
              )
            }
          }}
        />
      )}
    </Paper>
  )
}

function LimitsModal({
  data,
  onClose,
  onSave,
}: {
  data: Limits
  onClose: () => void
  onSave: (values: Record<LimitKind, number | null | 'plan'>) => Promise<void>
}) {
  const start = (row: LimitRow): Mode =>
    !row.custom ? 'plan' : row.limit == null ? 'none' : 'custom'
  const [mode, setMode] = useState<Record<LimitKind, Mode>>(
    () => Object.fromEntries(KINDS.map((k) => [k, start(data.limits[k])])) as Record<LimitKind, Mode>,
  )
  const [value, setValue] = useState<Record<LimitKind, number | string>>(
    () =>
      Object.fromEntries(
        KINDS.map((k) => [k, data.limits[k].limit ?? data.limits[k].plan_limit ?? '']),
      ) as Record<LimitKind, number | string>,
  )
  const [saving, setSaving] = useState(false)
  const invalid = KINDS.some((k) => mode[k] === 'custom' && typeof value[k] !== 'number')

  const planText = (k: LimitKind) => {
    const p = data.limits[k].plan_limit
    return p == null ? tr('kein Limit', 'no limit') : unit(k, p)
  }

  return (
    <Modal opened onClose={onClose} title={tr('Limits anpassen', 'Adjust limits')} size="lg">
      <Stack gap="lg">
        {KINDS.map((k) => (
          <Stack key={k} gap={6}>
            <Text size="sm" fw={600}>
              {LABEL[k]()}
            </Text>
            <SegmentedControl
              fullWidth
              size="xs"
              value={mode[k]}
              onChange={(v) => setMode((m) => ({ ...m, [k]: v as Mode }))}
              data={[
                { value: 'plan', label: tr(`Tarif (${planText(k)})`, `Plan (${planText(k)})`) },
                { value: 'custom', label: tr('Eigenes', 'Own') },
                { value: 'none', label: tr('Kein Limit', 'No limit') },
              ]}
            />
            {mode[k] === 'custom' && (
              <NumberInput
                aria-label={LABEL[k]()}
                min={0}
                allowDecimal={false}
                allowNegative={false}
                thousandSeparator="'"
                suffix={k === 'storage_mb' ? ' MB' : undefined}
                value={value[k]}
                onChange={(v) => setValue((s) => ({ ...s, [k]: v }))}
              />
            )}
          </Stack>
        ))}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {tr('Abbrechen', 'Cancel')}
          </Button>
          <Button
            loading={saving}
            disabled={invalid}
            onClick={async () => {
              setSaving(true)
              try {
                await onSave(
                  Object.fromEntries(
                    KINDS.map((k) => [
                      k,
                      mode[k] === 'plan' ? 'plan' : mode[k] === 'none' ? null : Number(value[k]),
                    ]),
                  ) as Record<LimitKind, number | null | 'plan'>,
                )
              } finally {
                setSaving(false)
              }
            }}
          >
            {tr('Speichern', 'Save')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}
