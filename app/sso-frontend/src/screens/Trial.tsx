import { useEffect, useRef, useState } from 'react'
import {
  Alert,
  Button,
  Center,
  Checkbox,
  Group,
  Loader,
  Radio,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Textarea,
  Title,
} from '@mantine/core'
import { DateField } from '@hubra/ui'
import { useMutation, useQuery } from '@tanstack/react-query'
import { IconCalendarEvent, IconCheck, IconMailCheck } from '@tabler/icons-react'
import { useParams, useSearchParams } from 'react-router-dom'
import { AuthFrame } from '@/components/AuthFrame'
import { useLang } from '@/lang'
import {
  bookTrial,
  cancelTrial,
  confirmTrial,
  getTrialPage,
  type TrialBooking,
  type TrialEvent,
} from '@/api/trials'

function useWhen() {
  const { lang } = useLang()
  return (e: Pick<TrialEvent, 'date' | 'time'>) =>
    new Date(`${e.date}T00:00:00Z`).toLocaleDateString(lang === 'en' ? 'en-GB' : 'de-CH', {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      timeZone: 'UTC',
    }) + (e.time ? `, ${e.time}` : '')
}

/**
 * A club's trial page (/clubs/<slug>/trial): someone who isn't a member yet
 * books a trial training, no account needed. The mail we send holds the
 * link back here (?token=) that confirms the booking or cancels it.
 */
export function TrialScreen() {
  const { slug = '' } = useParams()
  const [params] = useSearchParams()
  const token = params.get('token')
  return (
    <AuthFrame wide>
      {token ? <TrialBookingView slug={slug} token={token} /> : <TrialForm slug={slug} />}
    </AuthFrame>
  )
}

