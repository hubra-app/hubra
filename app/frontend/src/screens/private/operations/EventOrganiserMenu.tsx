import { useState } from 'react'
import { ActionIcon, Menu } from '@mantine/core'
import {
  IconCalendarCheck,
  IconCalendarOff,
  IconClipboardCheck,
  IconDots,
  IconPencil,
  IconTemplate,
  IconTrash,
  IconUserQuestion,
} from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useToast } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { useListCache } from '@/data/lists'
import { reinstateEvent } from '@/api/events'
import type { ClubEvent } from '@/types'
import { isPastEvent } from './eventDates'
import { useEventPerms } from './eventPerms'
import { PendingSignUpsModal } from './PendingSignUpsModal'
import { AttendanceModal } from './AttendanceModal'
import { CancelEventModal } from './CancelEventModal'
import { SaveTemplateModal } from './EventTemplates'

/**
 * The organisers' actions on one event, behind one "…" button: sign-ups to
 * approve, the attendance roll, calling it off, saving it as a template,
 * editing and deleting. Members without any of these rights see nothing.
 */
export function EventOrganiserMenu({
  ev,
  onEdit,
  onDelete,
}: {
  ev: ClubEvent
  onEdit?: () => void
  onDelete?: () => void
}) {
  const { t } = useT()
  const { notify } = useToast()
  const perms = useEventPerms()
  const eventCache = useListCache<ClubEvent>(qk.events)
  const [open, setOpen] = useState<'pending' | 'roll' | 'cancel' | 'template' | null>(null)
  const over = isPastEvent(ev)
  const mayUpdate = perms.canUpdate(ev)

  const reinstate = async () => {
    try {
      await reinstateEvent(ev.id)
      eventCache.patch(ev.id, (e) => ({ ...e, cancelledAt: null, cancelReason: null }))
      notify(
        'success',
        t('events.cancel.reinstated', 'Anlass findet statt'),
        t('events.cancel.reinstatedMsg', 'Die Angemeldeten wurden benachrichtigt.'),
      )
    } catch {
      notify('error', t('events.cancel.reinstateFailed', 'Das hat nicht geklappt'))
    }
  }

  const pending = perms.canApprove(ev) && (ev.pendingCount ?? 0) > 0
  const roll = perms.canTakeRoll(ev)
  const cancel = mayUpdate && !over
  const edit = mayUpdate && !!onEdit
  const remove = perms.canDelete(ev) && !!onDelete
  if (!pending && !roll && !cancel && !perms.canTemplates && !edit && !remove) return null

  return (
    <>
      <Menu position="bottom-end" withinPortal shadow="md">
        <Menu.Target>
          <ActionIcon
            variant="subtle"
            color="gray"
            size="lg"
            aria-label={t('events.menu.label', 'Aktionen für {{title}}', { title: ev.title })}
            data-testid="event-menu"
          >
            <IconDots size={18} />
          </ActionIcon>
        </Menu.Target>
        <Menu.Dropdown>
          {pending && (
            <Menu.Item leftSection={<IconUserQuestion size={16} />} onClick={() => setOpen('pending')}>
              {t('events.pendingCount', '{{count}} offen', { count: ev.pendingCount })}
            </Menu.Item>
          )}
          {roll && (
            <Menu.Item leftSection={<IconClipboardCheck size={16} />} onClick={() => setOpen('roll')}>
              {t('events.attendance.take', 'Anwesenheit erfassen')}
            </Menu.Item>
          )}
          {perms.canTemplates && (
            <Menu.Item
              leftSection={<IconTemplate size={16} />}
              data-testid="save-template"
              onClick={() => setOpen('template')}
            >
              {t('events.templates.saveTitle', 'Als Vorlage speichern')}
            </Menu.Item>
          )}
          {edit && (
            <Menu.Item leftSection={<IconPencil size={16} />} onClick={onEdit}>
              {t('common.edit', 'Bearbeiten')}
            </Menu.Item>
          )}
          {(cancel || remove) && <Menu.Divider />}
          {cancel &&
            (ev.cancelledAt ? (
              <Menu.Item
                color="green"
                leftSection={<IconCalendarCheck size={16} />}
                data-testid="reinstate-event"
                onClick={() => void reinstate()}
              >
                {t('events.cancel.reinstate', 'Doch durchführen')}
              </Menu.Item>
            ) : (
              <Menu.Item
                color="red"
                leftSection={<IconCalendarOff size={16} />}
                data-testid="cancel-event"
                onClick={() => setOpen('cancel')}
              >
                {t('events.cancel.action', 'Absagen')}
              </Menu.Item>
            ))}
          {remove && (
            <Menu.Item color="red" leftSection={<IconTrash size={16} />} onClick={onDelete}>
              {t('common.delete', 'Löschen')}
            </Menu.Item>
          )}
        </Menu.Dropdown>
      </Menu>
      <PendingSignUpsModal
        event={open === 'pending' ? ev : null}
        onClose={() => setOpen(null)}
        onDecided={(next) => eventCache.patch(next.id, () => next)}
      />
      <AttendanceModal event={open === 'roll' ? ev : null} onClose={() => setOpen(null)} />
      <CancelEventModal event={open === 'cancel' ? ev : null} onClose={() => setOpen(null)} />
      <SaveTemplateModal event={open === 'template' ? ev : null} onClose={() => setOpen(null)} />
    </>
  )
}
