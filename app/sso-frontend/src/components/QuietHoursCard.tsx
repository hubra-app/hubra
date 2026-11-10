import { useState } from 'react'
import { Button, Group, Paper, Stack, Switch, Text, TextInput } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { IconMoon } from '@tabler/icons-react'
import { useSso } from '@/context/SsoContext'
import { tr } from '@/lang'
import * as authApi from '@/api/auth'
import type { QuietHours } from '@/api/auth'

const KEY = ['quiet-hours']
const HHMM = /^([01]\d|2[0-3]):[0-5]\d$/

function browserZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'Europe/Zurich'
  } catch {
    return 'Europe/Zurich'
  }
}

/** Quiet hours for every club: push and direct messages wait until they
 * end; the bell and mails are not held. */
export function QuietHoursCard() {
  const { data, isLoading } = useQuery({ queryKey: KEY, queryFn: authApi.getQuietHours })
  if (isLoading) return null
  // Remount when the saved value changes, so the form starts from it.
  return <QuietHoursForm key={data ? `${data.from}-${data.to}` : 'off'} saved={data ?? null} />
}

function QuietHoursForm({ saved }: { saved: QuietHours | null }) {
  const { notify } = useSso()
  const queryClient = useQueryClient()
  const [on, setOn] = useState(saved !== null)
  const [from, setFrom] = useState(saved?.from ?? '22:00')
  const [to, setTo] = useState(saved?.to ?? '07:00')
  const [busy, setBusy] = useState(false)
  const valid = HHMM.test(from) && HHMM.test(to) && from !== to
  const dirty = on !== (saved !== null) || (on && (from !== saved?.from || to !== saved?.to))

  const save = async () => {
    setBusy(true)
    try {
      const next = on ? { from, to, tz: saved?.tz ?? browserZone() } : null
      queryClient.setQueryData(KEY, await authApi.setQuietHours(next))
      notify('success', tr('Gespeichert', 'Saved'))
    } catch (err) {
      notify('error', tr('Nicht gespeichert', 'Not saved'), err instanceof Error ? err.message : '')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Paper withBorder p="md" data-testid="quiet-hours">
      <Stack gap="sm">
        <Group gap="xs">
          <IconMoon size={18} style={{ color: 'var(--mantine-color-dimmed)' }} />
          <Text fw={600}>{tr('Ruhezeiten', 'Quiet hours')}</Text>
        </Group>
        <Switch
          checked={on}
          onChange={(e) => setOn(e.currentTarget.checked)}
          label={tr('Nachts nicht stören', 'Do not disturb at night')}
          description={tr(
            'Push-Nachrichten und Direktnachrichten (Discord) aus allen deinen Vereinen warten bis zum Ende der Ruhezeit. Die Glocke und E-Mails kommen wie immer.',
            'Push and direct messages (Discord) from all your clubs wait until quiet hours end. The bell and emails come as always.',
          )}
        />
        {on && (
          <Group gap="sm" align="flex-end">
            <TextInput
              type="time"
              label={tr('Von', 'From')}
              value={from}
              onChange={(e) => setFrom(e.currentTarget.value)}
              w={150}
            />
            <TextInput
              type="time"
              label={tr('Bis', 'To')}
              value={to}
              onChange={(e) => setTo(e.currentTarget.value)}
              w={150}
            />
            <Text size="xs" c="dimmed" pb={8}>
              {saved?.tz ?? browserZone()}
            </Text>
          </Group>
        )}
        <Group justify="flex-end">
          <Button size="xs" disabled={!dirty || (on && !valid)} loading={busy} onClick={() => void save()}>
            {tr('Speichern', 'Save')}
          </Button>
        </Group>
      </Stack>
    </Paper>
  )
}
