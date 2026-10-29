import { useState } from 'react'
import { Group, Paper, Stack, Switch, Text } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { IconAddressBook } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useToast } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { getMyDirectory, setMyDirectory, type DirectoryChoice } from '@/api/members'

/** The member chooses which contact data other members see. */
export function DirectoryCard() {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const [busy, setBusy] = useState(false)
  const { data } = useQuery({ queryKey: qk.account.directory, queryFn: getMyDirectory })
  if (!data) return null

  const labels: Record<DirectoryChoice, string> = {
    email: t('account.directory.email', 'E-Mail'),
    phone: t('account.directory.phone', 'Telefon und Mobile'),
    address: t('account.directory.address', 'Adresse'),
    birthday: t('account.directory.birthday', 'Geburtstag'),
  }

  const toggle = async (choice: DirectoryChoice, on: boolean) => {
    const shared = on
      ? [...data.shared, choice]
      : data.shared.filter((c) => c !== choice)
    setBusy(true)
    try {
      queryClient.setQueryData(qk.account.directory, await setMyDirectory(shared))
    } catch (err) {
      notify('error', t('common.error'), err instanceof Error ? err.message : '')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Paper withBorder shadow="sm" radius="lg">
      <Group p="md" gap="sm" style={{ borderBottom: '1px solid var(--mantine-color-gray-3)' }}>
        <IconAddressBook size={16} style={{ color: 'var(--mantine-color-ink-4)' }} />
        <Text fw={700} fz="md">
          {t('account.directory.title', 'Im Mitgliederverzeichnis zeigen')}
        </Text>
      </Group>
      <Stack p="md" gap="sm">
        <Text fz="sm" c="dimmed">
          {t(
            'account.directory.hint',
            'Was andere Mitglieder von dir sehen. Der Vorstand sieht deine Angaben immer.',
          )}
        </Text>
        {data.choices.map((choice) => (
          <Switch
            key={choice}
            label={labels[choice] ?? choice}
            checked={data.shared.includes(choice)}
            disabled={busy}
            onChange={(e) => toggle(choice, e.currentTarget.checked)}
          />
        ))}
      </Stack>
    </Paper>
  )
}
