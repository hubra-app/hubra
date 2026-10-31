import { useState } from 'react'
import { Group, Paper, Stack, Switch, Text } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { IconBellRinging } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useToast } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { getMyReminders, setMyReminders, type ReminderMails } from '@/api/members'

/** The member chooses which reminders also come by mail. */
export function RemindersCard() {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const [busy, setBusy] = useState(false)
  const { data } = useQuery({ queryKey: qk.account.reminders, queryFn: getMyReminders })
  if (!data) return null

  const toggle = async (key: keyof ReminderMails, on: boolean) => {
    setBusy(true)
    try {
      queryClient.setQueryData(qk.account.reminders, await setMyReminders({ [key]: on }))
    } catch (err) {
      notify('error', t('common.error'), err instanceof Error ? err.message : '')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Paper withBorder shadow="sm" radius="lg">
      <Group p="md" gap="sm" style={{ borderBottom: '1px solid var(--hb-border)' }}>
        <IconBellRinging size={16} style={{ color: 'var(--mantine-color-ink-4)' }} />
        <Text fw={700} fz="md">
          {t('account.reminders.title', 'Erinnerungen per E-Mail')}
        </Text>
      </Group>
      <Stack p="md" gap="sm">
        <Text fz="sm" c="dimmed">
          {t(
            'account.reminders.hint',
            'Vor Anlässen, für die du angemeldet bist, und bevor eine Umfrage schliesst, in der du noch nicht abgestimmt hast. In der App erscheinen sie immer.',
          )}
        </Text>
        <Switch
          label={t('account.reminders.events', 'Vor Anlässen')}
          checked={data.events}
          disabled={busy}
          onChange={(e) => toggle('events', e.currentTarget.checked)}
        />
        <Switch
          label={t('account.reminders.polls', 'Vor dem Ende von Umfragen')}
          checked={data.polls}
          disabled={busy}
          onChange={(e) => toggle('polls', e.currentTarget.checked)}
        />
      </Stack>
    </Paper>
  )
}
