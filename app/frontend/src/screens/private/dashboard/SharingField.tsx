import { useQuery } from '@tanstack/react-query'
import { MultiSelect, SegmentedControl, Stack, Text } from '@mantine/core'
import { useT } from '@/locales/i18n'
import { qk } from '@/data/keys'
import { listGroups } from '@/api/groups'
import type { Sharing, Visibility } from './sharing'

/**
 * Who sees a dashboard: only me, the whole club, or chosen groups. Shown
 * only to members with the right to share (dashboards.dashboards.share).
 */
export function SharingField({
  value,
  onChange,
  onlyStop = false,
}: {
  value: Sharing
  onChange: (next: Sharing) => void
  /** Someone else's dashboard (an admin): they may only stop sharing it. */
  onlyStop?: boolean
}) {
  const { t } = useT()
  const groups = useQuery({
    queryKey: qk.groups.all,
    queryFn: listGroups,
    enabled: value.visibility === 'groups',
  })
  return (
    <Stack gap={6}>
      <Text fz="sm" fw={500}>
        {t('dashboards.visibility', 'Wer sieht es')}
      </Text>
      <SegmentedControl
        fullWidth
        value={value.visibility}
        onChange={(v) => onChange({ ...value, visibility: v as Visibility })}
        data={[
          { value: 'private', label: t('dashboards.private', 'Privat') },
          { value: 'club', label: t('dashboards.visClub', 'Ganzer Verein') },
          { value: 'groups', label: t('dashboards.visGroups', 'Gruppen') },
        ].map((o) => ({
          ...o,
          disabled: onlyStop && o.value !== 'private' && o.value !== value.visibility,
        }))}
      />
      {value.visibility === 'groups' && (
        <MultiSelect
          searchable
          disabled={onlyStop}
          aria-label={t('dashboards.visGroupsPick', 'Gruppen wählen')}
          placeholder={t('dashboards.visGroupsPick', 'Gruppen wählen')}
          data={(groups.data ?? []).map((g) => ({ value: String(g.id), label: g.name }))}
          value={value.groupIds.map(String)}
          onChange={(ids) => onChange({ ...value, groupIds: ids.map(Number) })}
          error={
            value.groupIds.length === 0
              ? t('dashboards.visGroupsNone', 'Wähle mindestens eine Gruppe.')
              : undefined
          }
        />
      )}
      <Text fz="xs" c="dimmed">
        {value.visibility === 'private'
          ? t('dashboards.visPrivateHint', 'Nur du siehst es.')
          : value.visibility === 'club'
            ? t(
                'dashboards.visClubHint',
                'Alle Mitglieder sehen es, jedes nur mit den Widgets, die es sehen darf.',
              )
            : t(
                'dashboards.visGroupsHint',
                'Nur die Mitglieder dieser Gruppen sehen es, jedes nur mit den Widgets, die es sehen darf.',
              )}
      </Text>
    </Stack>
  )
}
