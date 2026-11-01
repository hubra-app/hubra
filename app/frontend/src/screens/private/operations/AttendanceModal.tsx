import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Group, SegmentedControl, Text } from '@mantine/core'
import { useT } from '@/locales/i18n'
import { useToast } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { Modal } from '@/components/ui'
import type { ClubEvent } from '@/types'
import { getRoll, saveRoll, type AttendanceStatus, type RollEntry } from '@/api/events'

type Choice = AttendanceStatus | 'none'

/** Organisers and trainers: who was there (present, excused, absent). */
export function AttendanceModal({
  event,
  onClose,
}: {
  event: ClubEvent | null
  onClose: () => void
}) {
  const { t, i18n } = useT()
  const when = event
    ? new Date(`${event.date}T00:00:00Z`).toLocaleDateString(i18n.language, {
        weekday: 'short',
        day: 'numeric',
        month: 'long',
        year: 'numeric',
        timeZone: 'UTC',
      })
    : ''
  return (
    <Modal
      open={!!event}
      onClose={onClose}
      wide
      title={t('events.attendance.title', 'Anwesenheit')}
      subtitle={event ? `${event.title} · ${when}` : undefined}
    >
      {event && <Roll key={event.id} event={event} onClose={onClose} />}
    </Modal>
  )
}

function Roll({ event, onClose }: { event: ClubEvent; onClose: () => void }) {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: qk.eventRoll(event.id),
    queryFn: () => getRoll(event.id),
    staleTime: 0,
  })
  const [changes, setChanges] = useState<Record<number, Choice>>({})
  const [saving, setSaving] = useState(false)
  const rows: RollEntry[] = data ?? []
  const choiceOf = (r: RollEntry): Choice => changes[r.memberId] ?? r.status ?? 'none'
  const pick = (memberId: number, choice: Choice) =>
    setChanges((prev) => ({ ...prev, [memberId]: choice }))
  const allPresent = () =>
    setChanges(
      Object.fromEntries(
        rows.filter((r) => choiceOf(r) === 'none').map((r) => [r.memberId, 'present']),
      ) as Record<number, Choice>,
    )

  const save = async () => {
    const entries = Object.entries(changes).map(([id, choice]) => ({
      memberId: Number(id),
      status: choice === 'none' ? null : choice,
    }))
    setSaving(true)
    try {
      const saved = await saveRoll(event.id, entries)
      queryClient.setQueryData(qk.eventRoll(event.id), saved)
      await queryClient.invalidateQueries({ queryKey: qk.attendance })
      notify('success', t('events.attendance.saved', 'Anwesenheit gespeichert'), event.title)
      onClose()
    } catch (err: unknown) {
      notify('error', t('common.error'), err instanceof Error ? err.message : '')
    } finally {
      setSaving(false)
    }
  }

  if (isLoading) return null
  const present = rows.filter((r) => choiceOf(r) === 'present').length
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {rows.length === 0 ? (
        <Text size="sm" c="dimmed">
          {t(
            'events.attendance.nobody',
            'Niemand erwartet: gib dem Anlass eine Gruppe oder melde Mitglieder an.',
          )}
        </Text>
      ) : (
        <>
          <Group justify="space-between">
            <Text size="sm" c="dimmed">
              {t('events.attendance.count', '{{present}} von {{count}} anwesend', {
                present,
                count: rows.length,
              })}
            </Text>
            <Button size="compact-sm" variant="default" onClick={allPresent}>
              {t('events.attendance.allPresent', 'Übrige anwesend')}
            </Button>
          </Group>
          {rows.map((r) => (
            <Group key={r.memberId} justify="space-between" wrap="wrap" gap={8}>
              <Text size="sm" fw={500}>
                {r.memberName}
              </Text>
              <SegmentedControl
                size="xs"
                value={choiceOf(r)}
                onChange={(v) => pick(r.memberId, v as Choice)}
                data={[
                  { value: 'present', label: t('events.attendance.present', 'Da') },
                  { value: 'excused', label: t('events.attendance.excused', 'Entschuldigt') },
                  { value: 'absent', label: t('events.attendance.absent', 'Fehlt') },
                  { value: 'none', label: '–' },
                ]}
              />
            </Group>
          ))}
        </>
      )}
      <Group justify="flex-end" gap="xs" mt="sm">
        <Button variant="default" onClick={onClose}>
          {t('common.cancel')}
        </Button>
        <Button
          onClick={save}
          loading={saving}
          disabled={Object.keys(changes).length === 0}
        >
          {t('common.save')}
        </Button>
      </Group>
    </div>
  )
}
