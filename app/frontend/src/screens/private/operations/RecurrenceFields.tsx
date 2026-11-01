import { Checkbox, Chip, Group, Select, Text, TextInput, UnstyledButton } from '@mantine/core'
import { useT } from '@/locales/i18n'
import { Field } from '@/components/ui'
import { defaultRepeat, ruleDates, type RepeatState } from './recurrence'

export function RecurrenceFields({
  start,
  value,
  onChange,
  toggle = true,
}: {
  /** The first date the rule counts from. */
  start: string
  value: RepeatState
  onChange: (next: RepeatState) => void
  /** Show the "repeat weekly" switch (off: the rule is always on). */
  toggle?: boolean
}) {
  const { t, i18n } = useT()
  const set = (patch: Partial<RepeatState>) => onChange({ ...value, ...patch })
  const names = [0, 1, 2, 3, 4, 5, 6].map((d) =>
    // 2024-01-01 was a Monday.
    new Date(Date.UTC(2024, 0, 1 + d)).toLocaleString(i18n.language, {
      weekday: 'short',
      timeZone: 'UTC',
    }),
  )
  const all = value.on ? ruleDates(start, value, true) : []
  const kept = all.filter((d) => !value.skipDates.includes(d))
  const toggleSkip = (d: string) =>
    set({
      skipDates: value.skipDates.includes(d)
        ? value.skipDates.filter((x) => x !== d)
        : [...value.skipDates, d].sort(),
    })
  const short = (d: string) =>
    new Date(`${d}T00:00:00Z`).toLocaleDateString(i18n.language, {
      day: 'numeric',
      month: 'short',
      timeZone: 'UTC',
    })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {toggle && (
        <Checkbox
          label={t('events.repeat.weekly', 'Wöchentlich wiederholen (z. B. Training)')}
          checked={value.on}
          onChange={(e) =>
            onChange(
              e.currentTarget.checked
                ? { ...defaultRepeat(start), on: true }
                : { ...value, on: false },
            )
          }
        />
      )}
      {value.on && (
        <>
          <Field label={t('events.repeat.days', 'An diesen Tagen')}>
            <Chip.Group
              multiple
              value={value.weekdays.map(String)}
              onChange={(v) => set({ weekdays: v.map(Number).sort() })}
            >
              <Group gap={6}>
                {names.map((name, d) => (
                  <Chip key={d} value={String(d)} size="sm">
                    {name}
                  </Chip>
                ))}
              </Group>
            </Chip.Group>
          </Field>
          <Group grow align="flex-start" gap={12}>
            <Field label={t('events.repeat.every', 'Rhythmus')}>
              <Select
                data={[1, 2, 3, 4].map((n) => ({
                  value: String(n),
                  label:
                    n === 1
                      ? t('events.repeat.everyWeek', 'Jede Woche')
                      : t('events.repeat.everyNWeeks', 'Alle {{count}} Wochen', { count: n }),
                }))}
                value={String(value.interval)}
                onChange={(v) => set({ interval: Number(v ?? 1) })}
                allowDeselect={false}
              />
            </Field>
            <Field label={t('events.repeat.until', 'Bis')}>
              <TextInput
                type="date"
                value={value.until}
                min={start}
                onChange={(e) => set({ until: e.currentTarget.value })}
              />
            </Field>
          </Group>
          <Field
            label={t('events.repeat.dates', '{{count}} Termine', { count: kept.length })}
            hint={t(
              'events.repeat.skipHint',
              'Tippe auf einen Termin, der ausfällt (Ferien, Feiertage).',
            )}
          >
            {all.length === 0 ? (
              <Text size="sm" c="dimmed">
                {t('events.repeat.none', 'Mit dieser Regel gibt es keinen Termin.')}
              </Text>
            ) : (
              <Group gap={6} style={{ maxHeight: 132, overflowY: 'auto' }}>
                {all.map((d) => {
                  const skipped = value.skipDates.includes(d)
                  return (
                    <UnstyledButton
                      key={d}
                      onClick={() => toggleSkip(d)}
                      aria-pressed={!skipped}
                      title={
                        skipped
                          ? t('events.repeat.skipped', 'Fällt aus')
                          : t('events.repeat.takesPlace', 'Findet statt')
                      }
                      style={{
                        fontSize: 'var(--mantine-font-size-xs)',
                        padding: '2px 8px',
                        borderRadius: 999,
                        border: '1px solid var(--hb-border)',
                        background: skipped ? 'transparent' : 'var(--hb-surface-2)',
                        color: skipped ? 'var(--hb-text-3)' : 'var(--hb-text)',
                        textDecoration: skipped ? 'line-through' : undefined,
                      }}
                    >
                      {short(d)}
                    </UnstyledButton>
                  )
                })}
              </Group>
            )}
          </Field>
        </>
      )}
    </div>
  )
}
