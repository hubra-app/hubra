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
      const res = await setTenantSandbox(tenant.id, sandbox)
      if (res.sandboxSubscription) {
        notify(
          'success',
          tr('Abo in die Sandbox verschoben', 'Subscription moved to the sandbox'),
          tr(
            'Das Live-Abo ist beendet; ein Sandbox-Abo mit denselben Posten läuft (Rechnung statt Karte).',
            'The live subscription has ended; a sandbox subscription with the same lines runs (invoice instead of card).',
          ),
        )
      } else if (res.subscriptionEnded) {
        notify(
          'success',
          tr('Abo beendet', 'Subscription ended'),
          tr(
            'Das bisherige Abo ist beendet. Der Verein startet ein neues unter Einstellungen › Hubra-Abo.',
            'The previous subscription has ended. The club starts a new one in Settings › Hubra subscription.',
          ),
        )
      }
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
      <Text size="xs" c="dimmed" mt={6}>
        {tr(
          'Wechselt der Stripe-Modus, endet ein laufendes Abo im alten Modus sofort (ohne Gutschrift). Ein Verein, der live bezahlt hat, bekommt dafür ein Sandbox-Abo mit denselben Posten.',
          'If the Stripe mode changes, a running subscription in the old mode ends at once (no credit). A club that paid live gets a sandbox subscription with the same lines instead.',
        )}
      </Text>
    </Paper>
  )
}
