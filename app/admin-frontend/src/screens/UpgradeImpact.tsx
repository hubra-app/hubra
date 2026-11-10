import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Alert, Badge, Button, Group, Paper, Stack, Table, Text, TextInput, Title } from '@mantine/core'
import { IconAlertTriangle, IconCircleCheck } from '@tabler/icons-react'
import { getUpgradeImpact, type ImpactRow } from '@/api/plugins'
import { tr } from '@/lang'

const STATE = {
  blocked: { color: 'red', label: () => tr('Keine Version passt', 'No version fits') },
  update: { color: 'orange', label: () => tr('Erst aktualisieren', 'Update first') },
  ok: { color: 'teal', label: () => tr('Passt', 'Fits') },
} as const

/**
 * Before a Hubra upgrade: which installed plugins would stop loading on
 * the new version (their `hubra:` range leaves it out), whether a version
 * in the repositories fixes that, and how many clubs use them.
 */
export function UpgradeImpactView() {
  // Empty: the backend checks the next minor version of what runs now.
  const [version, setVersion] = useState('')
  const [edited, setEdited] = useState<string | null>(null)
  const query = useQuery({
    queryKey: ['upgrade-impact', version],
    queryFn: () => getUpgradeImpact(version),
  })
  const data = query.data
  const draft = edited ?? data?.target ?? ''
  const setDraft = setEdited
  const problems = data ? data.counts.blocked + data.counts.update : 0
  return (
    <Stack gap="md">
      <Paper withBorder p="lg">
        <Title order={3} mb={4}>
          {tr('Vor einem Hubra-Update prüfen', 'Check before a Hubra upgrade')}
        </Title>
        <Text size="sm" c="dimmed" mb={12}>
          {tr(
            'Jedes Plugin nennt die Hubra-Versionen, mit denen es läuft. Hier siehst du, welche installierten Plugins mit der neuen Version nicht mehr laden und ob ein Plugin-Update hilft.',
            'Every plugin names the Hubra versions it runs on. This shows which installed plugins would no longer load on the new version, and whether a plugin update helps.',
          )}
        </Text>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            setVersion(draft.trim())
          }}
        >
          <Group align="flex-end" gap="sm" wrap="wrap">
            <TextInput
              label={tr('Neue Hubra-Version', 'New Hubra version')}
              description={data ? tr(`Läuft jetzt: ${data.current}`, `Running now: ${data.current}`) : undefined}
              value={draft}
              onChange={(e) => setDraft(e.currentTarget.value)}
              w={220}
              placeholder="0.3.0"
            />
            <Button type="submit" variant="default" loading={query.isFetching}>
              {tr('Prüfen', 'Check')}
            </Button>
          </Group>
        </form>
      </Paper>
      {query.isError && (
        <Alert color="red" variant="light">
          {(query.error as Error).message}
        </Alert>
      )}
      {data && (
        <Alert
          color={data.counts.blocked ? 'red' : problems ? 'orange' : 'teal'}
          variant="light"
          icon={problems ? <IconAlertTriangle size={18} /> : <IconCircleCheck size={18} />}
        >
          {problems === 0
            ? tr(
                `Alle ${data.plugins.length} installierten Plugins laufen mit Hubra ${data.target}.`,
                `All ${data.plugins.length} installed plugins run on Hubra ${data.target}.`,
              )
            : [
                data.counts.update
                  ? tr(
                      `${data.counts.update} vor dem Update aktualisieren`,
                      `${data.counts.update} to update before upgrading`,
                    )
                  : '',
                data.counts.blocked
                  ? tr(
                      `${data.counts.blocked} ohne Version für Hubra ${data.target}: sie laden danach nicht mehr`,
                      `${data.counts.blocked} without a version for Hubra ${data.target}: they would no longer load`,
                    )
                  : '',
              ]
                .filter(Boolean)
                .join(' · ')}
        </Alert>
      )}
      {data && data.plugins.length > 0 && (
        <Paper withBorder style={{ overflowX: 'auto' }}>
          <Table verticalSpacing="sm" miw={560}>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Plugin</Table.Th>
                <Table.Th>{tr('Installiert', 'Installed')}</Table.Th>
                <Table.Th>{tr('Braucht Hubra', 'Needs Hubra')}</Table.Th>
                <Table.Th>{tr(`Mit ${data.target}`, `On ${data.target}`)}</Table.Th>
                <Table.Th ta="right">{tr('Vereine', 'Clubs')}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.plugins.map((p) => (
                <ImpactLine key={p.id} p={p} />
              ))}
            </Table.Tbody>
          </Table>
        </Paper>
      )}
    </Stack>
  )
}

function ImpactLine({ p }: { p: ImpactRow }) {
  const s = STATE[p.state]
  return (
    <Table.Tr data-plugin={p.id}>
      <Table.Td>
        <Text size="sm" fw={600}>
          {p.name}
        </Text>
      </Table.Td>
      <Table.Td>
        <Text size="sm">{p.installedVersion}</Text>
      </Table.Td>
      <Table.Td>
        <Text size="sm" ff="monospace">
          {p.requiresHubra || tr('jede', 'any')}
        </Text>
      </Table.Td>
      <Table.Td>
        <Group gap={6} wrap="wrap">
          <Badge variant="light" color={s.color} size="sm">
            {s.label()}
          </Badge>
          {p.updateTo && (
            <Text size="xs" c="dimmed">
              {tr(`auf ${p.updateTo}`, `to ${p.updateTo}`)}
            </Text>
          )}
        </Group>
      </Table.Td>
      <Table.Td ta="right">
        <Text size="sm">{p.clubs ?? '–'}</Text>
      </Table.Td>
    </Table.Tr>
  )
}
