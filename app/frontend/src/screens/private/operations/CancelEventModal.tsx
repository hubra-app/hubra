import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Button, Chip, Group, Text, Textarea } from '@mantine/core'
import { useT } from '@/locales/i18n'
import { Modal } from '@/components/ui'
import { useToast } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { useListCache } from '@/data/lists'
import { cancelEvent } from '@/api/events'
import type { ClubEvent } from '@/types'

const MAX = 500

/** "Absagen": call an event off with a reason. One tap on a common reason,
 * or a reason of one's own; those signed up and the event's group hear it
 * on their channels. */
export function CancelEventModal({ event, onClose }: { event: ClubEvent | null; onClose: () => void }) {
  const { t } = useT()
  const { notify } = useToast()
  const events = useListCache<ClubEvent>(qk.events)
  const [reason, setReason] = useState('')

  const quick = [
    t('events.cancel.quick.weather', 'Schlechtes Wetter'),
    t('events.cancel.quick.venue', 'Platz gesperrt'),
    t('events.cancel.quick.few', 'Zu wenige Anmeldungen'),
    t('events.cancel.quick.ill', 'Leitung krank'),
  ]

  const mutation = useMutation({
    mutationFn: ({ id, why }: { id: string; why: string }) => cancelEvent(id, why),
    onSuccess: (updated) => {
      events.patch(updated.id, (ev) => ({
        ...ev,
        cancelledAt: updated.cancelledAt,
        cancelReason: updated.cancelReason,
      }))
      notify(
        'info',
        t('events.cancel.done', 'Anlass abgesagt'),
        t('events.cancel.doneMsg', 'Alle Angemeldeten wurden benachrichtigt.'),
      )
      setReason('')
      onClose()
    },
    onError: () => notify('error', t('events.cancel.failed', 'Absagen fehlgeschlagen')),
  })

  const close = () => {
    setReason('')
    onClose()
  }
  const trimmed = reason.trim()

  return (
    <Modal
      open={event !== null}
      onClose={close}
      title={t('events.cancel.title', '{{title}} absagen', { title: event?.title ?? '' })}
      subtitle={t(
        'events.cancel.subtitle',
        'Der Anlass bleibt im Kalender, als abgesagt markiert. Wer angemeldet ist und die Gruppe des Anlasses erfahren es mit dem Grund (Glocke, Push, Mail, Messenger).',
      )}
      footer={
        <>
          <Button variant="default" onClick={close}>
            {t('common.cancel')}
          </Button>
          <Button
            color="red"
            disabled={!trimmed || trimmed.length > MAX}
            loading={mutation.isPending}
            onClick={() => event && mutation.mutate({ id: event.id, why: trimmed })}
            data-testid="confirm-cancel-event"
          >
            {t('events.cancel.confirm', 'Absagen')}
          </Button>
        </>
      }
    >
      <Text size="sm" fw={500}>
        {t('events.cancel.quickLabel', 'Häufige Gründe')}
      </Text>
      <Group gap="xs">
        {quick.map((q) => (
          <Chip key={q} checked={reason === q} onChange={() => setReason(q)} size="sm">
            {q}
          </Chip>
        ))}
      </Group>
      <Textarea
        label={t('events.cancel.reason', 'Grund')}
        value={reason}
        onChange={(e) => setReason(e.currentTarget.value)}
        maxLength={MAX}
        autosize
        minRows={2}
        required
        data-testid="cancel-reason"
      />
    </Modal>
  )
}
