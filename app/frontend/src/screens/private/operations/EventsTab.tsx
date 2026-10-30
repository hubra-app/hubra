import { EVENT_TYPE_COLORS } from '@/constants'
import { useState } from 'react'
import { Button, Group, TextInput, Select, Badge, Checkbox } from '@mantine/core'
import { useForm } from '@mantine/form'
import { zod4Resolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { useT, zmsg } from '@/locales/i18n'
import i18n from 'i18next'
import {
  IconPlus,
  IconUserCheck,
  IconLogin,
  IconLogout as Leave,
} from '@tabler/icons-react'
import { useToast, useAuth } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { useEvents, useListCache, useMyJoinedEvents } from '@/data/lists'
import {
  Modal,
  Field,
  usePagination,
  ConfirmModal,
  DataTable,
  ActionButtons,
  useSubmitOnce,
} from '@/components/ui'
import type { ClubEvent } from '@/types'
import { createEvent, updateEvent, deleteEvent } from '@/api/events'
import {
  hasOpenSignUp,
  useToggleJoinEvent,
} from '@/screens/private/operations/useEventActions'
import { CalendarSubscribeButton } from './CalendarSubscribeButton'
import { PendingSignUpsModal } from './PendingSignUpsModal'

/* ── Events ─────────────────────────────────── */
const eventSchema = z.object({
  title: z.string().min(1, zmsg('validation.titleRequired', 'Titel ist erforderlich')),
  date: z.string().min(1, zmsg('validation.dateRequired', 'Datum ist erforderlich')),
  time: z.string(),
  location: z.string(),
  type: z.string(),
  // Empty: no limit.
  maxAttendees: z
    .string()
    .regex(/^\d*$/, zmsg('validation.wholeNumber', 'Bitte eine ganze Zahl eingeben')),
  requiresApproval: z.boolean(),
})
type EventForm = z.infer<typeof eventSchema>

const limitOf = (value: string) => (value.trim() ? Number(value) : null)


const EVENT_TYPES = ['Workshop', 'Social', 'Certification', 'Meeting']

/** Stored event types are English keys; show them in the user's language. */
function eventTypeLabel(type: string) {
  const defaults: Record<string, string> = {
    Workshop: 'Workshop',
    Social: 'Geselliges',
    Certification: 'Einführung',
    Meeting: 'Sitzung',
  }
  return defaults[type]
    ? i18n.t(`events.types.${type.toLowerCase()}`, defaults[type])
    : type
}

export function EventsTab() {
  const { notify } = useToast()
  const { events } = useEvents()
  const myJoinedEvents = useMyJoinedEvents()
  const eventCache = useListCache<ClubEvent>(qk.events)
  const { currentUser, hasPermission } = useAuth()
  const { t, i18n } = useT()
  const joinEventMutation = useToggleJoinEvent()
  const canCreate = hasPermission('events.events.create')
  const canUpdate = hasPermission('events.events.update')
  const canDelete = hasPermission('events.events.delete')
  const canApprove = hasPermission('events.events.add_attendee')
  const [pendingFor, setPendingFor] = useState<ClubEvent | null>(null)
  const [typeFilter, setTypeFilter] = useState('All')
  const [search, setSearch] = useState('')
  const [addOpen, setAddOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<ClubEvent | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<ClubEvent | null>(null)
  const form = useForm<EventForm>({
    validate: zod4Resolver(eventSchema),
    initialValues: {
      title: '',
      date: new Date().toISOString().slice(0, 10),
      time: '',
      location: '',
      type: 'Workshop',
      maxAttendees: '',
      requiresApproval: false,
    },
  })

  const types = ['All', ...EVENT_TYPES]
  const filtered = events.filter((e) => {
    const matchType = typeFilter === 'All' || e.type === typeFilter
    const q = search.toLowerCase()
    const matchSearch =
      !q ||
      e.title.toLowerCase().includes(q) ||
      (e.location || '').toLowerCase().includes(q)
    return matchType && matchSearch
  })
  const pg = usePagination(filtered, 10)

  const openAdd = () => {
    form.setValues({
      title: '',
      date: new Date().toISOString().slice(0, 10),
      time: '',
      location: '',
      type: 'Workshop',
      maxAttendees: '',
      requiresApproval: false,
    })
    setAddOpen(true)
  }
  const openEdit = (ev: ClubEvent) => {
    setEditTarget(ev)
    form.setValues({
      title: ev.title,
      date: ev.date,
      time: ev.time ?? '',
      location: ev.location ?? '',
      type: ev.type,
      maxAttendees: ev.maxAttendees ? String(ev.maxAttendees) : '',
      requiresApproval: ev.requiresApproval ?? false,
    })
  }

  const saveAdd = async (data: EventForm) => {
    try {
      const ev = await createEvent({
        title: data.title,
        date: data.date,
        time: data.time || undefined,
        location: data.location || undefined,
        type: data.type,
        maxAttendees: limitOf(data.maxAttendees),
        requiresApproval: data.requiresApproval,
      })
      eventCache.append(ev)
      setAddOpen(false)
      notify(
        'success',
        t('events.event.saved'),
        t('events.event.createdMsg', { title: data.title }),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekannter Fehler'),
      )
    }
  }
  const [submitAdd, adding] = useSubmitOnce(saveAdd)

  const saveEdit = async (data: EventForm) => {
    if (!editTarget) return
    try {
      const ev = await updateEvent(editTarget.id, {
        title: data.title,
        date: data.date,
        time: data.time || undefined,
        location: data.location || undefined,
        type: data.type,
        maxAttendees: limitOf(data.maxAttendees),
        requiresApproval: data.requiresApproval,
      })
      eventCache.replace(ev)
      setEditTarget(null)
      notify(
        'success',
        t('events.event.saved'),
        t('events.event.updatedMsg', { title: data.title }),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekannter Fehler'),
      )
    }
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    try {
      await deleteEvent(deleteTarget.id)
      eventCache.remove(deleteTarget.id)
      notify(
        'info',
        t('events.event.deleted'),
        t('events.event.deletedMsg', { title: deleteTarget.title }),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekannter Fehler'),
      )
    }
  }

  const eventForm = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Field label={t('events.event.title', 'Titel')}>
        <TextInput
          {...form.getInputProps('title')}
          placeholder={t(
            'events.event.titlePlaceholder',
            'z. B. Einführung Holzwerkstatt',
          )}
        />
      </Field>
      <div
        className="grid-2"
        style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}
      >
        <Field label={t('common.date', 'Datum')}>
          <TextInput type="date" {...form.getInputProps('date')} />
        </Field>
        <Field label={t('events.time', 'Zeit') + ' (optional)'}>
          <TextInput
            {...form.getInputProps('time')}
            placeholder="14:00–18:00"
          />
        </Field>
      </div>
      <Field label={t('events.location', 'Ort') + ' (optional)'}>
        <TextInput
          {...form.getInputProps('location')}
          placeholder={t('events.locationPlaceholder', 'z. B. Holzwerkstatt')}
        />
      </Field>
      <Field label={t('common.type', 'Typ')}>
        <Select
          data={EVENT_TYPES.map((tp) => ({
            value: tp,
            label: eventTypeLabel(tp),
          }))}
          {...form.getInputProps('type')}
        />
      </Field>
      <Field label={t('events.maxAttendees', 'Plätze') + ' (optional)'}>
        <TextInput
          inputMode="numeric"
          {...form.getInputProps('maxAttendees')}
          placeholder={t('events.maxAttendeesPlaceholder', 'Leer: ohne Begrenzung')}
        />
      </Field>
      <Checkbox
        label={t(
          'events.requiresApproval',
          'Anmeldungen bestätigen (Organisatoren entscheiden über jede Anmeldung)',
        )}
        {...form.getInputProps('requiresApproval', { type: 'checkbox' })}
      />
    </div>
  )

  return (
    <div>
      <Group justify="flex-end" mb={16} gap="xs" className="page-actions">
        <CalendarSubscribeButton />
        {canCreate && (
          <Button variant="filled" onClick={openAdd}>
            <IconPlus size={16} />
            {t('events.addEvent')}
          </Button>
        )}
      </Group>
      <DataTable
        breakpoint="wide"
        columns={[
          {
            key: 'date',
            header: t('common.date', 'Datum'),
            width: 64,
            render: (ev) => {
              const d = new Date(ev.date)
              return (
                <div
                  style={{
                    textAlign: 'center',
                    minWidth: 48,
                    background: 'var(--hb-surface-2)',
                    borderRadius: 10,
                    padding: '8px 0',
                  }}
                >
                  <div
                    className="num"
                    style={{
                      fontSize: 'var(--mantine-font-size-xl)',
                      fontWeight: 700,
                      color: 'var(--hb-text)',
                      lineHeight: 1,
                    }}
                  >
                    {d.getDate()}
                  </div>
                  <div
                    style={{
                      fontSize: 'var(--mantine-font-size-xs)',
                      fontWeight: 600,
                      color: 'var(--hb-text-3)',
                      letterSpacing: '0.08em',
                    }}
                  >
                    {d
                      .toLocaleString(i18n.language, { month: 'short' })
                      .toUpperCase()}
                  </div>
                </div>
              )
            },
          },
          {
            key: 'title',
            header: t('events.event.title', 'Titel'),
            render: (ev) => (
              <span
                style={{
                  fontSize: 'var(--mantine-font-size-sm)',
                  fontWeight: 600,
                  color: 'var(--hb-text)',
                }}
              >
                {ev.title}
              </span>
            ),
          },
          {
            key: 'timeLocation',
            header: t('events.time', 'Zeit'),
            render: (ev) => (
              <span
                style={{
                  fontSize: 'var(--mantine-font-size-sm)',
                  color: 'var(--hb-text-2)',
                }}
              >
                {ev.time && <>{ev.time} · </>}
                {ev.location || t('events.noLocation', 'Kein Ort')}
              </span>
            ),
          },
          {
            key: 'attendees',
            header: t('events.attendees', 'Teilnehmende'),
            width: 130,
            render: (ev) => (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                }}
              >
                <IconUserCheck size={13} style={{ color: 'var(--hb-text-2)' }} />
                <span
                  className="num"
                  style={{
                    fontSize: 'var(--mantine-font-size-xs)',
                    color: 'var(--hb-text-2)',
                  }}
                >
                  {ev.placesTaken ?? ev.attendees.length}
                  {ev.maxAttendees ? ` / ${ev.maxAttendees}` : ''}
                </span>
                {canApprove && (ev.pendingCount ?? 0) > 0 && (
                  <Badge
                    variant="light"
                    color="orange"
                    style={{ cursor: 'pointer' }}
                    onClick={() => setPendingFor(ev)}
                  >
                    {t('events.pendingCount', '{{count}} offen', {
                      count: ev.pendingCount,
                    })}
                  </Badge>
                )}
              </div>
            ),
          },
          {
            key: 'type',
            header: t('common.type', 'Typ'),
            width: 120,
            render: (ev) => (
              <Badge
                variant="light"
                style={{
                  borderColor: EVENT_TYPE_COLORS[ev.type] + '66',
                  color: EVENT_TYPE_COLORS[ev.type],
                  background: EVENT_TYPE_COLORS[ev.type] + '1a',
                }}
              >
                {eventTypeLabel(ev.type)}
              </Badge>
            ),
          },
          {
            key: 'actions',
            header: '',
            width: 200,
            render: (ev) => {
              const joined = hasOpenSignUp(ev, myJoinedEvents.has(ev.id))
              return (
                <div
                  style={{
                    display: 'flex',
                    gap: 4,
                    alignItems: 'center',
                  }}
                >
                  <Button
                    size="sm"
                    variant={joined ? 'default' : 'filled'}
                    disabled={joinEventMutation.isPending}
                    onClick={() =>
                      joinEventMutation.mutate({
                        eventId: ev.id,
                        eventTitle: ev.title,
                        memberId: currentUser?.id ?? '',
                      })
                    }
                  >
                    {joined ? (
                      <>
                        <Leave size={16} />
                        {ev.myStatus === 'pending'
                          ? t('events.withdrawRequest', 'Anfrage zurückziehen')
                          : ev.myStatus === 'waitlisted'
                            ? t('events.leaveWaitlist', 'Warteliste verlassen')
                            : t('events.leave', 'Abmelden')}
                      </>
                    ) : (
                      <>
                        <IconLogin size={16} />
                        {t('events.join', 'Teilnehmen')}
                      </>
                    )}
                  </Button>
                  <ActionButtons
                    onEdit={canUpdate ? () => openEdit(ev) : undefined}
                    onDelete={canDelete ? () => setDeleteTarget(ev) : undefined}
                  />
                </div>
              )
            },
          },
        ]}
        data={pg.paged}
        emptyMessage={t('events.noEvents', 'Keine Anlässe gefunden.')}
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder={t('events.search', 'Suchen …')}
        filters={types.map((typeItem) => ({
          label: typeItem === 'All' ? t('common.all', 'Alle') : eventTypeLabel(typeItem),
          value: typeItem.toLowerCase(),
          active: typeFilter === typeItem,
          onClick: () => setTypeFilter(typeItem),
        }))}
        page={pg.page}
        perPage={pg.perPage}
        total={pg.total}
        totalPages={pg.totalPages}
        onPageChange={pg.goPage}
        onPerPageChange={pg.setPerPage}
        getRowKey={(ev) => ev.id}
      />
      <Modal
        onSubmit={form.onSubmit(submitAdd)}
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title={t('events.addEvent')}
        footer={
          <>
            <Button variant="default" onClick={() => setAddOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button variant="filled" type="submit" loading={adding}>
              {t('events.createEvent', 'Anlass erstellen')}
            </Button>
          </>
        }
      >
        {eventForm}
      </Modal>
      <Modal
        onSubmit={form.onSubmit(saveEdit)}
        open={!!editTarget}
        onClose={() => setEditTarget(null)}
        title={t('events.editEvent')}
        subtitle={editTarget?.title}
        footer={
          <>
            <Button variant="default" onClick={() => setEditTarget(null)}>
              {t('common.cancel')}
            </Button>
            <Button variant="filled" type="submit">
              {t('common.save')}
            </Button>
          </>
        }
      >
        {eventForm}
      </Modal>
      <PendingSignUpsModal
        event={pendingFor}
        onClose={() => setPendingFor(null)}
        onDecided={(ev) =>
          eventCache.patch(ev.id, () => ev)
        }
      />
      <ConfirmModal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title={t('events.deleteEventTitle', '{{title}} löschen?', {
          title: deleteTarget?.title ?? '',
        })}
        body={t(
          'events.deleteEventBody',
          'Der Anlass und seine Teilnehmerliste werden endgültig gelöscht.',
        )}
        onConfirm={confirmDelete}
      />
    </div>
  )
}
