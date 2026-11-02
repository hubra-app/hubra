import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Badge, Group, Paper, SegmentedControl, Stack, Switch, Text, Title } from '@mantine/core'
import { useAdmin } from '@/context/AdminContext'
import { getLang, tr } from '@/lang'
import { getTenantEarlyAccess, setTenantEarlyAccess } from '@/api/tenants'

const STAGE = {
  off: () => tr('aus', 'off'),
  early: () => tr('Testgruppe', 'early group'),
  all: () => tr('alle Vereine', 'all clubs'),
} as const

/** Whether the club is in the early-access group, and its own choice per
 * feature (Alle Vereine › Früher Zugang). */
export function TenantEarlyAccess({ tenantId }: { tenantId: number }) {
  const { notify } = useAdmin()
  const queryClient = useQueryClient()
  const key = ['tenant-early-access', tenantId]
  const { data } = useQuery({ queryKey: key, queryFn: () => getTenantEarlyAccess(tenantId) })
  const [busy, setBusy] = useState(false)
  const en = getLang() === 'en'

  const save = async (body: Parameters<typeof setTenantEarlyAccess>[1]) => {
    setBusy(true)
    try {
      queryClient.setQueryData(key, await setTenantEarlyAccess(tenantId, body))
      queryClient.invalidateQueries({ queryKey: ['platform-features'] })
    } catch (err) {
      notify('error', tr('Speichern fehlgeschlagen', 'Could not save'), err instanceof Error ? err.message : undefined)
    } finally {
      setBusy(false)
    }
  }

  if (!data) return null

  return (
    <Paper withBorder p="lg" mb={20}>
      <Group justify="space-between" mb={4} wrap="nowrap">
        <Title order={3}>{tr('Früher Zugang', 'Early access')}</Title>
        <Switch
          checked={data.early_access}
          disabled={busy}
          onChange={(e) => save({ early_access: e.currentTarget.checked })}
          label={tr('In der Testgruppe', 'In the early group')}
          labelPosition="left"
        />
      </Group>
      <Text size="sm" c="dimmed" mb={data.features.length ? 14 : 0}>
        {data.early_access
          ? tr(
              'Der Verein sieht neue Funktionen, die auf «Testgruppe» stehen, vor allen anderen.',
              'The club sees new features set to “Early group” before everybody else.',
            )
          : tr(
              'Der Verein bekommt neue Funktionen erst, wenn sie für alle freigegeben sind.',
              'The club gets new features once they are on for all clubs.',
            )}
        {data.features.length === 0 &&
          tr(' Zurzeit ist keine Funktion im frühen Zugang.', ' No feature is in early access right now.')}
      </Text>
      <Stack gap={10}>
        {data.features.map((f) => (
          <Group key={f.key} justify="space-between" gap="sm" wrap="wrap">
            <Group gap={8}>
              <Text size="sm" fw={600}>
                {en ? f.title_en : f.title_de}
              </Text>
              <Badge size="sm" variant="light" color={f.on ? 'green' : 'gray'}>
                {f.on ? tr('An', 'On') : tr('Aus', 'Off')}
              </Badge>
            </Group>
            <SegmentedControl
              size="xs"
              disabled={busy}
              value={f.override === null ? 'stage' : f.override ? 'on' : 'off'}
              onChange={(v) => save({ features: { [f.key]: v === 'stage' ? null : v === 'on' } })}
              data={[
                { value: 'stage', label: tr(`Wie Stufe (${STAGE[f.stage]()})`, `Like stage (${STAGE[f.stage]()})`) },
                { value: 'on', label: tr('Immer an', 'Always on') },
                { value: 'off', label: tr('Immer aus', 'Always off') },
              ]}
            />
          </Group>
        ))}
      </Stack>
    </Paper>
  )
}
