import { useMutation, useQuery } from '@tanstack/react-query'
import { Anchor, Badge, Button, Code, Group, Paper, Stack, Text, Title } from '@mantine/core'
import { tr } from '@/lang'
import { runPostDeploySteps, type BuildReport, type HealthDetail, type PostDeployStep } from '@/api/platform'
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
    'global-api': tr('Anmeldung & Konto (API)', 'Sign-in & account (API)'),
    worker: tr('Hintergrund-Worker', 'Background worker'),
    beat: tr('Zeitplaner (Beat)', 'Scheduler (beat)'),
    'discord-gateway': 'Discord-Gateway',
    // A split install (docs/platform-backend.md) runs these as well.
    'platform-api': tr('Plattform-Backend (API)', 'Platform backend (API)'),
    'platform-worker': tr('Plattform-Worker', 'Platform worker'),
  }
  const byComponent = new Map<string, BuildReport[]>()
  for (const r of reports) {
    // Beat from a release before the fix reported as platform-beat (role image).
    const component = r.component === 'platform-beat' ? 'beat' : r.component
    byComponent.set(component, [...(byComponent.get(component) ?? []), r])
  }

  // API, worker and beat always run; others (the Discord gateway) show once they report.
  const components = [...new Set(['api', 'worker', 'beat', ...byComponent.keys()])]
  const backendRows: BuildRow[] = components.map((name) => {
    const list = byComponent.get(name)
    if (!list) {
      // The answering API process knows its own commit even without Redis.
      if (name === 'api') return { key: name, label: labels.api, shas: [api] }
      return {
        key: name,
        label: labels[name] ?? name,
        note: health.processes_unknown
          ? tr('Unbekannt (Redis antwortet nicht)', 'Unknown (Redis did not answer)')
          : tr('Meldet sich nicht', 'Not reporting'),
      }
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
    <Paper withBorder p="lg">
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
                <Badge variant="light" color="orange" size="sm">
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
      <PostDeploy health={health} />
    </Paper>
  )
}

const STEP_COLOR = { done: 'teal', failed: 'red', skipped: 'gray' } as const

/** The last run of the post-deploy steps (migrations, seeds, permission
 * sync) and a button to run them again. */
function PostDeploy({ health }: { health: HealthDetail }) {
  const run = health.post_deploy
  const start = useMutation({ mutationFn: runPostDeploySteps })
  const steps = (run?.details.steps as PostDeployStep[] | undefined) ?? []
  const failed = run?.details.state === 'failed'
  return (
    <Stack gap={6} mt={14}>
      <Group justify="space-between" wrap="wrap">
        <Text fw={600} size="sm">
          {tr('Schritte nach dem Deploy', 'Post-deploy steps')}
        </Text>
        <Group gap={8}>
          {health.post_deploy_enabled === false && (
            <Badge variant="light" color="gray" size="sm">
              {tr('Automatisch: aus', 'Automatic: off')}
            </Badge>
          )}
          <Button
            size="xs"
            variant="default"
            loading={start.isPending}
            disabled={start.isSuccess}
            onClick={() => start.mutate()}
          >
            {start.isSuccess ? tr('Gestartet', 'Started') : tr('Jetzt ausführen', 'Run now')}
          </Button>
        </Group>
      </Group>
      {!run ? (
        <Text size="sm" c="dimmed">
          {tr('Noch nicht gelaufen.', 'Not run yet.')}
        </Text>
      ) : (
        <>
          <Text size="sm" c={failed ? 'red' : 'dimmed'}>
            {eventText(run)} · {formatDateTime(run.time)}
          </Text>
          {steps.map((step) => (
            <Group key={step.key} gap={8} wrap="nowrap" align="flex-start">
              <Badge variant="light" color={STEP_COLOR[step.state]} size="sm" miw={84}>
                {step.state === 'done'
                  ? tr('Erledigt', 'Done')
                  : step.state === 'failed'
                    ? tr('Fehler', 'Failed')
                    : tr('Ausgelassen', 'Skipped')}
              </Badge>
              <Stack gap={2} style={{ minWidth: 0 }}>
                <Text size="sm" ff={MONO}>
                  {step.label}
                  {step.seconds !== undefined && (
                    <Text span size="xs" c="dimmed">
                      {' '}
                      · {step.seconds} s
                    </Text>
                  )}
                </Text>
                {step.state === 'failed' && step.output && (
                  <Code block style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                    {step.output}
                  </Code>
                )}
              </Stack>
            </Group>
          ))}
        </>
      )}
    </Stack>
  )
}
