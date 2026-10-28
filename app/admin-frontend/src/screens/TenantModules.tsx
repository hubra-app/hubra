import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Badge, Group, Paper, Stack, Switch, Table, Text, Title } from '@mantine/core'
import { useAdmin } from '@/context/AdminContext'
import { tr } from '@/lang'
import { getTenantModules, setTenantModule, type TenantModule } from '@/api/tenants'

/**
 * Which modules a club may use. "Allowed" is the platform's decision; the
 * club admin switches allowed modules on or off in the club's own settings.
 */
export function TenantModules({ tenantId }: { tenantId: number }) {
  const { notify } = useAdmin()
  const queryClient = useQueryClient()
  const { data: modules = [], isLoading } = useQuery({
    queryKey: ['tenant-modules', tenantId],
    queryFn: () => getTenantModules(tenantId),
  })

  const update = async (m: TenantModule, body: { allowed?: boolean; enabled?: boolean }) => {
    try {
      await setTenantModule(tenantId, m.code, body)
      await queryClient.invalidateQueries({ queryKey: ['tenant-modules', tenantId] })
    } catch (err) {
      notify('error', m.name, err instanceof Error ? err.message : undefined)
    }
  }

  const optional = modules.filter((m) => !m.required)

  return (
    <Paper withBorder p="lg" mb={20}>
      <Stack gap={4} mb={12}>
        <Title order={3}>{tr('Module', 'Modules')}</Title>
        <Text size="sm" c="dimmed">
          {tr(
            'Ein gesperrtes Modul ist für den Verein ausgeschaltet und kann vom Vereins-Admin nicht wieder eingeschaltet werden. Die Daten bleiben erhalten.',
            'Blocking a module switches it off for the club and stops the club admin from switching it back on. Data is kept.',
          )}
        </Text>
      </Stack>
      {isLoading ? (
        <Text size="sm" c="dimmed">
          {tr('Wird geladen …', 'Loading…')}
        </Text>
      ) : (
        <Table.ScrollContainer minWidth={480}>
        <Table verticalSpacing="xs">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{tr('Modul', 'Module')}</Table.Th>
              <Table.Th>{tr('Eingeschaltet', 'In use')}</Table.Th>
              <Table.Th>{tr('Erlaubt', 'Allowed')}</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {optional.map((m) => (
              <Table.Tr key={m.code}>
                <Table.Td>
                  <Group gap={6}>
                    <Text size="sm" fw={600}>
                      {m.name}
                    </Text>
                    {m.plugin && (
                      <Badge size="xs" variant="outline" color="gray">
                        Plugin {m.plugin.name} {m.plugin.version}
                      </Badge>
                    )}
                  </Group>
                  <Text size="xs" c="dimmed">
                    {m.description}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Group gap={6}>
                    <Switch
                      size="sm"
                      checked={m.switchedOn && m.allowed}
                      disabled={!m.allowed}
                      onChange={(e) => update(m, { enabled: e.currentTarget.checked })}
                      aria-label={tr(`${m.name} eingeschaltet`, `${m.name} in use`)}
                    />
                    {m.switchedOn && m.missingDependencies.length > 0 && (
                      <Badge size="xs" color="orange" variant="light">
                        {tr('braucht', 'needs')} {m.missingDependencies.join(', ')}
                      </Badge>
                    )}
                  </Group>
                </Table.Td>
                <Table.Td>
                  <Switch
                    size="sm"
                    checked={m.allowed}
                    onChange={(e) => update(m, { allowed: e.currentTarget.checked })}
                    aria-label={tr(`${m.name} erlaubt`, `${m.name} allowed`)}
                  />
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
        </Table.ScrollContainer>
      )}
    </Paper>
  )
}
