import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Anchor, Button, Group, Paper, Stack, Text, TextInput, Textarea } from '@mantine/core'
import { IconNotes } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import { useT } from '@/locales/i18n'
import { useToast } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { formatDate } from '@/format'
import { getSessionNotes, saveSessionNotes, type SessionNote, type SessionNotes as Notes } from '@/api/events'

/**
 * On a date of a series, in the attendance dialog: what the last trainer
 * noted ("Letztes Mal") and this date's notes. The API also gives members
 * of the event what was trained and the guide link; the trainer note only
 * those who take attendance (hubra/api/events/session_notes.py).
 */
export function SessionNotes({ eventId }: { eventId: string }) {
  const { data } = useQuery({
    queryKey: qk.sessionNotes(eventId),
    queryFn: () => getSessionNotes(eventId),
  })
  if (!data) return null
  return <NotesForm key={data.note?.updated_at ?? 'new'} eventId={eventId} data={data} />
}

function GuideLink({ url }: { url: string }) {
  const { t } = useT()
  const navigate = useNavigate()
  const inApp = url.startsWith('/')
  return (
    <Anchor
      size="sm"
      href={inApp ? undefined : url}
      target={inApp ? undefined : '_blank'}
      rel={inApp ? undefined : 'noopener noreferrer'}
      onClick={inApp ? () => navigate(url) : undefined}
    >
      {t('events.notes.guide', 'Anleitung öffnen')}
    </Anchor>
  )
}

function Previous({ note }: { note: SessionNote }) {
  const { t } = useT()
  return (
    <Paper withBorder p="sm" bg="var(--hb-notice-bg)" data-testid="session-notes-previous">
      <Group gap={6} mb={4}>
        <IconNotes size={16} />
        <Text size="sm" fw={600}>
          {t('events.notes.previous', 'Letztes Mal ({{date}})', { date: note.date ? formatDate(note.date) : '' })}
        </Text>
        {note.updated_by_name && (
          <Text size="xs" c="dimmed">
            {note.updated_by_name}
          </Text>
        )}
      </Group>
      <Stack gap={4}>
        {note.trained && <Text size="sm">{note.trained}</Text>}
        {note.trainer_note && (
          <Text size="sm" c="dimmed">
            {t('events.notes.forTrainer', 'Für Trainer:')} {note.trainer_note}
          </Text>
        )}
        {note.guide_url && <GuideLink url={note.guide_url} />}
      </Stack>
    </Paper>
  )
}

function NotesForm({ eventId, data }: { eventId: string; data: Notes }) {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const [trained, setTrained] = useState(data.note?.trained ?? '')
  const [trainerNote, setTrainerNote] = useState(data.note?.trainer_note ?? '')
  const [guide, setGuide] = useState(data.note?.guide_url ?? '')
  const [saving, setSaving] = useState(false)
  const dirty =
    trained !== (data.note?.trained ?? '') ||
    trainerNote !== (data.note?.trainer_note ?? '') ||
    guide !== (data.note?.guide_url ?? '')

  const save = async () => {
    setSaving(true)
    try {
      const saved = await saveSessionNotes(eventId, {
        trained,
        trainer_note: trainerNote,
        guide_url: guide,
      })
      queryClient.setQueryData(qk.sessionNotes(eventId), saved)
      notify('success', t('events.notes.saved', 'Notizen gespeichert'))
    } catch (err) {
      notify('error', t('common.error', 'Fehler'), err instanceof Error ? err.message : '')
    } finally {
      setSaving(false)
    }
  }

  if (!data.can_edit) {
    return data.previous ? <Previous note={data.previous} /> : null
  }
  return (
    <Stack gap="xs" data-testid="session-notes">
      {data.previous && <Previous note={data.previous} />}
      <Textarea
        label={t('events.notes.trained', 'Was trainiert wurde')}
        description={t('events.notes.trainedHint', 'Erscheint beim nächsten Termin der Serie.')}
        value={trained}
        onChange={(e) => setTrained(e.currentTarget.value)}
        autosize
        minRows={2}
        maxLength={4000}
      />
      <Textarea
        label={t('events.notes.trainerNote', 'Notiz für die nächste Trainerin, den nächsten Trainer')}
        description={t('events.notes.trainerNoteHint', 'Nur wer die Anwesenheit führt, sieht sie.')}
        value={trainerNote}
        onChange={(e) => setTrainerNote(e.currentTarget.value)}
        autosize
        minRows={2}
        maxLength={4000}
      />
      <TextInput
        label={t('events.notes.guideUrl', 'Link zur Anleitung')}
        placeholder="https://… /app/…"
        value={guide}
        onChange={(e) => setGuide(e.currentTarget.value)}
        maxLength={500}
      />
      <Group justify="flex-end">
        <Button size="xs" variant="default" disabled={!dirty} loading={saving} onClick={() => void save()}>
          {t('events.notes.save', 'Notizen speichern')}
        </Button>
      </Group>
    </Stack>
  )
}
