import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Group, Paper, Switch, Text, Title } from '@mantine/core'
import { useAdmin } from '@/context/AdminContext'
import { tr } from '@/lang'
import { setTenantSandbox, type Tenant } from '@/api/tenants'

/** Sandbox club: a demo or test club that always uses the Stripe sandbox
 * keys, for online payments and for its Hubra subscription. */
export function TenantSandbox({ tenant }: { tenant: Tenant }) {
  const { notify } = useAdmin()
  const queryClient = useQueryClient()
  const [busy, setBusy] = useState(false)
  const on = !!tenant.sandbox

  const save = async (sandbox: boolean) => {
    setBusy(true)
    try {
      await setTenantSandbox(tenant.id, sandbox)
      queryClient.invalidateQueries({ queryKey: ['tenant', tenant.id] })
      queryClient.invalidateQueries({ queryKey: ['tenants'] })
      queryClient.invalidateQueries({ queryKey: ['tenant-billing', tenant.id] })
    } catch (err) {
      notify('error', tr('Speichern fehlgeschlagen', 'Could not save'), err instanceof Error ? err.message : undefined)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Paper withBorder p="lg" mb={20}>
      <Group justify="space-between" mb={4} wrap="nowrap">
        <Title order={3}>{tr('Sandbox-Verein', 'Sandbox club')}</Title>
        <Switch
          checked={on}
          disabled={busy}
          onChange={(e) => save(e.currentTarget.checked)}
          label={tr('Sandbox', 'Sandbox')}
          labelPosition="left"
        />
      </Group>
      <Text size="sm" c="dimmed">
        {on
          ? tr(
              'Demo- oder Testverein: Online-Zahlungen und das Hubra-Abo laufen immer über die Stripe-Sandbox-Schlüssel, auch wenn die Plattform live ist. Es fliesst kein echtes Geld, und der Verein zählt nicht zum Umsatz.',
              "Demo or test club: online payments and the Hubra subscription always use the Stripe sandbox keys, even when the platform is live. No real money moves, and the club isn't counted in revenue.",
            )
          : tr(
              'Der Verein folgt dem Stripe-Modus der Plattform (Einstellungen › Zahlungen). Einschalten für Demo- und Testvereine.',
              "The club follows the platform's Stripe mode (Settings › Payments). Turn on for demo and test clubs.",
            )}
      </Text>
    </Paper>
  )
}