function TrialForm({ slug }: { slug: string }) {
  const { tr, lang } = useLang()
  const when = useWhen()
  const page = useQuery({
    queryKey: ['trial-page', slug],
    queryFn: () => getTrialPage(slug),
    enabled: !!slug,
    retry: false,
  })
  const [eventId, setEventId] = useState<string | null>(null)
  const [form, setForm] = useState({
    firstName: '',
    lastName: '',
    email: '',
    phone: '',
    birthDate: '',
    message: '',
    website: '',
  })
  const [consent, setConsent] = useState(false)
  const set = (k: keyof typeof form) => (e: { currentTarget: { value: string } }) => {
    // Read it now: the event is gone by the time the state updates.
    const value = e.currentTarget.value
    setForm((f) => ({ ...f, [k]: value }))
  }

  const book = useMutation({
    mutationFn: () =>
      bookTrial(slug, {
        eventId: Number(eventId),
        firstName: form.firstName.trim(),
        lastName: form.lastName.trim(),
        email: form.email.trim(),
        phone: form.phone.trim() || undefined,
        birthDate: form.birthDate || undefined,
        message: form.message.trim() || undefined,
        consent,
        lang,
        website: form.website,
      }),
  })

  if (page.isLoading)
    return (
      <Center h={200}>
        <Loader />
      </Center>
    )
  if (page.isError || !page.data)
    return (
      <Alert color="red" title={tr('Verein nicht gefunden', 'Club not found')}>
        {tr(
          'Diesen Verein gibt es nicht oder er ist nicht aktiv.',
          "This club doesn't exist or isn't active.",
        )}
      </Alert>
    )

  const { club, events } = page.data
  const head = (
    <div>
      <Text size="sm" c="dimmed">
        {club.name}
      </Text>
      <Title order={2}>{tr('Schnuppertraining', 'Trial training')}</Title>
    </div>
  )

  if (book.isSuccess)
    return (
      <Stack gap="md">
        {head}
        <Alert color="green" icon={<IconMailCheck size={18} />} title={tr('Fast geschafft', 'Almost done')}>
          {tr(
            `Wir haben dir eine E-Mail an ${form.email.trim()} geschickt. Bestätige die Buchung mit dem Link darin, dann ist dein Platz reserviert.`,
            `We sent an email to ${form.email.trim()}. Confirm the booking with the link in it, and your place is reserved.`,
          )}
        </Alert>
      </Stack>
    )

  if (events.length === 0)
    return (
      <Stack gap="md">
        {head}
        <Alert color="gray" title={tr('Zurzeit keine Schnuppertrainings', 'No trial trainings right now')}>
          {tr(
            `${club.name} bietet gerade keine Trainings zum Schnuppern an. Schau später wieder vorbei.`,
            `${club.name} has no trainings open for a trial right now. Check back later.`,
          )}
        </Alert>
      </Stack>
    )

  const picked = events.find((e) => String(e.id) === eventId)
  const ready =
    !!picked &&
    picked.free > 0 &&
    !!form.firstName.trim() &&
    !!form.lastName.trim() &&
    /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email.trim()) &&
    consent

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        if (ready) book.mutate()
      }}
    >
      <Stack gap="md">
        {head}
        <Text size="sm">
          {tr(
            `Komm vorbei und probier es aus, bevor du Mitglied wirst. Wähle ein Training und sag uns, wer du bist.`,
            `Come along and try it before you join. Pick a training and tell us who you are.`,
          )}
        </Text>

        <Radio.Group
          value={eventId}
          onChange={setEventId}
          label={tr('Training', 'Training')}
          withAsterisk
        >
          <Stack gap={8} mt={6}>
            {events.map((e) => (
              <Radio.Card
                key={e.id}
                value={String(e.id)}
                disabled={e.free === 0}
                p="sm"
                radius="md"
                style={{ opacity: e.free === 0 ? 0.55 : 1 }}
              >
                <Group wrap="nowrap" align="flex-start" gap="sm">
                  <Radio.Indicator mt={2} />
                  <div style={{ minWidth: 0 }}>
                    <Text fw={600} size="sm">
                      {e.title}
                    </Text>
                    <Text size="sm">
                      <IconCalendarEvent size={14} style={{ verticalAlign: '-2px', marginRight: 4 }} />
                      {when(e)}
                    </Text>
                    {e.location && (
                      <Text size="xs" c="dimmed">
                        {e.location}
                      </Text>
                    )}
                    <Text size="xs" c={e.free === 0 ? 'red' : 'dimmed'}>
                      {e.free === 0
                        ? tr('Ausgebucht', 'Fully booked')
                        : e.free === 1
                          ? tr('Noch 1 Platz', '1 place left')
                          : tr(`Noch ${e.free} Plätze`, `${e.free} places left`)}
                    </Text>
                  </div>
                </Group>
              </Radio.Card>
            ))}
          </Stack>
        </Radio.Group>

        <SimpleGrid cols={{ base: 1, xs: 2 }} spacing="sm">
          <TextInput
            label={tr('Vorname', 'First name')}
            required
            value={form.firstName}
            onChange={set('firstName')}
            autoComplete="given-name"
          />
          <TextInput
            label={tr('Nachname', 'Last name')}
            required
            value={form.lastName}
            onChange={set('lastName')}
            autoComplete="family-name"
          />
        </SimpleGrid>
        <TextInput
          label={tr('E-Mail', 'Email')}
          type="email"
          required
          value={form.email}
          onChange={set('email')}
          autoComplete="email"
        />
        <SimpleGrid cols={{ base: 1, xs: 2 }} spacing="sm">
          <TextInput
            label={tr('Telefon (optional)', 'Phone (optional)')}
            type="tel"
            value={form.phone}
            onChange={set('phone')}
            autoComplete="tel"
          />
          <DateField
            label={tr('Geburtsdatum (optional)', 'Date of birth (optional)')}
            value={form.birthDate}
            onChange={(v) => set('birthDate')({ currentTarget: { value: v } })}
            autoComplete="bday"
          />
        </SimpleGrid>
        <Textarea
          label={tr('Nachricht (optional)', 'Message (optional)')}
          placeholder={tr(
            'z. B. Vorkenntnisse, Fragen, für wen du buchst',
            'e.g. experience, questions, who you book for',
          )}
          autosize
          minRows={2}
          maxLength={2000}
          value={form.message}
          onChange={set('message')}
        />
        {/* Not for people: bots fill it, and the booking is dropped. */}
        <input
          type="text"
          name="website"
          tabIndex={-1}
          autoComplete="off"
          aria-hidden="true"
          value={form.website}
          onChange={set('website')}
          style={{ position: 'absolute', left: '-10000px', width: 1, height: 1, opacity: 0 }}
        />
        <Checkbox
          checked={consent}
          onChange={(e) => setConsent(e.currentTarget.checked)}
          label={tr(
            `${club.name} darf meine Angaben für das Schnuppertraining speichern und mich dazu kontaktieren. Sie werden spätestens ein halbes Jahr danach gelöscht.`,
            `${club.name} may keep my details for the trial training and contact me about it. They are deleted half a year after it at the latest.`,
          )}
        />
        {book.isError && (
          <Alert color="red">
            {book.error instanceof Error ? book.error.message : tr('Buchung fehlgeschlagen', 'Booking failed')}
          </Alert>
        )}
        <Button type="submit" disabled={!ready} loading={book.isPending}>
          {tr('Schnuppertraining buchen', 'Book trial training')}
        </Button>
      </Stack>
    </form>
  )
}

