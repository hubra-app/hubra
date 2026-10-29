import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Button, Group, Text } from '@mantine/core'
import { useT } from '@/locales/i18n'
import { useToast } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { Modal } from '@/components/ui'
import type { ClubEvent } from '@/types'
import {
  decideRegistration,
  listRegistrations,
  type EventRegistration,
} from '@/api/events'

/** Organisers: the sign-ups of an event that wait for approval. */
export function PendingSignUpsModal({
  event,
  onClose,
  onDecided,
}: {
  event: ClubEvent | null
  onClose: () => void
  onDecided: (ev: ClubEvent) => void
}) {
  const { t } = useT()
  return (
    <Modal
      open={!!event}
      onClose={onClose}
      title={t('events.pendingTitle', 'Offene Anmeldungen')}
      subtitle={event?.title}
      footer={
        <Button variant="default" onClick={onClose}>
          {t('common.close', 'Schliessen')}
        </Button>
      }
    >
      {event && <PendingList key={event.id} event={event} onDecided={onDecided} />}
    </Modal>
  )
}

function PendingList({
  event,
  onDecided,
}: {
  event: ClubEvent
  onDecided: (ev: ClubEvent) => void
}) {
  const { t } = useT()
  const { notify } = useToast()
  const [current, setCurrent] = useState(event)
  const [decided, setDecided] = useState<number[]>([])
  const [busy, setBusy] = useState<number | null>(null)
  const { data, isLoading } = useQuery({
    queryKey: qk.eventPending(event.id),
    queryFn: () => listRegistrations(event.id, 'pending'),
    staleTime: 0,
  })
  const pending = (data ?? []).filter((r) => !decided.includes(r.id))

  const decide = async (reg: EventRegistration, decision: 'approve' | 'decline') => {
    setBusy(reg.memberId)
    try {
      const result = await decideRegistration(current.id, reg.memberId, decision)
      setDecided((prev) => [...prev, reg.id])
      const gotPlace = result.status === 'approved'
      const next: ClubEvent = {
        ...current,
        pendingCount: Math.max(0, (current.pendingCount ?? 1) - 1),
        placesTaken: (current.placesTaken ?? 0) + (gotPlace ? 1 + reg.guests : 0),
        attendees: gotPlace
          ? [...current.attendees, String(reg.memberId)]
          : current.attendees,
      }
      setCurrent(next)
      onDecided(next)
    } catch (err: unknown) {
      notify('error', t('common.error'), err instanceof Error ? err.message : '')
    } finally {
      setBusy(null)
    }
  }

  if (isLoading) return null
  if (pending.length === 0) {
    return (
      <Text size="sm" c="dimmed">
        {t('events.noPending', 'Keine offenen Anmeldungen.')}
      </Text>
    )
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {pending.map((reg) => (
        <Group key={reg.id} justify="space-between" wrap="nowrap">
          <Text size="sm">
            {reg.memberName ?? `#${reg.memberId}`}
            {reg.guests > 0 &&
              ` + ${t('events.guests', '{{count}} Gäste', { count: reg.guests })}`}
          </Text>
          <Group gap={4} wrap="nowrap">
            <Button
              size="compact-sm"
              variant="default"
              disabled={busy !== null}
              onClick={() => decide(reg, 'decline')}
            >
              {t('events.decline', 'Ablehnen')}
            </Button>
            <Button
              size="compact-sm"
              loading={busy === reg.memberId}
              disabled={busy !== null && busy !== reg.memberId}
              onClick={() => decide(reg, 'approve')}
            >
              {t('events.approve', 'Bestätigen')}
            </Button>
          </Group>
        </Group>
      ))}
    </div>
  )
}
