import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Anchor, Badge, Group, Paper, SegmentedControl, Stack, Text, Title } from '@mantine/core'
import { useAdmin } from '@/context/AdminContext'
import { getLang, tr } from '@/lang'
import { getFeatures, setFeatureStage, type FeatureFlag, type FeatureStage } from '@/api/platform'

function FlagRow({ flag, total, onSaved }: { flag: FeatureFlag; total: number; onSaved: () => void }) {
  const { notify } = useAdmin()
  const [busy, setBusy] = useState(false)
  const en = getLang() === 'en'
  const forced = flag.forced_on.length + flag.forced_off.length

  const change = async (stage: FeatureStage) => {
    setBusy(true)
    try {
      await setFeatureStage(flag.key, stage)
      onSaved()
    } catch (err) {
      notify('error', tr('Speichern fehlgeschlagen', 'Could not save'), err instanceof Error ? err.message : undefined)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Paper withBorder p="md">
      <Group justify="space-between" align="flex-start" gap="md" wrap="wrap">
        <Stack gap={2} style={{ flex: '1 1 280px' }}>
          <Group gap={8}>
            <Text fw={600}>{en ? flag.title_en : flag.title_de}</Text>
            <Text size="xs" c="dimmed" ff="'JetBrains Mono', monospace">
              {flag.key}
            </Text>
          </Group>
          {(en ? flag.description_en : flag.description_de) && (
            <Text size="sm" c="dimmed">
              {en ? flag.description_en : flag.description_de}
            </Text>
          )}
          <Text size="xs" c="dimmed" mt={4}>
            {tr(`An bei ${flag.clubs_on} von ${total} Vereinen`, `On for ${flag.clubs_on} of ${total} clubs`)}
            {forced > 0 &&
              tr(
                ` · ${forced} ${forced === 1 ? 'Verein hat' : 'Vereine haben'} eine eigene Einstellung`,
                ` · ${forced} ${forced === 1 ? 'club has' : 'clubs have'} their own setting`,
              )}
          </Text>
        </Stack>
        <SegmentedControl
          size="xs"
          value={flag.stage}
          disabled={busy}
          onChange={(v) => change(v as FeatureStage)}
          data={[
            { value: 'off', label: tr('Aus', 'Off') },
            { value: 'early', label: tr('Testgruppe', 'Early group') },
            { value: 'all', label: tr('Alle Vereine', 'All clubs') },
          ]}
          aria-label={tr('Stufe', 'Stage')}
        />
      </Group>
    </Paper>
  )
}

/**
 * New features club by club: each gated feature is off, on for the
 * early-access group, or on for everybody (services/feature_flags.py).
 */
export function EarlyAccess() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ['platform-features'], queryFn: getFeatures })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['platform-features'] })

  return (
    <Stack gap={20} maw={820}>
      <Text size="sm" c="dimmed">
        {tr(
          'Alle Vereine laufen auf derselben Version. Neue Funktionen lassen sich trotzdem zuerst einer Testgruppe zeigen: Stell eine Funktion auf «Testgruppe», prüfe sie dort, und gib sie danach für alle Vereine frei. Welche Vereine zur Testgruppe gehören, legst du beim Verein fest.',
          'Every club runs the same build. New features can still go to an early group first: set a feature to “Early group”, check it there, then turn it on for all clubs. Which clubs are in the early group is set on each club.',
        )}
      </Text>

      <Paper withBorder p="md">
        <Group justify="space-between" mb={8}>
          <Title order={4}>{tr('Testgruppe', 'Early group')}</Title>
          <Badge variant="light">{data?.early_access.length ?? 0}</Badge>
        </Group>
        {data && data.early_access.length === 0 ? (
          <Text size="sm" c="dimmed">
            {tr(
              'Noch kein Verein. Öffne einen Verein unter «Alle Vereine» und schalte dort «Früher Zugang» ein.',
              'No club yet. Open a club under “All clubs” and turn on “Early access” there.',
            )}
          </Text>
        ) : (
          <Group gap={8}>
            {data?.early_access.map((c) => (
              <Badge
                key={c.id}
                variant="outline"
                size="lg"
                tt="none"
                style={{ cursor: 'pointer' }}
                onClick={() => navigate(`/app/tenants/${c.id}`)}
              >
                {c.name}
              </Badge>
            ))}
          </Group>
        )}
      </Paper>

      <Stack gap={10}>
        <Title order={4}>{tr('Funktionen', 'Features')}</Title>
        {isLoading && (
          <Text size="sm" c="dimmed">
            {tr('Wird geladen …', 'Loading…')}
          </Text>
        )}
        {data && data.flags.length === 0 && (
          <Text size="sm" c="dimmed">
            {tr(
              'In dieser Version ist keine Funktion im frühen Zugang. Wie eine neue Funktion hinter einen Schalter kommt, steht in ',
              'No feature is in early access in this build. How a new feature goes behind a switch is described in ',
            )}
            <Anchor
              size="sm"
              href="https://github.com/hubra-app/hubra/blob/main/docs/feature-flags.md"
              target="_blank"
              rel="noreferrer"
            >
              docs/feature-flags.md
            </Anchor>
            .
          </Text>
        )}
        {data?.flags.map((f) => <FlagRow key={f.key} flag={f} total={data.clubs_total} onSaved={refresh} />)}
      </Stack>
    </Stack>
  )
}
