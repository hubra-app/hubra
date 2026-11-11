import { Button } from '@mantine/core'
import { useT } from '@/locales/i18n'
import { useToast } from '@/context/AppContext'
import { ConfirmModal, Modal } from '@/components/ui'
import { qk } from '@/data/keys'
import { useListCache } from '@/data/lists'
import { deleteEvent, type SeriesScope } from '@/api/events'
import type { ClubEvent } from '@/types'

/**
 * Deleting an event: a plain confirmation, or for a date of a series the
 * choice between this date and this one with all that follow.
 */
export function DeleteEventModal({
  event,
  onClose,
  onDeleted,
}: {
  event: ClubEvent | null
  onClose: () => void
  onDeleted?: () => void
}) {
  const { t } = useT()
  const { notify } = useToast()
  const eventCache = useListCache<ClubEvent>(qk.events)

  const confirm = async (scope: SeriesScope = 'this') => {
    if (!event) return
    try {
      await deleteEvent(event.id, scope)
      if (scope === 'following') {
        await eventCache.invalidate()
      } else {
        eventCache.remove(event.id)
      }
      notify('info', t('events.event.deleted'), t('events.event.deletedMsg', { title: event.title }))
      onDeleted?.()
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    }
  }
  const title = t('events.deleteEventTitle', '{{title}} löschen?', { title: event?.title ?? '' })

  return (
    <>
      <Modal
        open={!!event?.seriesId}
        onClose={onClose}
        title={title}
        subtitle={event?.date}
        footer={
          <>
            <Button variant="default" onClick={onClose}>
              {t('common.cancel')}
            </Button>
            <Button
              variant="light"
              color="red"
              onClick={() => {
                void confirm('this')
                onClose()
              }}
            >
              {t('events.series.deleteThis', 'Nur diesen Termin')}
            </Button>
            <Button
              variant="filled"
              color="red"
              onClick={() => {
                void confirm('following')
                onClose()
              }}
            >
              {t('events.series.deleteFollowing', 'Diesen und alle folgenden')}
            </Button>
          </>
        }
      >
        {t(
          'events.series.deleteBody',
          'Der Termin gehört zu einer Serie. Gelöschte Termine und ihre Anmeldungen sind endgültig weg.',
        )}
      </Modal>
      <ConfirmModal
        open={!!event && !event.seriesId}
        onClose={onClose}
        title={title}
        body={t('events.deleteEventBody', 'Der Anlass und seine Teilnehmerliste werden endgültig gelöscht.')}
        onConfirm={() => confirm()}
      />
    </>
  )
}
