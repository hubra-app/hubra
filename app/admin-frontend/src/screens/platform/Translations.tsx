import { useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Badge,
  Button,
  Group,
  Paper,
  SegmentedControl,
  Stack,
  Table,
  Text,
  Textarea,
  TextInput,
  Title,
} from '@mantine/core'
import { useAdmin } from '@/context/AdminContext'
import { useLang } from '@/lang'
import { formatDate } from '@/format'
import {
  decideTranslationRequest,
  listTranslationRequests,
  listTranslations,
  saveTranslation,
  type TranslationRequest,
} from '@/api/translations'

const LOCALES = ['de-CH', 'en-GB'] as const
const PAGE = 100

type Filter = 'all' | 'missing'

/**
 * The platform's texts, the same for every club: the app ships them, `flask
 * seed` loads them, and edits here go to every club at once. Clubs suggest
 * changes, which land in the list on top.
 */
export function PlatformTranslations() {
  const { tr } = useLang()
  return (
    <Stack gap={20}>
      <Suggestions />
      <Paper withBorder shadow="sm" radius="lg" p="lg">
        <Title order={3} mb={4}>
          {tr('Texte', 'Texts')}
        </Title>
        <Text size="xs" c="dimmed" mb={12}>
          {tr(
            'Die Texte der Vereins-App für alle Vereine. Eine Änderung gilt sofort überall; ein leerer Text zeigt wieder den mitgelieferten.',
            "The club app's texts for every club. A change applies everywhere at once; an empty text shows the shipped one again.",
          )}
        </Text>
        <Editor />
      </Paper>
    </Stack>
  )
}

