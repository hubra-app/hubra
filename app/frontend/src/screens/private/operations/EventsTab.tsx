import { EVENT_TYPE_COLORS } from '@/constants'
import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Button,
  Group,
  TextInput,
  Select,
  Badge,
  Checkbox,
  SimpleGrid,
  SegmentedControl,
  Divider,
  ActionIcon,
  Tooltip,
} from '@mantine/core'
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
  IconRepeat,
  IconClipboardCheck,
  IconChartBar,
} from '@tabler/icons-react'
import { useToast, useAuth, useData } from '@/context/AppContext'
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
  useLinkedId,
  LinkedEntryBar,
} from '@/components/ui'
import type { ClubEvent } from '@/types'
import {
  createEvent,
  updateEvent,
  deleteEvent,
  type EventUpdate,
  type SeriesScope,
} from '@/api/events'
import { listGroups } from '@/api/groups'
import {
  hasOpenSignUp,
  useToggleJoinEvent,
} from '@/screens/private/operations/useEventActions'
import { CalendarSubscribeButton } from './CalendarSubscribeButton'
import { PendingSignUpsModal } from './PendingSignUpsModal'
import { AttendanceModal } from './AttendanceModal'
import { RecurrenceFields } from './RecurrenceFields'
import { defaultRepeat, type RepeatState } from './recurrence'

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
  // Empty: for everyone.
  groupId: z.string(),
})
type EventForm = z.infer<typeof eventSchema>

const limitOf = (value: string) => (value.trim() ? Number(value) : null)

const sameRule = (a: RepeatState, b: RepeatState) =>
  a.until === b.until &&
  a.interval === b.interval &&
  a.weekdays.join() === b.weekdays.join() &&
  a.skipDates.join() === b.skipDates.join()


const EVENT_TYPES = ['Workshop', 'Social', 'Certification', 'Meeting']

