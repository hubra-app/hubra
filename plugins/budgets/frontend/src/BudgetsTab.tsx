import { useState } from 'react'
import {
  ActionIcon,
  Badge,
  Button,
  Group,
  NumberInput,
  Paper,
  Progress,
  Select,
  Table,
  Text,
  TextInput,
} from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { IconPlus, IconTrash } from '@tabler/icons-react'
import { useT } from '@hubra/plugin-sdk'
import { useAuth, useToast } from '@hubra/plugin-sdk'
import { ConfirmModal, Field, Modal } from '@hubra/plugin-sdk'
import { listTxCategories } from '@hubra/plugin-sdk'
import {
  copyBudget,
  createBudget,
  deleteBudget,
  getBudget,
  listBudgets,
  saveBudgetLines,
  updateBudget,
  type Budget,
  type BudgetKind,
} from './api'

interface DraftLine {
  categoryId: string | null
  kind: BudgetKind
  planned: number
}

const chf = (v: string | number) =>
  Number(v).toLocaleString('de-CH', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })

export function BudgetsTab() {
  const { t } = useT()
  const { notify } = useToast()
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const canWrite = hasPermission('budgets.budgets.write')

  const { data: budgets = [] } = useQuery({
    queryKey: ['budgets'],
    queryFn: listBudgets,
  })
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const activeId = selectedId ?? budgets[0]?.id ?? null

  const { data: budget } = useQuery({
    queryKey: ['budgets', activeId],
    queryFn: () => getBudget(activeId as number),
    enabled: activeId !== null,
  })
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const refresh = async (id?: number) => {
    await queryClient.invalidateQueries({ queryKey: ['budgets'] })
    if (id !== undefined) setSelectedId(id)
  }

  const fail = (err: unknown) =>
    notify(
      'error',
      t('common.error'),
      err instanceof Error ? err.message : t('common.unknownError'),
    )

  const act = async (fn: () => Promise<Budget | void>, then?: number) => {
    try {
      const result = await fn()
      await refresh(then ?? (result ? result.id : undefined))
    } catch (err) {
      fail(err)
    }
  }

  return (
    <Paper withBorder shadow="sm" radius="lg" style={{ padding: 20 }}>
      <Group justify="space-between" mb="md" wrap="wrap">
        <Select
          w={260}
          placeholder={t('budgets.pick', 'Choose a budget')}
          data={budgets.map((b) => ({
            value: String(b.id),
            label: `${b.year} · ${b.name}`,
          }))}
          value={activeId === null ? null : String(activeId)}
          onChange={(v) => setSelectedId(v ? Number(v) : null)}
          allowDeselect={false}
        />
        {canWrite && (
          <Group gap="xs">
            {budget && !budget.approved && (
              <Button variant="default" size="xs" onClick={() => setEditing(true)}>
                {t('budgets.editLines', 'Edit lines')}
              </Button>
            )}
            {budget && (
              <Button
                variant="default"
                size="xs"
                onClick={() => act(() => updateBudget(budget.id, { approved: !budget.approved }))}
              >
                {budget.approved
                  ? t('budgets.unapprove', 'Reopen')
                  : t('budgets.approve', 'Mark approved')}
              </Button>
            )}
            {budget && (
              <Button variant="default" size="xs" onClick={() => act(() => copyBudget(budget.id))}>
                {t('budgets.copy', 'Copy to {{year}}', { year: budget.year + 1 })}
              </Button>
            )}
            {budget && !budget.approved && (
              <Button variant="subtle" color="red" size="xs" onClick={() => setDeleting(true)}>
                {t('common.delete')}
              </Button>
            )}
            <Button size="xs" onClick={() => setCreating(true)}>
              <IconPlus size={14} />
              {t('budgets.new', 'New budget')}
            </Button>
          </Group>
        )}
      </Group>

      {!budget ? (
        <Text c="dimmed" fz="sm">
          {t('budgets.empty', 'No budget yet. Create one for this year.')}
        </Text>
      ) : (
        <BudgetView budget={budget} />
      )}

      {creating && (
        <CreateModal
          onClose={() => setCreating(false)}
          onCreate={async (name, year) => {
            await act(() => createBudget({ name, year }))
            setCreating(false)
          }}
        />
      )}
      {editing && budget && (
        <LinesModal
          budget={budget}
          onClose={() => setEditing(false)}
          onSaved={async () => {
            await refresh()
            setEditing(false)
          }}
          onError={fail}
        />
      )}
      <ConfirmModal
        open={deleting}
        title={t('budgets.delete', 'Delete budget')}
        body={
          budget
            ? t('budgets.deleteConfirm', 'Delete {{name}} {{year}}?', {
                name: budget.name,
                year: budget.year,
              })
            : undefined
        }
        onConfirm={async () => {
          if (!budget) return
          setDeleting(false)
          setSelectedId(null)
          await act(() => deleteBudget(budget.id))
        }}
        onClose={() => setDeleting(false)}
      />
    </Paper>
  )
}

