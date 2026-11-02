import { useQuery } from '@tanstack/react-query'
import { Anchor, Badge, Group, Paper, Text, Title } from '@mantine/core'
import { tr } from '@/lang'
import type { BuildReport, HealthDetail } from '@/api/platform'
import { SSO_URL } from '@hubra/api-client'
import { Row } from './StatusRow'
import { eventText } from './eventLabels'
import { formatDateTime } from '@/format'

const MONO = "'JetBrains Mono', monospace"
const REPO_URL = 'https://github.com/hubra-app/hubra'
const COS_URL = import.meta.env.VITE_COS_URL ?? 'https://app.hubra.club'

/**
 * The commit a frontend image was built from: its /version.json (written by
 * the Dockerfile). Undefined when it can't be read, "" for a build without
 * one (local build or dev server, shown as "dev").
 */
async function frontendCommit(base: string): Promise<string | undefined> {
  try {
    const url = new URL('/version.json', new URL(base, window.location.href)).toString()
    const res = await fetch(url, { cache: 'no-store', credentials: 'omit' })
    if (!res.ok) return undefined
    // The dev server answers every path with index.html.
    if (!(res.headers.get('content-type') ?? '').includes('json')) return ''
    const data = (await res.json()) as { commit?: unknown }
    return typeof data.commit === 'string' ? data.commit : ''
  } catch {
    return undefined
  }
}

/** Short hash linked to the commit, or "dev" for a build without one. */
export function CommitLink({ sha }: { sha: string | null }) {
  if (!sha) {
    return (
      <Badge variant="light" color="gray" size="sm">
        dev
      </Badge>
    )
  }
  return (
    <Anchor href={`${REPO_URL}/commit/${sha}`} target="_blank" rel="noreferrer" size="sm" ff={MONO}>
      {sha.slice(0, 7)}
    </Anchor>
  )
}

interface BuildRow {
  key: string
  label: string
  /** Commits it runs; several while a roll-out is half done. Undefined: unknown. */
  shas?: (string | null)[]
  note?: string
  hosts?: string
}

export function BuildsPanel({ health }: { health: HealthDetail }) {
  const frontends = useQuery({
    queryKey: ['frontend-builds'],
    queryFn: async () => {
      const [app, manage, sso] = await Promise.all([
        frontendCommit(COS_URL),
        frontendCommit(window.location.origin),
        frontendCommit(SSO_URL),
      ])
      return { app, manage, sso }
    },
  })

  const api = health.commit ?? null
  const reports = health.processes ?? []
  const labels: Record<string, string> = {
    api: tr('Backend (API)', 'Backend (API)'),
    worker: tr('Hintergrund-Worker', 'Background worker'),
    beat: tr('Zeitplaner (Beat)', 'Scheduler (beat)'),
    'discord-gateway': 'Discord-Gateway',
    // A split install (docs/platform-backend.md) runs these as well.
    'platform-api': tr('Plattform-Backend (API)', 'Platform backend (API)'),
    'platform-worker': tr('Plattform-Worker', 'Platform worker'),
  }
  const byComponent = new Map<string, BuildReport[]>()
  for (const r of reports) byComponent.set(r.component, [...(byComponent.get(r.component) ?? []), r])

  // API, worker and beat always run; others (the Discord gateway) show once they report.
  const components = [...new Set(['api', 'worker', 'beat', ...byComponent.keys()])]
  const backendRows: BuildRow[] = components.map((name) => {
    const list = byComponent.get(name)
    if (!list) {
      // The answering API process knows its own commit even without Redis.
      if (name === 'api') return { key: name, label: labels.api, shas: [api] }
      return { key: name, label: labels[name] ?? name, note: tr('Meldet sich nicht', 'Not reporting') }
    }
    return {
      key: name,
      label: labels[name] ?? name,
      shas: [...new Set(list.map((r) => r.commit))],
      hosts: list.length > 1 ? tr(`${list.length} Instanzen`, `${list.length} instances`) : undefined,
    }
  })
  const front = (sha: string | undefined): Pick<BuildRow, 'shas' | 'note'> =>
    sha === undefined ? { note: tr('Nicht erreichbar', 'Not reachable') } : { shas: [sha || null] }
  const rows: BuildRow[] = [
    ...backendRows,
    { key: 'app', label: tr('Vereins-App', 'Club app'), ...front(frontends.data?.app) },
    { key: 'manage', label: 'Manage', ...front(frontends.data?.manage) },
    { key: 'sso', label: 'SSO', ...front(frontends.data?.sso) },
  ]
  const upgrade = health.last_upgrade

  return (
    <Paper withBorder shadow="sm" radius="lg" p="lg">
      <Title order={3} mb={4}>
        Builds
      </Title>
      <Text size="sm" c="dimmed" mb={8}>
        {tr(
          'Aus welchem Commit jedes laufende Image gebaut wurde. Weicht eines vom Backend ab, hat es der letzte Deploy nicht erneuert.',
          'The commit each running image was built from. One that differs from the backend was not replaced by the last deploy.',
        )}
      </Text>
      {rows.map((row) => {
        const loading = frontends.isLoading && ['app', 'manage', 'sso'].includes(row.key)
        const differs = !!api && !!row.shas?.some((sha) => sha !== api)
        const ok = loading || !row.shas || !api ? null : !differs
        return (
          <Row key={row.key} ok={ok === false ? null : ok} label={row.label}>
            <Group gap={8} wrap="wrap">
              {loading ? (
                <Text size="sm" c="dimmed">
                  {tr('Wird geprüft …', 'Checking…')}
                </Text>
              ) : row.note ? (
                <Text size="sm" c="dimmed">
                  {row.note}
                </Text>
              ) : (
                row.shas?.map((sha) => <CommitLink key={sha ?? 'dev'} sha={sha} />)
              )}
              {row.hosts && (
                <Text size="xs" c="dimmed">
                  {row.hosts}
                </Text>
              )}
              {differs && (
                <Badge variant="light" color="yellow" size="sm">
                  {tr('Weicht ab', 'Differs')}
                </Badge>
              )}
            </Group>
          </Row>
        )
      })}
      {upgrade && (
        <Text size="sm" c="dimmed" mt={10}>
          {eventText(upgrade)} ·{' '}
          {formatDateTime(upgrade.time)}
        </Text>
      )}
    </Paper>
  )
}
