import { useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Badge, Button, Group, Paper, SegmentedControl, Stack, Text, TextInput, Textarea } from '@mantine/core'
import i18n from 'i18next'
import { PageHead, Field, LoadingSpinner } from '@/components/ui'
import { useToast } from '@/context/AppContext'
import { useT } from '@/locales/i18n'
import { fetchSuggestions, suggestTranslation, type TranslationSuggestion } from '@/api/i18n'
import { qk } from '@/data/keys'

const LOCALES = [
  { value: 'de-CH', label: 'Deutsch' },
  { value: 'en-GB', label: 'English' },
]
const MAX_HITS = 30

/** Every text the app shows in a language, as dotted key → text. */
function texts(locale: string): Record<string, string> {
  const out: Record<string, string> = {}
  const walk = (node: unknown, prefix: string) => {
    if (typeof node === 'string') out[prefix] = node
    else if (node && typeof node === 'object')
      for (const [k, v] of Object.entries(node)) walk(v, prefix ? `${prefix}.${k}` : k)
  }
  walk(i18n.getResourceBundle(locale, 'translation'), '')
  return out
}

/**
 * The texts belong to the platform and are the same for every club. A club
 * suggests a better wording here; a platform admin accepts it (for every
 * club) or rejects it with a reason.
 */
export function TranslationsScreen() {
  const { t } = useT()
  const { data: suggestions = [], isLoading } = useQuery({
    queryKey: qk.translationSuggestions,
    queryFn: fetchSuggestions,
  })

  return (
    <div>
      <PageHead
        title={t('suggest.title', 'Übersetzung vorschlagen')}
        desc={t(
          'suggest.desc',
          'Die Texte der App gelten für alle Vereine und werden von der Plattform gepflegt. Schlage hier eine bessere Formulierung vor; die Plattform-Verwaltung entscheidet.',
        )}
      />
      <Stack gap={20} maw={860}>
        <SuggestForm />
        <Paper withBorder radius="lg" p="lg">
          <Text fw={700} mb={10}>
            {t('suggest.mine', 'Vorschläge des Vereins')}
          </Text>
          {isLoading ? (
            <LoadingSpinner />
          ) : suggestions.length === 0 ? (
            <Text size="sm" c="dimmed">
              {t('suggest.none', 'Noch keine Vorschläge.')}
            </Text>
          ) : (
            <Stack gap={10}>
              {suggestions.map((s) => (
                <SuggestionRow key={s.id} s={s} />
              ))}
            </Stack>
          )}
        </Paper>
      </Stack>
    </div>
  )
}

function SuggestForm() {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const [locale, setLocale] = useState(i18n.language === 'en-GB' ? 'en-GB' : 'de-CH')
  const [search, setSearch] = useState('')
  const [key, setKey] = useState<string | null>(null)
  const [value, setValue] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  const all = useMemo(() => texts(locale), [locale])
  const hits = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (q.length < 2) return []
    return Object.entries(all)
      .filter(([k, v]) => k.toLowerCase().includes(q) || v.toLowerCase().includes(q))
      .slice(0, MAX_HITS)
  }, [all, search])

  const pick = (k: string) => {
    setKey(k)
    setValue(all[k] ?? '')
  }

  const submit = async () => {
    if (!key) return
    setBusy(true)
    try {
      await suggestTranslation({ locale, key, value, note: note || undefined })
      await queryClient.invalidateQueries({ queryKey: qk.translationSuggestions })
      notify(
        'success',
        t('suggest.sent', 'Vorschlag gesendet'),
        t('suggest.sentMsg', 'Die Plattform-Verwaltung prüft ihn.'),
      )
      setKey(null)
      setValue('')
      setNote('')
    } catch (err) {
      notify('error', t('common.error', 'Fehler'), err instanceof Error ? err.message : undefined)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Paper withBorder radius="lg" p="lg">
      <Stack gap={12}>
        <Group justify="space-between" wrap="wrap" gap={8}>
          <Text fw={700}>{t('suggest.new', 'Neuer Vorschlag')}</Text>
          <SegmentedControl
            size="xs"
            value={locale}
            onChange={(v) => {
              setLocale(v)
              setKey(null)
            }}
            data={LOCALES}
          />
        </Group>
        {key === null ? (
          <>
            <TextInput
              placeholder={t('suggest.search', 'Text suchen, den du ändern möchtest …')}
              value={search}
              onChange={(e) => setSearch(e.currentTarget.value)}
            />
            {hits.length > 0 && (
              <Stack gap={4}>
                {hits.map(([k, v]) => (
                  <Paper
                    key={k}
                    withBorder
                    radius="md"
                    p={8}
                    style={{ cursor: 'pointer' }}
                    onClick={() => pick(k)}
                  >
                    <Text size="sm">{v}</Text>
                    <Text size="xs" c="dimmed" ff="monospace">
                      {k}
                    </Text>
                  </Paper>
                ))}
              </Stack>
            )}
          </>
        ) : (
          <>
            <Field label={t('suggest.current', 'Heute')}>
              <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
                {all[key] ?? '—'}
              </Text>
            </Field>
            <Textarea
              label={t('suggest.proposed', 'Dein Vorschlag')}
              autosize
              minRows={2}
              value={value}
              onChange={(e) => setValue(e.currentTarget.value)}
            />
            <TextInput
              label={t('suggest.note', 'Warum? (optional)')}
              value={note}
              onChange={(e) => setNote(e.currentTarget.value)}
            />
            <Group gap={8}>
              <Button
                loading={busy}
                disabled={!value.trim() || value.trim() === (all[key] ?? '').trim()}
                onClick={submit}
              >
                {t('suggest.send', 'Vorschlag senden')}
              </Button>
              <Button variant="default" onClick={() => setKey(null)}>
                {t('common.cancel', 'Abbrechen')}
              </Button>
            </Group>
          </>
        )}
      </Stack>
    </Paper>
  )
}

function SuggestionRow({ s }: { s: TranslationSuggestion }) {
  const { t } = useT()
  const color = s.status === 'accepted' ? 'green' : s.status === 'rejected' ? 'red' : 'yellow'
  const label =
    s.status === 'accepted'
      ? t('suggest.status.accepted', 'Angenommen')
      : s.status === 'rejected'
        ? t('suggest.status.rejected', 'Abgelehnt')
        : t('suggest.status.pending', 'Offen')
  return (
    <Paper withBorder radius="md" p="sm">
      <Group justify="space-between" gap={6} mb={4} wrap="wrap">
        <Text size="xs" c="dimmed" ff="monospace">
          {s.key} · {s.locale}
        </Text>
        <Badge size="sm" color={color} variant="light">
          {label}
        </Badge>
      </Group>
      <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
        {s.proposedValue}
      </Text>
      {s.currentValue && (
        <Text size="xs" c="dimmed" mt={2}>
          {t('suggest.was', 'Vorher')}: {s.currentValue}
        </Text>
      )}
      {s.decisionNote && (
        <Text size="xs" mt={4}>
          {t('suggest.reason', 'Begründung')}: {s.decisionNote}
        </Text>
      )}
    </Paper>
  )
}
