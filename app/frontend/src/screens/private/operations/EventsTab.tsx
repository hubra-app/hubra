import { Fragment, useState } from 'react'
import { DateField, DateTimeField, FilterBar, TimeField } from '@hubra/ui'
import { useSearchParams } from 'react-router-dom'
import {
  Button,
  Group,
  NumberInput,
  TextInput,
  Textarea,
  Select,
  Checkbox,
  SimpleGrid,
  SegmentedControl,
  Paper,
  Divider,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { zod4Resolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { useT, zmsg } from '@/locales/i18n'
import { isPastEvent, monthKey } from './eventDates'
import { AssociationEventsCard } from './AssociationEventsCard'
import i18n from 'i18next'
import {
  IconPlus,
  IconCalendarEvent,
  IconList,
  IconCalendarMonth,
} from '@tabler/icons-react'
import { useToast, useAuth, useData } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { useEvents, useListCache, useMyJoinedEvents } from '@/data/lists'
import {
  Modal,
  Field,
  usePagination,
  ConfirmModal,
  EmptyState,
  Pagination,
  useSubmitOnce,
  useLinkedId,
  LinkedEntryBar,
} from '@/components/ui'
import type { ClubEvent } from '@/types'
import {
  createEvent,
  updateEvent,
  deleteEvent,
  reinstateEvent,
  type EventUpdate,
  type SeriesScope,
} from '@/api/events'
import {
  hasOpenSignUp,
  useToggleJoinEvent,
  useMaybeEvent,
} from '@/screens/private/operations/useEventActions'
import { CalendarSubscribeButton } from './CalendarSubscribeButton'
import { EventCard, MonthHeading } from './EventCard'
import { EventsMonth } from './EventsMonth'
import { fromLocalInput, toLocalInput } from './localInput'
import { filterLabels } from '@/components/filterLabels'
import { PendingSignUpsModal } from './PendingSignUpsModal'
import { AttendanceModal } from './AttendanceModal'
import { CancelEventModal } from './CancelEventModal'
import { SaveTemplateModal, TemplateMenu } from './EventTemplates'
import { templateExtras } from './templateExtras'
import { joinTime, splitTime } from './eventTime'
import type { EventTemplate, EventTemplateData } from '@/api/events'
import { RecurrenceFields } from './RecurrenceFields'
import { GroupField } from './ContentGroupFields'
import { useContentGroups } from './contentGroups'
import { defaultRepeat, type RepeatState } from './recurrence'

/* ── Events ─────────────────────────────────── */
const eventSchema = z.object({
  title: z.string().min(1, zmsg('validation.titleRequired', 'Titel ist erforderlich')),
  date: z.string().min(1, zmsg('validation.dateRequired', 'Datum ist erforderlich')),
  // Von/bis compose the event's time text ("14:00–18:00"); an old free
  // text that isn't a time stays as it is until a time is picked.
  timeFrom: z.string(),
  timeTo: z.string(),
  timeText: z.string(),
  // Multi-day events; empty: one day.
  endDate: z.string(),
  // datetime-local values (local time); empty: no deadline.
  registrationDeadline: z.string(),
  cancellationDeadline: z.string(),
  location: z.string(),
  type: z.string(),
  // Empty: no limit.
  maxAttendees: z
    .string()
    .regex(/^\d*$/, zmsg('validation.wholeNumber', 'Bitte eine ganze Zahl eingeben')),
  requiresApproval: z.boolean(),
  // Empty: for everyone.
  groupId: z.string(),
  description: z.string(),
  // Public: may be shown outside the club (a Discord server that is not
  // members-only, the club's public pages).
  isPublic: z.boolean(),
  // An association's event shown to its member clubs (federation module).
  federationShared: z.boolean(),
  // Places for people who aren't members yet; empty: no trials.
  trialSpots: z
    .string()
    .regex(/^([1-9]\d?|100)?$/, zmsg('events.trialSpotsInvalid', 'Eine Zahl von 1 bis 100, oder leer')),
})
  .refine((v) => !v.endDate || v.endDate >= v.date, {
    path: ['endDate'],
    ...zmsg('events.endDateBeforeStart', 'Das Enddatum liegt vor dem Datum'),
  })
  .refine((v) => !v.timeTo || !!v.timeFrom, {
    path: ['timeTo'],
    ...zmsg('events.timeToWithoutFrom', 'Bitte auch den Beginn angeben'),
  })
  .refine((v) => !v.timeTo || !v.timeFrom || v.endDate > v.date || v.timeTo > v.timeFrom, {
    path: ['timeTo'],
    ...zmsg('events.timeToBeforeFrom', 'Das Ende liegt vor dem Beginn'),
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
  const maybeMutation = useMaybeEvent()
  // Club-wide, or through a role for one group (that group's events).
  const createScope = useContentGroups('events.events.create')
  const updateScope = useContentGroups('events.events.update')
  const canCreate = createScope.canAny
  // Templates are club-wide: saving and listing them takes the club-wide right.
  const canTemplates = hasPermission('events.events.create')
  const { moduleList, modules } = useData()
  const federationOn = Boolean(modules.federation)
  const eventTypes = clubEventTypes(
    moduleList.find((m) => m.code === 'events')?.config?.event_types,
  )
  // Whoever put an event up runs it (the API checks the same).
  const hosts = (ev: ClubEvent) =>
    currentUser != null && ev.createdById === Number(currentUser.id)
  const inScope = (key: string, ev: ClubEvent) => hasPermission(key, ev.groupId ?? undefined)
  const canUpdate = (ev: ClubEvent) => inScope('events.events.update', ev) || hosts(ev)
  const canDelete = (ev: ClubEvent) => inScope('events.events.delete', ev) || hosts(ev)
  const canApprove = (ev: ClubEvent) => inScope('events.events.add_attendee', ev) || hosts(ev)
  // Club-wide, or a trainer holding the right for one group.
  const canTakeRoll = (ev: ClubEvent) =>
    hasPermission('events.events.add_attendee', ev.groupId ?? undefined)
  const [rollFor, setRollFor] = useState<ClubEvent | null>(null)
  const [cancelFor, setCancelFor] = useState<ClubEvent | null>(null)
  const [templateFor, setTemplateFor] = useState<ClubEvent | null>(null)
  // The template a new event was started from (fields the form doesn't show).
  const [fromTemplate, setFromTemplate] = useState<EventTemplateData | null>(null)
  const reinstate = async (ev: ClubEvent) => {
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
  const [repeat, setRepeat] = useState<RepeatState>(() => defaultRepeat(''))
  const [ruleAtOpen, setRuleAtOpen] = useState<RepeatState | null>(null)
  const [editScope, setEditScope] = useState<SeriesScope>('this')
  const [pendingFor, setPendingFor] = useState<ClubEvent | null>(null)
  const [typeFilter, setTypeFilter] = useState('All')
  const [when, setWhen] = useState<'upcoming' | 'past' | 'all'>('upcoming')
  // List or month; remembered on this device.
  const [view, setViewState] = useState<'list' | 'month'>(() => {
    try {
      return localStorage.getItem('hubra.events.view') === 'month' ? 'month' : 'list'
    } catch {
      return 'list'
    }
  })
  const setView = (v: 'list' | 'month') => {
    setViewState(v)
    try {
      localStorage.setItem('hubra.events.view', v)
    } catch {
      // Private window: the choice lasts until the page is left.
    }
  }
  const [search, setSearch] = useState('')
  const [mineOnly, setMineOnly] = useState(false)
  const [addOpen, setAddOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<ClubEvent | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<ClubEvent | null>(null)
  const form = useForm<EventForm>({
    validate: zod4Resolver(eventSchema),
    initialValues: {
      title: '',
      date: new Date().toISOString().slice(0, 10),
      timeFrom: '',
      timeTo: '',
      timeText: '',
      endDate: '',
      registrationDeadline: '',
      cancellationDeadline: '',
      location: '',
      type: eventTypes[0],
      maxAttendees: '',
      requiresApproval: false,
      groupId: '',
      description: '',
      isPublic: false,
      federationShared: false,
      trialSpots: '',
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
    : events
        .filter((e) => {
          const matchType = typeFilter === 'All' || e.type === typeFilter
          const q = search.trim().toLowerCase()
          // A search looks through every date: whoever types a title wants
          // that event, whether it is coming up or over.
          const matchWhen =
            !!q || when === 'all' || (when === 'past' ? isPastEvent(e) : !isPastEvent(e))
          const matchSearch =
            !q ||
            e.title.toLowerCase().includes(q) ||
            (e.location || '').toLowerCase().includes(q)
          const matchMine = !mineOnly || hasOpenSignUp(e, myJoinedEvents.has(e.id))
          return matchType && matchWhen && matchSearch && matchMine
        })
        // Past events read newest first; what is coming reads soonest first.
        .sort((a, b) =>
          when === 'past' ? b.date.localeCompare(a.date) : a.date.localeCompare(b.date),
        )
  const pg = usePagination(filtered, 20)

  const openAdd = () => {
    form.setValues({
      title: '',
      date: new Date().toISOString().slice(0, 10),
      timeFrom: '',
      timeTo: '',
      timeText: '',
      endDate: '',
      registrationDeadline: '',
      cancellationDeadline: '',
      location: '',
      type: eventTypes[0],
      maxAttendees: '',
      requiresApproval: false,
      groupId: createScope.defaultGroup,
      description: '',
      isPublic: false,
      federationShared: false,
      trialSpots: '',
    })
    setRepeat(defaultRepeat(new Date().toISOString().slice(0, 10)))
    setFromTemplate(null)
    setAddOpen(true)
  }
  const openFromTemplate = (tpl: EventTemplate) => {
    openAdd()
    const d = tpl.data
    form.setValues({
      title: d.title ?? '',
      ...splitTime(d.time),
      location: d.location ?? '',
      type: d.type && eventTypes.includes(d.type) ? d.type : eventTypes[0],
      maxAttendees: d.max_attendees ? String(d.max_attendees) : '',
      requiresApproval: d.requires_approval ?? false,
      groupId: d.group_id != null ? String(d.group_id) : createScope.defaultGroup,
      description: d.description ?? '',
      isPublic: d.is_public ?? false,
      federationShared: d.federation_shared ?? false,
      trialSpots: d.trial_spots ? String(d.trial_spots) : '',
    })
    setFromTemplate(d)
  }
  // ?new=1 (the dashboard's "Neuer Anlass") opens the form right away.
  const [params, setParams] = useSearchParams()
  const newLink = params.get('new') === '1'
  const [handledNew, setHandledNew] = useState(false)
  if (newLink && canCreate && !handledNew) {
    setHandledNew(true)
    // The form still holds its fresh initial values; a group lead starts in
    // their group.
    if (createScope.defaultGroup) form.setFieldValue('groupId', createScope.defaultGroup)
    setAddOpen(true)
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
      ...splitTime(ev.time),
      endDate: ev.endDate ?? '',
      registrationDeadline: toLocalInput(ev.registrationDeadline),
      cancellationDeadline: toLocalInput(ev.cancellationDeadline),
      location: ev.location ?? '',
      type: ev.type,
      maxAttendees: ev.maxAttendees ? String(ev.maxAttendees) : '',
      requiresApproval: ev.requiresApproval ?? false,
      groupId: ev.groupId ?? '',
      description: ev.description ?? '',
      isPublic: ev.isPublic ?? false,
      federationShared: ev.federationShared ?? false,
      trialSpots: ev.trialSpots ? String(ev.trialSpots) : '',
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
        time: joinTime(data) || undefined,
        location: data.location || undefined,
        type: data.type,
        maxAttendees: limitOf(data.maxAttendees),
        requiresApproval: data.requiresApproval,
        groupId: data.groupId || null,
        description: data.description,
        isPublic: data.isPublic,
        federationShared: data.federationShared,
        trialSpots: limitOf(data.trialSpots),
        registrationDeadline: fromLocalInput(data.registrationDeadline),
        cancellationDeadline: fromLocalInput(data.cancellationDeadline),
        ...templateExtras(fromTemplate, data.date),
        // A chosen end date wins over the template's length.
        ...(data.endDate ? { endDate: data.endDate } : {}),
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
      time: joinTime(data),
      location: data.location || undefined,
      type: data.type,
      maxAttendees: limitOf(data.maxAttendees),
      requiresApproval: data.requiresApproval,
      groupId: data.groupId || null,
      description: data.description,
      isPublic: data.isPublic,
      federationShared: data.federationShared,
      trialSpots: limitOf(data.trialSpots),
      // End date and deadlines belong to one date; a series moves them
      // along with its rule.
      ...(editScope === 'following' && editTarget.seriesId
        ? {}
        : {
            endDate: data.endDate || null,
            registrationDeadline: fromLocalInput(data.registrationDeadline),
            cancellationDeadline: fromLocalInput(data.cancellationDeadline),
          }),
    }
    const following = editScope === 'following' && !!editTarget.seriesId
    let input = all
    if (following) {
      // Only what was changed goes to the later dates, so one date's own
      // location or time stays; dates move with the rule.
      const was: EventUpdate = {
        title: editTarget.title,
        time: editTarget.time ?? '',
        location: editTarget.location || undefined,
        type: editTarget.type,
        maxAttendees: editTarget.maxAttendees ?? null,
        requiresApproval: editTarget.requiresApproval ?? false,
        groupId: editTarget.groupId ?? null,
        description: editTarget.description ?? '',
        isPublic: editTarget.isPublic ?? false,
        federationShared: editTarget.federationShared ?? false,
        trialSpots: editTarget.trialSpots ?? null,
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
      <Field label={t('events.description', 'Beschreibung') + ' (optional)'}>
        <Textarea
          autosize
          minRows={2}
          maxRows={8}
          {...form.getInputProps('description')}
          placeholder={t(
            'events.descriptionPlaceholder',
            'Was erwartet die Teilnehmenden? Was mitbringen?',
          )}
        />
      </Field>
      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing={12}>
        <Field label={t('common.date', 'Datum')}>
          <DateField
            {...form.getInputProps('date')}
            disabled={followingScope}
          />
        </Field>
        <Field
          label={t('events.endDate', 'Enddatum') + ' (optional)'}
          hint={followingScope ? t('events.perDateHint', 'Gilt nur für diesen Termin.') : undefined}
        >
          <DateField
            min={form.values.date || undefined}
            {...form.getInputProps('endDate')}
            disabled={followingScope}
          />
        </Field>
        <Field
          label={t('events.timeFrom', 'Beginn') + ' (optional)'}
          // An old free-text time stays until a time is picked.
          hint={
            !form.values.timeFrom && form.values.timeText
              ? t('events.timeTextHint', 'Bisher: {{text}}', { text: form.values.timeText })
              : undefined
          }
        >
          <TimeField
            {...form.getInputProps('timeFrom')}
            onChange={(v) => {
              form.setFieldValue('timeFrom', v)
              // A picked time replaces the old text for good.
              form.setFieldValue('timeText', '')
            }}
          />
        </Field>
        <Field label={t('events.timeTo', 'Ende') + ' (optional)'}>
          <TimeField
            {...form.getInputProps('timeTo')}
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
      </SimpleGrid>
      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing={12}>
        <Field label={t('events.maxAttendees', 'Plätze') + ' (optional)'}>
          <NumberInput
            allowDecimal={false}
            allowNegative={false}
            hideControls
            {...form.getInputProps('maxAttendees')}
            // The form keeps the number as text (empty = no limit).
            onChange={(v) => form.setFieldValue('maxAttendees', v === '' ? '' : String(v))}
            placeholder={t('events.maxAttendeesPlaceholder', 'Leer: ohne Begrenzung')}
          />
        </Field>
        <Field
          label={t('events.trialSpots', 'Plätze für Schnuppertraining') + ' (optional)'}
          hint={t(
            'events.trialSpotsHint',
            'Wer noch nicht Mitglied ist, kann dieses Training auf der Schnupperseite des Vereins buchen. Leer: keine Schnupperplätze.',
          )}
        >
          <NumberInput
            allowDecimal={false}
            allowNegative={false}
            hideControls
            {...form.getInputProps('trialSpots')}
            // The form keeps the number as text (empty = no limit).
            onChange={(v) => form.setFieldValue('trialSpots', v === '' ? '' : String(v))}
            placeholder={t('events.trialSpotsPlaceholder', 'z. B. 2')}
          />
        </Field>
        <Field
          label={t('events.registrationDeadline', 'Anmeldeschluss') + ' (optional)'}
          hint={followingScope ? t('events.perDateHint', 'Gilt nur für diesen Termin.') : undefined}
        >
          <DateTimeField
            {...form.getInputProps('registrationDeadline')}
            disabled={followingScope}
          />
        </Field>
        <Field
          label={t('events.cancellationDeadline', 'Abmeldeschluss') + ' (optional)'}
          hint={
            followingScope
              ? t('events.perDateHint', 'Gilt nur für diesen Termin.')
              : t('events.cancellationDeadlineHint', 'Danach kann man sich nicht mehr selbst abmelden.')
          }
        >
          <DateTimeField
            {...form.getInputProps('cancellationDeadline')}
            disabled={followingScope}
          />
        </Field>
      </SimpleGrid>
      <GroupField
        scope={editTarget ? updateScope : createScope}
        value={form.values.groupId}
        onChange={(v) => form.setFieldValue('groupId', v)}
        error={form.errors.groupId}
        hint={t(
          'events.groupHint',
          'Ihre Mitglieder werden bei der Anwesenheit erwartet (z. B. das Team eines Trainings).',
        )}
      />
      <Checkbox
        label={t(
          'events.requiresApproval',
          'Anmeldungen bestätigen (Organisatoren entscheiden über jede Anmeldung)',
        )}
        {...form.getInputProps('requiresApproval', { type: 'checkbox' })}
      />
      <Checkbox
        label={t('events.isPublic', 'Öffentlicher Anlass')}
        description={t(
          'events.isPublicHint',
          'Darf auch ausserhalb des Vereins erscheinen, z. B. auf einem offenen Discord-Server. Sonst sehen ihn nur Mitglieder.',
        )}
        {...form.getInputProps('isPublic', { type: 'checkbox' })}
      />
      {federationOn && (
        <Checkbox
          label={t('events.federationShared', 'Mit Mitgliedvereinen teilen')}
          description={t(
            'events.federationSharedHint',
            'Eure Mitgliedvereine sehen den Anlass unter Anlässe › Vom Verband.',
          )}
          {...form.getInputProps('federationShared', { type: 'checkbox' })}
        />
      )}
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
      <Group justify="space-between" mb={16} gap="xs" className="page-actions">
        <SegmentedControl
          value={view}
          onChange={(v) => setView(v as 'list' | 'month')}
          data-testid="events-view"
          data={[
            {
              value: 'list',
              label: (
                <Group gap={6} wrap="nowrap">
                  <IconList size={16} />
                  {t('events.view.list', 'Liste')}
                </Group>
              ),
            },
            {
              value: 'month',
              label: (
                <Group gap={6} wrap="nowrap">
                  <IconCalendarMonth size={16} />
                  {t('events.view.month', 'Monat')}
                </Group>
              ),
            },
          ]}
        />
        <Group gap="xs" wrap="wrap">
          <CalendarSubscribeButton />
          {canTemplates && <TemplateMenu onPick={openFromTemplate} />}
          {canCreate && (
            <Button variant="filled" onClick={openAdd}>
              <IconPlus size={16} />
              {t('events.addEvent')}
            </Button>
          )}
        </Group>
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
      {!linked.id && <AssociationEventsCard />}
      {view === 'month' && !linked.id ? (
        // The month shows every date, so only the type and "mine" filters apply.
        <EventsMonth
          events={events.filter(
            (e) =>
              (typeFilter === 'All' || e.type === typeFilter) &&
              (!mineOnly || hasOpenSignUp(e, myJoinedEvents.has(e.id))),
          )}
        />
      ) : (
      <Paper withBorder>
        <FilterBar
          padded
          search={search}
          onSearchChange={setSearch}
          searchPlaceholder={t('events.search', 'Suchen …')}
          labels={filterLabels()}
          groups={[
            {
              key: 'when',
              label: t('events.filter.when', 'Zeitraum'),
              value: when,
              defaultValue: 'upcoming',
              options: [
                { value: 'upcoming', label: t('events.filter.upcoming', 'Kommende') },
                { value: 'past', label: t('events.filter.past', 'Vergangene') },
                { value: 'all', label: t('common.all', 'Alle') },
              ],
              onChange: (v) => setWhen(v as 'upcoming' | 'past' | 'all'),
            },
            {
              key: 'mine',
              label: t('events.filter.mine', 'Anmeldung'),
              value: mineOnly ? 'mine' : 'all',
              defaultValue: 'all',
              options: [
                { value: 'all', label: t('common.all', 'Alle') },
                { value: 'mine', label: t('events.filter.mineOnly', 'Nur meine') },
              ],
              onChange: (v) => setMineOnly(v === 'mine'),
            },
            {
              key: 'type',
              label: t('events.filter.type', 'Typ'),
              value: typeFilter,
              defaultValue: 'All',
              hidden: eventTypes.length === 0,
              options: types.map((typeItem) => ({
                value: typeItem,
                label: typeItem === 'All' ? t('common.all', 'Alle') : eventTypeLabel(typeItem),
              })),
              onChange: setTypeFilter,
            },
          ]}
        />
        {pg.total > pg.perPage && <Pagination {...pg} top />}
        {pg.paged.length === 0 ? (
          <EmptyState
            icon={<IconCalendarEvent size={36} />}
            title={
              mineOnly
                ? t('events.noMine', 'Du bist für keinen Anlass angemeldet.')
                : t('events.noEvents', 'Keine Anlässe gefunden.')
            }
            description={
              when === 'upcoming' && !search && !mineOnly
                ? canCreate
                  ? t('events.emptyHint', 'Plane den nächsten Anlass, die Mitglieder können sich hier gleich anmelden.')
                  : t('events.emptyMember', 'Sobald ein Anlass geplant ist, kannst du dich hier anmelden.')
                : undefined
            }
            action={
              canCreate && when === 'upcoming' && !search && !mineOnly
                ? { label: t('events.addEvent'), onClick: openAdd }
                : undefined
            }
          />
        ) : (
          <div className="hb-event-list">
            {pg.paged.map((ev, i) => {
              const joined = hasOpenSignUp(ev, myJoinedEvents.has(ev.id))
              const over = isPastEvent(ev)
              const newMonth = i === 0 || monthKey(pg.paged[i - 1].date) !== monthKey(ev.date)
              return (
                <Fragment key={ev.id}>
                  {newMonth && <MonthHeading month={monthKey(ev.date)} locale={i18n.language} />}
                  <EventCard
                    ev={ev}
                    joined={joined}
                    over={over}
                    groupName={createScope.groupName(ev.groupId)}
                    typeLabel={eventTypeLabel(ev.type)}
                    actions={{
                      busy: joinEventMutation.isPending || maybeMutation.isPending,
                      onJoin: () =>
                        joinEventMutation.mutate({
                          eventId: ev.id,
                          eventTitle: ev.title,
                          memberId: currentUser?.id ?? '',
                        }),
                      onMaybe: () => maybeMutation.mutate({ eventId: ev.id, eventTitle: ev.title }),
                      onRoll: canTakeRoll(ev) ? () => setRollFor(ev) : undefined,
                      onPending:
                        canApprove(ev) && (ev.pendingCount ?? 0) > 0 ? () => setPendingFor(ev) : undefined,
                      onEdit: canUpdate(ev) ? () => openEdit(ev) : undefined,
                      onTemplate: canTemplates ? () => setTemplateFor(ev) : undefined,
                      onCancel: canUpdate(ev) && !over && !ev.cancelledAt ? () => setCancelFor(ev) : undefined,
                      onReinstate: canUpdate(ev) && !over && ev.cancelledAt ? () => void reinstate(ev) : undefined,
                      onDelete: canDelete(ev) ? () => setDeleteTarget(ev) : undefined,
                    }}
                  />
                </Fragment>
              )
            })}
          </div>
        )}
        <Pagination {...pg} />
      </Paper>
      )}
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
      <CancelEventModal event={cancelFor} onClose={() => setCancelFor(null)} />
      <SaveTemplateModal event={templateFor} onClose={() => setTemplateFor(null)} />
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
