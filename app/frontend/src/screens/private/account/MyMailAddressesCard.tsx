import { useState } from 'react'
import { Badge, Group, Paper, Stack, Switch, Text } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { IconMail } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useToast } from '@/context/AppContext'
import { qk } from '@/data/keys'
import {
  listMyMailAddresses,
  toggleFunctionMail,
  toggleGroupMail,
  type MyMailAddress,
} from '@/api/mail'

/**
 * The club addresses of the groups the member leads and the functions they
 * hold (jugend@…, kassier@…). They switch them on or off themselves; the
 * address's name and extra aliases stay with the club. Hidden for everyone
 * else.
 */
export function MyMailAddressesCard() {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const [busy, setBusy] = useState<number | null>(null)
  const { data: addresses = [] } = useQuery({
    queryKey: qk.account.mailAddresses,
    queryFn: listMyMailAddresses,
  })
  if (addresses.length === 0) return null

  const toggle = async (addr: MyMailAddress, enabled: boolean) => {
    if (addr.ownerId == null) return
    setBusy(addr.id)
    try {
      const updated = await (addr.ownerType === 'function'
        ? toggleFunctionMail(addr.ownerId, enabled)
        : toggleGroupMail(addr.ownerId, enabled))
      queryClient.setQueryData<MyMailAddress[]>(qk.account.mailAddresses, (prev) =>
        (prev ?? []).map((a) => (a.id === addr.id ? { ...a, ...updated } : a)),
      )
    } catch (err) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error ? err.message : t('common.unknownError'),
      )
    } finally {
      setBusy(null)
    }
  }

  return (
    <Paper withBorder>
      <Group p="md" gap="sm" style={{ borderBottom: '1px solid var(--hb-border)' }}>
        <IconMail size={16} style={{ color: 'var(--mantine-color-ink-4)' }} />
        <Text fw={700} fz="md">
          {t('account.myAddresses.title', 'Adressen, die du betreust')}
        </Text>
      </Group>
      <Stack p="md" gap="md">
        <Text fz="sm" c="dimmed">
          {t(
            'account.myAddresses.hint',
            'Als Leitung einer Gruppe oder Inhaber/in einer Funktion schaltest du ihre Vereinsadresse ein oder aus. Den Namen der Adresse ändert der Vorstand.',
          )}
        </Text>
        {addresses.map((addr) => (
          <Group key={addr.id} justify="space-between" wrap="nowrap" gap="sm">
            <div style={{ minWidth: 0 }}>
              <Text fz="sm" fw={600} truncate>
                {addr.address}
              </Text>
              <Group gap={6}>
                <Badge variant="light" color="gray" size="sm" style={{ textTransform: 'none' }}>
                  {addr.ownerType === 'function'
                    ? t('account.myAddresses.function', 'Funktion')
                    : t('account.myAddresses.group', 'Gruppe')}
                </Badge>
                <Text fz="xs" c="dimmed">
                  {addr.ownerName}
                </Text>
              </Group>
            </div>
            <Switch
              checked={addr.isEnabled}
              disabled={busy === addr.id}
              onChange={(e) => toggle(addr, e.currentTarget.checked)}
              aria-label={t('account.myAddresses.toggle', '{{address}} aktiv', {
                address: addr.address,
              })}
            />
          </Group>
        ))}
      </Stack>
    </Paper>
  )
}
