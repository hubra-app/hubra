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
  TextInput,
  Textarea,
} from '@mantine/core'
import i18n from 'i18next'
import { PageHead, Field, LoadingSpinner } from '@/components/ui'
import { useToast } from '@/context/AppContext'
import { useT } from '@/locales/i18n'
import { fetchSuggestions, suggestTranslation, type TranslationSuggestion } from '@/api/i18n'
import { qk } from '@/data/keys'
import { usePlugins } from '@/plugins/store'
import { coverage, flatten, percent, type CoverageRow } from './coverage'

const LOCALES = [
  { value: 'de-CH', label: 'Deutsch' },
  { value: 'en-GB', label: 'English' },
]
const MAX_HITS = 30
const MAX_MISSING = 50

/** Every text the app shows in a language, as dotted key → text. */
function texts(locale: string): Record<string, string> {
  return flatten(i18n.getResourceBundle(locale, 'translation'))
}

interface Preset {
  locale: string
  key: string
  n: number
}

/**
 * The texts belong to the platform and are the same for every club. A club
 * suggests a better wording here; a platform admin accepts it (for every
 * club) or rejects it with a reason.
 */
export function TranslationsScreen() {
  const { t } = useT()
  const [preset, setPreset] = useState<Preset | null>(null)
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
        <SuggestForm key={preset?.n ?? 0} preset={preset} />
        <Coverage
          onSuggest={(locale, key) => {
            setPreset((p) => ({ locale, key, n: (p?.n ?? 0) + 1 }))
            window.scrollTo({ top: 0, behavior: 'smooth' })
          }}
        />
        <Paper withBorder p="lg">
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

function SuggestForm({ preset }: { preset: Preset | null }) {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const [locale, setLocale] = useState(
    preset?.locale ?? (i18n.language === 'en-GB' ? 'en-GB' : 'de-CH'),
  )
  const [search, setSearch] = useState('')
  const [key, setKey] = useState<string | null>(preset?.key ?? null)
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
    <Paper withBorder p="lg">
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
            <Text size="xs" c="dimmed" ff="monospace">
              {key}
            </Text>
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

/** Texts a language lacks, per source (Hubra or a plugin), each with a
 * button that starts a suggestion for it. */
function Coverage({ onSuggest }: { onSuggest: (locale: string, key: string) => void }) {
  const { t } = useT()
  const plugins = usePlugins()
  const [open, setOpen] = useState<{ id: string; locale: string } | null>(null)
  const rows = useMemo(() => {
    const all = Object.fromEntries(LOCALES.map((l) => [l.value, texts(l.value)]))
    const sources = plugins.map((p) => {
      const keys = new Set<string>()
      for (const bundle of Object.values(p.translations ?? {}))
        for (const k of Object.keys(flatten(bundle))) keys.add(k)
      return { id: p.id, keys }
    })
    return coverage(all, sources)
  }, [plugins])
  const name = (id: string) =>
    id === 'core' ? 'Hubra' : id.charAt(0).toUpperCase() + id.slice(1)
  const current = open ? rows.find((r) => r.id === open.id) : undefined
  const missing = current && open ? current.missing[open.locale] : []
  const other = open ? LOCALES.find((l) => l.value !== open.locale)?.value : undefined
  const reference = useMemo(() => (other ? texts(other) : {}), [other])

  return (
    <Paper withBorder p="lg" data-testid="translation-coverage">
      <Text fw={700}>{t('suggest.coverage.title', 'Abdeckung')}</Text>
      <Text size="sm" c="dimmed" mb={10}>
        {t(
          'suggest.coverage.desc',
          'Wie viele Texte es in jeder Sprache gibt, für Hubra und jedes Plugin. Fehlt einer, kannst du ihn vorschlagen.',
        )}
      </Text>
      <Table.ScrollContainer minWidth={420}>
        <Table verticalSpacing={6}>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{t('suggest.coverage.source', 'Bereich')}</Table.Th>
              {LOCALES.map((l) => (
                <Table.Th key={l.value}>{l.label}</Table.Th>
              ))}
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {rows.map((row) => (
              <Table.Tr key={row.id}>
                <Table.Td>
                  <Text size="sm">{name(row.id)}</Text>
                  <Text size="xs" c="dimmed">
                    {t('suggest.coverage.texts', '{{count}} Texte', { count: row.total })}
                  </Text>
                </Table.Td>
                {LOCALES.map((l) => (
                  <Table.Td key={l.value}>
                    <CoverageCell
                      row={row}
                      locale={l.value}
                      active={open?.id === row.id && open.locale === l.value}
                      onOpen={() =>
                        setOpen((o) =>
                          o?.id === row.id && o.locale === l.value
                            ? null
                            : { id: row.id, locale: l.value },
                        )
                      }
                    />
                  </Table.Td>
                ))}
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
      {open && current && missing.length > 0 && (
        <Stack gap={4} mt={12} data-testid="translation-missing">
          <Text size="sm" fw={600}>
            {t('suggest.coverage.missingIn', 'Fehlt in {{lang}} ({{source}})', {
              lang: LOCALES.find((l) => l.value === open.locale)?.label ?? open.locale,
              source: name(current.id),
            })}
          </Text>
          {missing.slice(0, MAX_MISSING).map((k) => (
            <Paper key={k} withBorder p={8}>
              <Group justify="space-between" wrap="nowrap" gap={8}>
                <div style={{ minWidth: 0 }}>
                  <Text size="sm" truncate>
                    {reference[k] ?? '—'}
                  </Text>
                  <Text size="xs" c="dimmed" ff="monospace" truncate>
                    {k}
                  </Text>
                </div>
                <Button size="xs" variant="light" onClick={() => onSuggest(open.locale, k)}>
                  {t('suggest.coverage.suggest', 'Vorschlagen')}
                </Button>
              </Group>
            </Paper>
          ))}
          {missing.length > MAX_MISSING && (
            <Text size="xs" c="dimmed">
              {t('suggest.coverage.more', 'und {{count}} weitere', {
                count: missing.length - MAX_MISSING,
              })}
            </Text>
          )}
        </Stack>
      )}
    </Paper>
  )
}

function CoverageCell({
  row,
  locale,
  active,
  onOpen,
}: {
  row: CoverageRow
  locale: string
  active: boolean
  onOpen: () => void
}) {
  const { t } = useT()
  const pct = percent(row, locale)
  const count = row.missing[locale]?.length ?? 0
  if (!count)
    return (
      <Badge color="green" variant="light">
        100 %
      </Badge>
    )
  return (
    <Button size="compact-sm" variant={active ? 'filled' : 'light'} color="orange" onClick={onOpen}>
      {t('suggest.coverage.missing', '{{pct}} % · {{count}} fehlen', { pct, count })}
    </Button>
  )
}

function SuggestionRow({ s }: { s: TranslationSuggestion }) {
  const { t } = useT()
  const color = s.status === 'accepted' ? 'green' : s.status === 'rejected' ? 'red' : 'orange'
  const label =
    s.status === 'accepted'
      ? t('suggest.status.accepted', 'Angenommen')
      : s.status === 'rejected'
        ? t('suggest.status.rejected', 'Abgelehnt')
        : t('suggest.status.pending', 'Offen')
  return (
    <Paper withBorder p="sm">
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