function Editor() {
  const { tr } = useLang()
  const { notify } = useAdmin()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<Filter>('all')
  const [shown, setShown] = useState(PAGE)
  const [editing, setEditing] = useState<{ key: string; locale: string; value: string } | null>(
    null,
  )
  const [saving, setSaving] = useState(false)

  const de = useQuery({ queryKey: ['translations', 'de-CH'], queryFn: () => listTranslations('de-CH') })
  const en = useQuery({ queryKey: ['translations', 'en-GB'], queryFn: () => listTranslations('en-GB') })

  const rows = useMemo(() => {
    const byLocale = { 'de-CH': de.data ?? [], 'en-GB': en.data ?? [] }
    const keys = new Map<string, Record<string, { value: string }>>()
    for (const locale of LOCALES) {
      for (const r of byLocale[locale]) {
        if (r.alias_for) continue
        const entry = keys.get(r.key) ?? {}
        entry[locale] = { value: r.value }
        keys.set(r.key, entry)
      }
    }
    const q = search.trim().toLowerCase()
    return [...keys.entries()]
      .filter(([key, v]) => {
        if (filter === 'missing' && LOCALES.every((l) => v[l]?.value)) return false
        if (!q) return true
        return (
          key.toLowerCase().includes(q) ||
          LOCALES.some((l) => v[l]?.value.toLowerCase().includes(q))
        )
      })
      .sort(([a], [b]) => (a < b ? -1 : 1))
  }, [de.data, en.data, search, filter])

  const save = async () => {
    if (!editing) return
    setSaving(true)
    try {
      await saveTranslation(editing.locale, editing.key, editing.value)
      await queryClient.invalidateQueries({ queryKey: ['translations', editing.locale] })
      setEditing(null)
      notify('success', tr('Text gespeichert', 'Text saved'))
    } catch (err) {
      notify('error', tr('Speichern fehlgeschlagen', 'Save failed'), (err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  if (de.isLoading || en.isLoading) {
    return (
      <Text size="sm" c="dimmed">
        {tr('Wird geladen …', 'Loading…')}
      </Text>
    )
  }

  return (
    <Stack gap={12}>
      <Group gap={10} wrap="wrap">
        <TextInput
          placeholder={tr('Schlüssel oder Text suchen …', 'Search key or text…')}
          value={search}
          onChange={(e) => {
            setSearch(e.currentTarget.value)
            setShown(PAGE)
          }}
          style={{ flex: 1, minWidth: 220 }}
        />
        <SegmentedControl
          value={filter}
          onChange={(v) => {
            setFilter(v as Filter)
            setShown(PAGE)
          }}
          data={[
            { value: 'all', label: tr('Alle', 'All') },
            { value: 'missing', label: tr('Fehlend', 'Missing') },
          ]}
        />
      </Group>
      <Text size="xs" c="dimmed">
        {tr(`${rows.length} Texte`, `${rows.length} texts`)}
      </Text>
      <Table.ScrollContainer minWidth={760}>
        <Table verticalSpacing={6}>
          <Table.Thead>
            <Table.Tr>
              <Table.Th style={{ width: '28%' }}>{tr('Schlüssel', 'Key')}</Table.Th>
              <Table.Th>Deutsch</Table.Th>
              <Table.Th>English</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {rows.slice(0, shown).map(([key, v]) => (
              <Table.Tr key={key}>
                <Table.Td data-label={tr('Schlüssel', 'Key')}>
                  <Text size="xs" ff="monospace" style={{ wordBreak: 'break-all' }}>
                    {key}
                  </Text>
                </Table.Td>
                {LOCALES.map((locale) => {
                  const cell = v[locale]
                  const isEditing = editing?.key === key && editing.locale === locale
                  return (
                    <Table.Td key={locale} data-label={locale === 'de-CH' ? 'Deutsch' : 'English'}>
                      {isEditing ? (
                        <Stack gap={6}>
                          <Textarea
                            autosize
                            minRows={1}
                            autoFocus
                            value={editing.value}
                            onChange={(e) => setEditing({ ...editing, value: e.currentTarget.value })}
                            onKeyDown={(e) => {
                              if (e.key === 'Escape') setEditing(null)
                              if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault()
                                save()
                              }
                            }}
                          />
                          <Group gap={6}>
                            <Button size="xs" loading={saving} onClick={save}>
                              {tr('Speichern', 'Save')}
                            </Button>
                            <Button size="xs" variant="default" onClick={() => setEditing(null)}>
                              {tr('Abbrechen', 'Cancel')}
                            </Button>
                          </Group>
                        </Stack>
                      ) : (
                        <Text
                          size="sm"
                          c={cell?.value ? undefined : 'dimmed'}
                          style={{ cursor: 'pointer', whiteSpace: 'pre-wrap' }}
                          onClick={() => setEditing({ key, locale, value: cell?.value ?? '' })}
                        >
                          {cell?.value || tr('— fehlt —', '— missing —')}
                        </Text>
                      )}
                    </Table.Td>
                  )
                })}
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
      {rows.length > shown && (
        <Button variant="default" onClick={() => setShown(shown + PAGE)}>
          {tr('Mehr anzeigen', 'Show more')}
        </Button>
      )}
    </Stack>
  )
}

function Suggestions() {
  const { tr } = useLang()
  const [view, setView] = useState<'pending' | 'done'>('pending')
  const { data = [], isLoading } = useQuery({
    queryKey: ['translation-requests'],
    queryFn: () => listTranslationRequests(),
  })
  const pending = data.filter((r) => r.status === 'pending')
  const shown = view === 'pending' ? pending : data.filter((r) => r.status !== 'pending')

  return (
    <Paper withBorder shadow="sm" radius="lg" p="lg">
      <Group justify="space-between" mb={4}>
        <Title order={3}>
          {tr('Vorschläge der Vereine', 'Suggestions from clubs')}
          {pending.length > 0 && (
            <Badge ml={8} color="yellow" variant="light">
              {pending.length}
            </Badge>
          )}
        </Title>
        <SegmentedControl
          size="xs"
          value={view}
          onChange={(v) => setView(v as 'pending' | 'done')}
          data={[
            { value: 'pending', label: tr('Offen', 'Open') },
            { value: 'done', label: tr('Erledigt', 'Done') },
          ]}
        />
      </Group>
      <Text size="xs" c="dimmed" mb={12}>
        {tr(
          'Annehmen ändert den Text für alle Vereine. Beim Ablehnen sieht der Verein deine Begründung.',
          'Accepting changes the text for every club. When you reject, the club sees your reason.',
        )}
      </Text>
      {isLoading ? (
        <Text size="sm" c="dimmed">
          {tr('Wird geladen …', 'Loading…')}
        </Text>
      ) : shown.length === 0 ? (
        <Text size="sm" c="dimmed">
          {view === 'pending'
            ? tr('Keine offenen Vorschläge.', 'No open suggestions.')
            : tr('Noch nichts entschieden.', 'Nothing decided yet.')}
        </Text>
      ) : (
        <Stack gap={10}>
          {shown.map((r) => (
            <SuggestionCard key={r.id} r={r} />
          ))}
        </Stack>
      )}
    </Paper>
  )
}

function SuggestionCard({ r }: { r: TranslationRequest }) {
  const { tr } = useLang()
  const { notify } = useAdmin()
  const queryClient = useQueryClient()
  const [value, setValue] = useState(r.proposedValue)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState<'accept' | 'reject' | null>(null)
  const pending = r.status === 'pending'
  const changedSince = pending && (r.liveValue ?? null) !== (r.currentValue ?? null)

  const decide = async (accept: boolean) => {
    setBusy(accept ? 'accept' : 'reject')
    try {
      await decideTranslationRequest(r.id, accept, {
        value: accept ? value : undefined,
        note: note || undefined,
      })
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['translation-requests'] }),
        queryClient.invalidateQueries({ queryKey: ['translations', r.locale] }),
      ])
      notify(
        'success',
        accept ? tr('Vorschlag angenommen', 'Suggestion accepted') : tr('Vorschlag abgelehnt', 'Suggestion rejected'),
      )
    } catch (err) {
      notify('error', tr('Fehlgeschlagen', 'Failed'), (err as Error).message)
    } finally {
      setBusy(null)
    }
  }

  return (
    <Paper withBorder radius="md" p="md">
      <Group justify="space-between" mb={6} wrap="wrap" gap={6}>
        <Group gap={8}>
          <Text size="xs" ff="monospace">
            {r.key}
          </Text>
          <Badge size="xs" variant="outline" color="gray">
            {r.locale}
          </Badge>
          {!pending && (
            <Badge size="xs" color={r.status === 'accepted' ? 'green' : 'red'} variant="light">
              {r.status === 'accepted' ? tr('Angenommen', 'Accepted') : tr('Abgelehnt', 'Rejected')}
            </Badge>
          )}
        </Group>
        <Text size="xs" c="dimmed">
          {r.tenantName ?? tr('Verein gelöscht', 'Club deleted')}
          {r.createdAt ? ` · ${formatDate(r.createdAt)}` : ''}
        </Text>
      </Group>
      <Text size="sm" c="dimmed" style={{ whiteSpace: 'pre-wrap' }}>
        {tr('Jetzt', 'Now')}: {r.currentValue ?? tr('— fehlt —', '— missing —')}
      </Text>
      {changedSince && (
        <Text size="xs" c="orange">
          {tr('Inzwischen geändert zu', 'Since changed to')}: {r.liveValue ?? '—'}
        </Text>
      )}
      {r.note && (
        <Text size="xs" mt={4} fs="italic">
          «{r.note}»
        </Text>
      )}
      {pending ? (
        <Stack gap={8} mt={8}>
          <Textarea
            label={tr('Vorgeschlagen (du kannst es anpassen)', 'Suggested (you can adjust it)')}
            autosize
            minRows={1}
            value={value}
            onChange={(e) => setValue(e.currentTarget.value)}
          />
          <TextInput
            label={tr('Begründung für den Verein (optional)', 'Note for the club (optional)')}
            value={note}
            onChange={(e) => setNote(e.currentTarget.value)}
          />
          <Group gap={8}>
            <Button size="xs" loading={busy === 'accept'} disabled={!value.trim()} onClick={() => decide(true)}>
              {tr('Annehmen', 'Accept')}
            </Button>
            <Button size="xs" variant="default" color="red" loading={busy === 'reject'} onClick={() => decide(false)}>
              {tr('Ablehnen', 'Reject')}
            </Button>
          </Group>
        </Stack>
      ) : (
        <>
          <Text size="sm" mt={4} style={{ whiteSpace: 'pre-wrap' }}>
            {tr('Vorschlag', 'Suggestion')}: {r.proposedValue}
          </Text>
          {r.decisionNote && (
            <Text size="xs" c="dimmed" mt={4}>
              {tr('Begründung', 'Note')}: {r.decisionNote}
            </Text>
          )}
        </>
      )}
    </Paper>
  )
}