function TrialBookingView({ slug, token }: { slug: string; token: string }) {
  const { tr } = useLang()
  const when = useWhen()
  const [booking, setBooking] = useState<TrialBooking | null>(null)
  const confirm = useMutation({
    mutationFn: () => confirmTrial(slug, token),
    onSuccess: setBooking,
  })
  const { mutate: confirmNow } = confirm
  const cancel = useMutation({
    mutationFn: () => cancelTrial(slug, token),
    onSuccess: setBooking,
  })
  // Opening the mail's link confirms the booking (once, also in StrictMode).
  const started = useRef(false)
  useEffect(() => {
    if (started.current) return
    started.current = true
    confirmNow()
  }, [confirmNow])

  if (confirm.isError && (confirm.error as { code?: string }).code === 'EVENT_FULL')
    return (
      <Alert color="orange" title={tr('Leider ausgebucht', 'Fully booked')}>
        {tr(
          'Du hast die Buchung nicht rechtzeitig bestätigt, und inzwischen sind alle Plätze vergeben. Wähle auf der Schnupperseite ein anderes Training.',
          "You didn't confirm the booking in time, and all places have been taken since. Pick another training on the trial page.",
        )}
      </Alert>
    )
  if (confirm.isError)
    return (
      <Alert color="red" title={tr('Link ungültig', 'Invalid link')}>
        {tr(
          'Diese Buchung gibt es nicht mehr. Buche das Training auf der Schnupperseite neu.',
          "This booking doesn't exist any more. Book the training again on the trial page.",
        )}
      </Alert>
    )
  if (!booking)
    return (
      <Center h={200}>
        <Loader />
      </Center>
    )

  const ev = booking.event
  const cancelled = booking.status === 'cancelled'
  return (
    <Stack gap="md">
      <Title order={2}>{tr('Schnuppertraining', 'Trial training')}</Title>
      {cancelled ? (
        <Alert color="gray" title={tr('Abgesagt', 'Cancelled')}>
          {tr(
            'Deine Buchung ist abgesagt, der Platz ist wieder frei.',
            'Your booking is cancelled, the place is free again.',
          )}
        </Alert>
      ) : (
        <Alert color="green" icon={<IconCheck size={18} />} title={tr('Du bist dabei', "You're in")}>
          {tr(
            `Hallo ${booking.firstName}, deine Buchung ist bestätigt. Wir freuen uns auf dich!`,
            `Hi ${booking.firstName}, your booking is confirmed. We look forward to seeing you!`,
          )}
        </Alert>
      )}
      <div>
        <Text fw={600}>{ev.title}</Text>
        <Text size="sm">{when(ev)}</Text>
        {ev.location && (
          <Text size="sm" c="dimmed">
            {ev.location}
          </Text>
        )}
        {ev.description && (
          <Text size="sm" mt={8} style={{ whiteSpace: 'pre-wrap' }}>
            {ev.description}
          </Text>
        )}
      </div>
      {!cancelled && ['pending', 'confirmed'].includes(booking.status) && (
        <Button variant="default" color="red" loading={cancel.isPending} onClick={() => cancel.mutate()}>
          {tr('Ich kann nicht kommen (absagen)', "I can't make it (cancel)")}
        </Button>
      )}
    </Stack>
  )
}