/** The club's own types (Events module setting), or the built-in four. */
function clubEventTypes(raw: unknown): string[] {
  const own = String(raw ?? '')
    .split(',')
    .map((x) => x.trim())
    .filter(Boolean)
  return own.length ? own : EVENT_TYPES
}

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
  const { moduleList } = useData()
  const eventTypes = clubEventTypes(
    moduleList.find((m) => m.code === 'events')?.config?.event_types,
  )
  // Whoever put an event up runs it (the API checks the same).
  const hosts = (ev: ClubEvent) =>
    currentUser != null && ev.createdById === Number(currentUser.id)
  const canUpdate = (ev: ClubEvent) => hasPermission('events.events.update') || hosts(ev)
  const canDelete = (ev: ClubEvent) => hasPermission('events.events.delete') || hosts(ev)
  const canApprove = (ev: ClubEvent) =>
    hasPermission('events.events.add_attendee') || hosts(ev)
  const navigate = useNavigate()
  const mayGroups = moduleList.some((m) => m.code === 'groups')
  const { data: groups = [] } = useQuery({
    queryKey: qk.groups.all,
    queryFn: listGroups,
    enabled: mayGroups,
  })
  // Club-wide, or a trainer holding the right for one group.
  const canTakeRoll = (ev: ClubEvent) =>
    hasPermission('events.events.add_attendee', ev.groupId ?? undefined)
  const seesAttendance =
    hasPermission('events.events.add_attendee') || groups.some((g) => hasPermission('events.events.add_attendee', g.id))
  const [rollFor, setRollFor] = useState<ClubEvent | null>(null)
  const [repeat, setRepeat] = useState<RepeatState>(() => defaultRepeat(''))
  const [ruleAtOpen, setRuleAtOpen] = useState<RepeatState | null>(null)
  const [editScope, setEditScope] = useState<SeriesScope>('this')
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
      type: eventTypes[0],
      maxAttendees: '',
      requiresApproval: false,
      groupId: '',
    },
  })

  const types = ['All', ...eventTypes]
  // ?event=<id> (from a notification) shows just that event; &pending=1
  // opens its sign-ups waiting for approval.
  const linked = useLinkedId('event', ['pending'])
  const [handledPending, setHandledPending] = useState<string | null>(null)
  if (linked.id && linked.params.get('pending') === '1' && handledPending !== linked.id) {
    const ev = events.find((e) => e.id === linked.id)
    if (ev) {
      setHandledPending(linked.id)
      if (canApprove(ev)) setPendingFor(ev)
    }
  }
  const filtered = linked.id
    ? events.filter((e) => e.id === linked.id)
    : events.filter((e) => {
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
      type: eventTypes[0],
      maxAttendees: '',
      requiresApproval: false,
      groupId: '',
    })
    setRepeat(defaultRepeat(new Date().toISOString().slice(0, 10)))
    setAddOpen(true)
  }
  // ?new=1 (the dashboard's "Neuer Anlass") opens the form right away.
  const [params, setParams] = useSearchParams()
  const newLink = params.get('new') === '1'
  const [handledNew, setHandledNew] = useState(false)
  if (newLink && canCreate && !handledNew) {
    setHandledNew(true)
    setAddOpen(true) // the form still holds its fresh initial values
  }
  // Reset only once the URL has dropped ?new=1 (see MembersTab).
  if (!newLink && handledNew) setHandledNew(false)
  const closeAdd = () => {
    setAddOpen(false)
    if (newLink) {
      setParams(
        (p) => {
          p.delete('new')
          return p
        },
        { replace: true },
      )
    }
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
      groupId: ev.groupId ?? '',
    })
    setEditScope('this')
    // The rule as it stands from this date on.
    const rule = ev.recurrence
      ? defaultRepeat(ev.seriesDate ?? ev.date, {
          ...ev.recurrence,
          skipDates: ev.recurrence.skipDates.filter((d) => d >= (ev.seriesDate ?? ev.date)),
        })
      : null
    setRuleAtOpen(rule)
    if (rule) setRepeat(rule)
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
        groupId: data.groupId || null,
        recurrence: repeat.on
          ? {
              until: repeat.until,
              interval: repeat.interval,
              weekdays: repeat.weekdays,
              skipDates: repeat.skipDates,
            }
          : undefined,
      })
      if (repeat.on) {
        // The other dates of the series come with the list.
        await eventCache.invalidate()
      } else {
        eventCache.append(ev)
      }
      closeAdd()
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
    const all: EventUpdate = {
      title: data.title,
      date: data.date,
      time: data.time || undefined,
      location: data.location || undefined,
      type: data.type,
      maxAttendees: limitOf(data.maxAttendees),
      requiresApproval: data.requiresApproval,
      groupId: data.groupId || null,
    }
    const following = editScope === 'following' && !!editTarget.seriesId
    let input = all
    if (following) {
      // Only what was changed goes to the later dates, so one date's own
      // location or time stays; dates move with the rule.
      const was: EventUpdate = {
        title: editTarget.title,
        time: editTarget.time || undefined,
        location: editTarget.location || undefined,
        type: editTarget.type,
        maxAttendees: editTarget.maxAttendees ?? null,
        requiresApproval: editTarget.requiresApproval ?? false,
        groupId: editTarget.groupId ?? null,
      }
      input = Object.fromEntries(
        (Object.keys(was) as (keyof EventUpdate)[])
          .filter((k) => all[k] !== was[k])
          .map((k) => [k, all[k] ?? (k === 'time' || k === 'location' ? '' : all[k])]),
      ) as EventUpdate
      if (ruleAtOpen && !sameRule(repeat, ruleAtOpen)) {
        input.recurrence = {
          until: repeat.until,
          interval: repeat.interval,
          weekdays: repeat.weekdays,
          skipDates: repeat.skipDates,
        }
      }
    }
    try {
      const ev = await updateEvent(editTarget.id, input, following ? 'following' : 'this')
      if (following) {
        await eventCache.invalidate()
      } else {
        eventCache.replace(ev)
      }
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

  const confirmDelete = async (scope: SeriesScope = 'this') => {
    if (!deleteTarget) return
    try {
      await deleteEvent(deleteTarget.id, scope)
      if (scope === 'following') {
        await eventCache.invalidate()
      } else {
        eventCache.remove(deleteTarget.id)
      }
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

  const editingSeries = !!editTarget?.seriesId
  const followingScope = editingSeries && editScope === 'following'
  const eventForm = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {editingSeries && (
        <Field label={t('events.series.applyTo', 'Ändern für')}>
          <SegmentedControl
            fullWidth
            value={editScope}
            onChange={(v) => setEditScope(v as SeriesScope)}
            data={[
              { value: 'this', label: t('events.series.thisOne', 'Nur diesen Termin') },
              {
                value: 'following',
                label: t('events.series.following', 'Diesen und alle folgenden'),
              },
            ]}
          />
        </Field>
      )}
      <Field label={t('events.event.title', 'Titel')}>
        <TextInput
          {...form.getInputProps('title')}
          placeholder={t(
            'events.event.titlePlaceholder',
            'z. B. Einführung Holzwerkstatt',
          )}
        />
      </Field>
      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing={12}>
        <Field label={t('common.date', 'Datum')}>
          <TextInput
            type="date"
            {...form.getInputProps('date')}
            disabled={followingScope}
          />
        </Field>
        <Field label={t('events.time', 'Zeit') + ' (optional)'}>
          <TextInput
            {...form.getInputProps('time')}
            placeholder="14:00–18:00"
          />
        </Field>
        <Field label={t('events.location', 'Ort') + ' (optional)'}>
          <TextInput
            {...form.getInputProps('location')}
            placeholder={t('events.locationPlaceholder', 'z. B. Holzwerkstatt')}
          />
        </Field>
        <Field label={t('common.type', 'Typ')}>
          <Select
            // An event keeps a type the club no longer lists.
            data={[...new Set([...eventTypes, form.values.type])].map((tp) => ({
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
      </SimpleGrid>
      {mayGroups && (
        <Field
          label={t('events.group', 'Gruppe') + ' (optional)'}
          hint={t(
            'events.groupHint',
            'Ihre Mitglieder werden bei der Anwesenheit erwartet (z. B. das Team eines Trainings).',
          )}
        >
          <Select
            data={[
              { value: '', label: t('events.noGroup', 'Für alle') },
              ...groups.map((g) => ({ value: g.id, label: g.name })),
            ]}
            searchable
            allowDeselect={false}
            {...form.getInputProps('groupId')}
          />
        </Field>
      )}
      <Checkbox
        label={t(
          'events.requiresApproval',
          'Anmeldungen bestätigen (Organisatoren entscheiden über jede Anmeldung)',
        )}
        {...form.getInputProps('requiresApproval', { type: 'checkbox' })}
      />
      {(!editTarget || followingScope) && (
        <>
          <Divider />
          <RecurrenceFields
            start={editTarget ? (editTarget.seriesDate ?? editTarget.date) : form.values.date}
            value={repeat}
            onChange={setRepeat}
            toggle={!editTarget}
          />
        </>
      )}
    </div>
  )

  return (
    <div>
      <Group justify="flex-end" mb={16} gap="xs" className="page-actions">
        <CalendarSubscribeButton />
        {seesAttendance && (
          <Button variant="default" onClick={() => navigate('/app/operations/events/attendance')}>
            <IconChartBar size={16} />
            {t('events.attendance.overview', 'Anwesenheit')}
          </Button>
        )}
        {canCreate && (
          <Button variant="filled" onClick={openAdd}>
            <IconPlus size={16} />
            {t('events.addEvent')}
          </Button>
        )}
      </Group>
      {linked.id && (
        <LinkedEntryBar
          label={
            filtered.length
              ? t('events.linkedOne', 'Du siehst den Anlass aus deiner Benachrichtigung.')
              : t('events.linkedGone', 'Diesen Anlass gibt es nicht mehr.')
          }
          onShowAll={linked.clear}
        />
      )}
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
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                }}
              >
                {ev.title}
                {ev.seriesId && (
                  <Tooltip label={t('events.series.badge', 'Wiederkehrender Termin')}>
                    <IconRepeat
                      size={14}
                      aria-label={t('events.series.badge', 'Wiederkehrender Termin')}
                      style={{ color: 'var(--hb-text-3)' }}
                    />
                  </Tooltip>
                )}
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
                {canApprove(ev) && (ev.pendingCount ?? 0) > 0 && (
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
                  {canTakeRoll(ev) && (
                    <Tooltip label={t('events.attendance.take', 'Anwesenheit erfassen')}>
                      <ActionIcon
                        variant="subtle"
                        color="gray"
                        size="lg"
                        aria-label={t('events.attendance.take', 'Anwesenheit erfassen')}
                        onClick={() => setRollFor(ev)}
                      >
                        <IconClipboardCheck size={18} />
                      </ActionIcon>
                    </Tooltip>
                  )}
                  <ActionButtons
                    onEdit={canUpdate(ev) ? () => openEdit(ev) : undefined}
                    onDelete={canDelete(ev) ? () => setDeleteTarget(ev) : undefined}
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
        onClose={closeAdd}
        wide
        title={t('events.addEvent')}
        footer={
          <>
            <Button variant="default" onClick={closeAdd}>
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
        wide
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
      <AttendanceModal event={rollFor} onClose={() => setRollFor(null)} />
      <Modal
        open={!!deleteTarget?.seriesId}
        onClose={() => setDeleteTarget(null)}
        title={t('events.deleteEventTitle', '{{title}} löschen?', {
          title: deleteTarget?.title ?? '',
        })}
        subtitle={deleteTarget?.date}
        footer={
          <>
            <Button variant="default" onClick={() => setDeleteTarget(null)}>
              {t('common.cancel')}
            </Button>
            <Button
              variant="light"
              color="red"
              onClick={() => {
                void confirmDelete('this')
                setDeleteTarget(null)
              }}
            >
              {t('events.series.deleteThis', 'Nur diesen Termin')}
            </Button>
            <Button
              variant="filled"
              color="red"
              onClick={() => {
                void confirmDelete('following')
                setDeleteTarget(null)
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
        open={!!deleteTarget && !deleteTarget.seriesId}
        onClose={() => setDeleteTarget(null)}
        title={t('events.deleteEventTitle', '{{title}} löschen?', {
          title: deleteTarget?.title ?? '',
        })}
        body={t(
          'events.deleteEventBody',
          'Der Anlass und seine Teilnehmerliste werden endgültig gelöscht.',
        )}
        onConfirm={() => confirmDelete()}
      />
    </div>
  )
}