function BudgetView({ budget }: { budget: Budget }) {
  const { t } = useT()
  const sections: BudgetKind[] = ['income', 'expense']
  return (
    <div>
      <Group gap="xl" mb="md">
        <Stat label={t('budgets.plannedResult', 'Planned result')} value={budget.plannedResult} />
        <Stat label={t('budgets.actualResult', 'Result so far')} value={budget.actualResult} />
        {budget.approved && (
          <Badge color="green" variant="light">
            {t('budgets.approved', 'Approved')}
          </Badge>
        )}
      </Group>
      {sections.map((kind) => {
        const lines = (budget.lines ?? []).filter((l) => l.kind === kind)
        const unplanned = (budget.unplanned ?? []).filter((u) => u.kind === kind)
        return (
          <div key={kind} style={{ marginBottom: 20 }}>
            <Text fw={600} fz="sm" mb={6}>
              {kind === 'income' ? t('budgets.income', 'Income') : t('budgets.expense', 'Expenses')}
            </Text>
            <Table.ScrollContainer minWidth={520}>
              <Table verticalSpacing={6} fz="sm">
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>{t('budgets.category', 'Category')}</Table.Th>
                    <Table.Th ta="right">{t('budgets.planned', 'Planned')}</Table.Th>
                    <Table.Th ta="right">{t('budgets.actual', 'Actual')}</Table.Th>
                    <Table.Th w={160} />
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {lines.map((l) => {
                    const planned = Number(l.planned)
                    const actual = Number(l.actual)
                    const pct = planned > 0 ? (actual / planned) * 100 : 0
                    const over = kind === 'expense' && actual > planned
                    return (
                      <Table.Tr key={l.id}>
                        <Table.Td>{l.categoryName}</Table.Td>
                        <Table.Td ta="right" className="num">
                          {chf(l.planned)}
                        </Table.Td>
                        <Table.Td ta="right" className="num" c={over ? 'red' : undefined}>
                          {chf(l.actual)}
                        </Table.Td>
                        <Table.Td>
                          <Progress
                            value={Math.min(pct, 100)}
                            color={over ? 'red' : 'green'}
                            size="sm"
                            aria-label={`${Math.round(pct)}%`}
                          />
                        </Table.Td>
                      </Table.Tr>
                    )
                  })}
                  {unplanned.map((u) => (
                    <Table.Tr key={`u-${u.categoryId}`}>
                      <Table.Td c="dimmed">
                        {u.categoryName}{' '}
                        <Badge size="xs" variant="light" color="orange">
                          {t('budgets.unplanned', 'not in budget')}
                        </Badge>
                      </Table.Td>
                      <Table.Td ta="right" className="num" c="dimmed">
                        —
                      </Table.Td>
                      <Table.Td ta="right" className="num">
                        {chf(u.actual)}
                      </Table.Td>
                      <Table.Td />
                    </Table.Tr>
                  ))}
                  <Table.Tr>
                    <Table.Td fw={600}>{t('budgets.total', 'Total')}</Table.Td>
                    <Table.Td ta="right" fw={600} className="num">
                      {chf(budget.totals[kind].planned)}
                    </Table.Td>
                    <Table.Td ta="right" fw={600} className="num">
                      {chf(budget.totals[kind].actual)}
                    </Table.Td>
                    <Table.Td />
                  </Table.Tr>
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
          </div>
        )
      })}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  const n = Number(value)
  return (
    <div>
      <Text fz="xs" c="dimmed">
        {label}
      </Text>
      <Text fw={700} className="num" c={n < 0 ? 'red' : undefined}>
        CHF {chf(value)}
      </Text>
    </div>
  )
}

function CreateModal({
  onClose,
  onCreate,
}: {
  onClose: () => void
  onCreate: (name: string, year: number) => void
}) {
  const { t } = useT()
  const [name, setName] = useState(t('budgets.defaultName', 'Annual budget'))
  const [year, setYear] = useState<number>(new Date().getFullYear())
  return (
    <Modal
      open
      onClose={onClose}
      title={t('budgets.new', 'New budget')}
      footer={
        <>
          <Button variant="subtle" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button
            variant="default"
            disabled={!name.trim()}
            onClick={() => onCreate(name.trim(), year)}
          >
            {t('common.save')}
          </Button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <Field label={t('budgets.name', 'Name')}>
          <TextInput value={name} onChange={(e) => setName(e.currentTarget.value)} />
        </Field>
        <Field label={t('budgets.year', 'Year')}>
          <NumberInput
            value={year}
            onChange={(v) => setYear(Number(v) || year)}
            min={1900}
            max={2200}
            allowDecimal={false}
          />
        </Field>
      </div>
    </Modal>
  )
}

function LinesModal({
  budget,
  onClose,
  onSaved,
  onError,
}: {
  budget: Budget
  onClose: () => void
  onSaved: () => void
  onError: (err: unknown) => void
}) {
  const { t } = useT()
  const { data: categories = [] } = useQuery({
    queryKey: ['txCategories'],
    queryFn: listTxCategories,
  })
  const [lines, setLines] = useState<DraftLine[]>(() =>
    (budget.lines ?? []).map((l) => ({
      categoryId: String(l.categoryId),
      kind: l.kind,
      planned: Number(l.planned),
    })),
  )
  const [busy, setBusy] = useState(false)
  const categoryOptions = categories.map((c) => ({ value: c.id, label: c.name }))

  const set = (i: number, patch: Partial<DraftLine>) =>
    setLines((prev) => prev.map((l, j) => (j === i ? { ...l, ...patch } : l)))

  const save = async () => {
    setBusy(true)
    try {
      await saveBudgetLines(
        budget.id,
        lines
          .filter((l) => l.categoryId)
          .map((l) => ({
            category_id: Number(l.categoryId),
            kind: l.kind,
            planned: l.planned,
          })),
      )
      onSaved()
    } catch (err) {
      onError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open
      wide
      onClose={onClose}
      title={`${budget.name} ${budget.year}`}
      footer={
        <>
          <Button variant="subtle" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button variant="default" onClick={save} loading={busy}>
            {t('common.save')}
          </Button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {lines.map((line, i) => (
          <Group key={i} gap="xs" wrap="nowrap" align="flex-end">
            <Select
              style={{ flex: 2 }}
              data={categoryOptions}
              value={line.categoryId}
              onChange={(v) => set(i, { categoryId: v })}
              placeholder={t('budgets.category', 'Category')}
              searchable
            />
            <Select
              style={{ flex: 1 }}
              data={[
                { value: 'income', label: t('budgets.income', 'Income') },
                { value: 'expense', label: t('budgets.expense', 'Expenses') },
              ]}
              value={line.kind}
              onChange={(v) => set(i, { kind: (v as BudgetKind) ?? 'expense' })}
              allowDeselect={false}
            />
            <NumberInput
              style={{ flex: 1 }}
              value={line.planned}
              onChange={(v) => set(i, { planned: Number(v) || 0 })}
              min={0}
              decimalScale={2}
              thousandSeparator="'"
              prefix="CHF "
            />
            <ActionIcon
              variant="subtle"
              color="red"
              aria-label={t('common.delete')}
              onClick={() => setLines((prev) => prev.filter((_, j) => j !== i))}
            >
              <IconTrash size={16} />
            </ActionIcon>
          </Group>
        ))}
        <Button
          variant="subtle"
          size="xs"
          style={{ alignSelf: 'flex-start' }}
          onClick={() =>
            setLines((prev) => [...prev, { categoryId: null, kind: 'expense', planned: 0 }])
          }
        >
          <IconPlus size={14} />
          {t('budgets.addLine', 'Add line')}
        </Button>
      </div>
    </Modal>
  )
}
