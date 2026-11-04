import { useState, type ReactNode } from 'react'
import {
  Accordion,
  Anchor,
  Badge,
  Box,
  Button,
  Code,
  Group,
  Paper,
  SimpleGrid,
  Stack,
  Text,
  UnstyledButton,
} from '@mantine/core'
import { IconCircleCheck, IconExternalLink } from '@tabler/icons-react'
import type { Lang } from './lang'

// Release notes ("Neuigkeiten", from CHANGELOG.md) and the roadmap (from
// ROADMAP.yaml), shared by the club app and manage. Both come from the
// public /api/v1/global/version endpoints. Texts are German or English: the
// changelog comes in the page's language (?lang=), English where a version
// has no German text yet.

export interface ChangelogEntry {
  version: string
  date: string | null
  sections: Record<string, string[]>
  /** The language the sections are in; a translation that lags stays English. */
  lang?: 'de' | 'en'
}

export type RoadmapStatus = 'now' | 'next' | 'later' | 'done'

export interface RoadmapItem {
  id: string
  status: RoadmapStatus
  area: Record<string, string>
  title: Record<string, string>
  summary: Record<string, string>
  version: string | null
  link: string | null
}

const TEXT = {
  de: {
    unreleased: (prev?: string) => (prev ? `Neu seit v${prev}` : 'Neueste Änderungen'),
    unreleasedBadge: 'Noch ohne Versionsnummer',
    latest: 'Neueste Version',
    older: 'Frühere Versionen',
    loadOlder: (n: number) => `Ältere Versionen laden (${n} weitere)`,
    changes: (n: number) => (n === 1 ? '1 Änderung' : `${n} Änderungen`),
    more: 'Mehr',
    less: 'Weniger',
    showAll: (n: number) => `Alle ${n} Änderungen zeigen`,
    empty: 'Noch keine Einträge.',
    now: 'Jetzt in Arbeit',
    next: 'Als Nächstes',
    later: 'Später',
    done: 'Erledigt',
    nowHint: 'Daran arbeiten wir gerade.',
    nextHint: 'Kommt als Nächstes an die Reihe.',
    laterHint: 'Geplant, aber noch ohne Termin.',
    doneHint: 'Schon in Hubra.',
    roadmapEmpty: 'Die Roadmap ist noch leer.',
    shippedIn: (v: string) => `in v${v}`,
    englishOnly: 'Noch nicht übersetzt',
  },
  en: {
    unreleased: (prev?: string) => (prev ? `New since v${prev}` : 'Latest changes'),
    unreleasedBadge: 'No version number yet',
    latest: 'Latest version',
    older: 'Earlier versions',
    loadOlder: (n: number) => `Load older versions (${n} more)`,
    changes: (n: number) => (n === 1 ? '1 change' : `${n} changes`),
    more: 'More',
    less: 'Less',
    showAll: (n: number) => `Show all ${n} changes`,
    empty: 'No entries yet.',
    now: 'In progress',
    next: 'Up next',
    later: 'Later',
    done: 'Done',
    nowHint: 'What we are working on right now.',
    nextHint: 'What comes next.',
    laterHint: 'Planned, no date yet.',
    doneHint: 'Already in Hubra.',
    roadmapEmpty: 'The roadmap is still empty.',
    shippedIn: (v: string) => `in v${v}`,
    englishOnly: 'Not translated yet',
  },
} as const

const SECTION: Record<string, { de: string; en: string; color: string }> = {
  added: { de: 'Neu', en: 'Added', color: 'green' },
  changed: { de: 'Geändert', en: 'Changed', color: 'blue' },
  fixed: { de: 'Behoben', en: 'Fixed', color: 'orange' },
  removed: { de: 'Entfernt', en: 'Removed', color: 'red' },
  deprecated: { de: 'Veraltet', en: 'Deprecated', color: 'gray' },
  security: { de: 'Sicherheit', en: 'Security', color: 'grape' },
}

const isUnreleased = (e: ChangelogEntry) => e.version.toLowerCase() === 'unreleased'
const itemCount = (e: ChangelogEntry) =>
  Object.values(e.sections).reduce((n, items) => n + items.length, 0)

/** Releases worth showing: the empty "Unreleased" heading is left out. */
export function visibleReleases(entries: ChangelogEntry[]): ChangelogEntry[] {
  return entries.filter((e) => itemCount(e) > 0)
}

/**
 * A key for the newest release notes, to tell whether someone has seen them.
 * "Unreleased" grows without a new version, so its item count is part of it.
 */
export function latestReleaseKey(entries: ChangelogEntry[]): string | null {
  const top = visibleReleases(entries)[0]
  if (!top) return null
  return isUnreleased(top) ? `unreleased:${itemCount(top)}` : top.version
}

function formatDate(iso: string | null, lang: Lang) {
  if (!iso) return null
  const d = new Date(`${iso}T12:00:00`)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString(lang === 'en' ? 'en-GB' : 'de-CH', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

/** **bold** and `code` from changelog lines, as text (never as HTML). */
export function InlineMarkdown({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean)
  return (
    <>
      {parts.map((part, i) =>
        part.startsWith('**') && part.endsWith('**') ? (
          <strong key={i}>{part.slice(2, -2)}</strong>
        ) : part.startsWith('`') && part.endsWith('`') ? (
          <Code key={i} fz="0.85em">
            {part.slice(1, -1)}
          </Code>
        ) : (
          part
        ),
      )}
    </>
  )
}

/** One changelog line: "**Title**: details" shows the title on its own line. */
function ReleaseItem({ text, lang }: { text: string; lang: Lang }) {
  const [open, setOpen] = useState(false)
  const m = /^\*\*([^*]+)\*\*[:.]?\s*(.*)$/s.exec(text)
  const title = m ? m[1] : null
  // "**Title**: details" often goes on in lower case; it stands alone here.
  const body = m ? m[2].replace(/^[a-zäöü]/, (c) => c.toUpperCase()) : text
  const long = body.length > 220
  return (
    <Box py={6} style={{ borderTop: '1px solid var(--hb-border)' }}>
      {title && (
        <Text fz="sm" fw={650} style={{ overflowWrap: 'anywhere' }}>
          <InlineMarkdown text={title} />
        </Text>
      )}
      {body && (
        <Text
          fz="sm"
          c={title ? 'var(--hb-text-2)' : undefined}
          lineClamp={long && !open ? 3 : undefined}
          style={{ overflowWrap: 'anywhere' }}
        >
          <InlineMarkdown text={body} />
        </Text>
      )}
      {long && (
        <UnstyledButton
          onClick={() => setOpen((o) => !o)}
          fz="xs"
          fw={600}
          c="var(--mantine-primary-color-filled)"
          mt={2}
        >
          {open ? TEXT[lang].less : TEXT[lang].more}
        </UnstyledButton>
      )}
    </Box>
  )
}

function ReleaseSections({ entry, lang, limit }: { entry: ChangelogEntry; lang: Lang; limit?: number }) {
  const [all, setAll] = useState(false)
  const total = itemCount(entry)
  const cap = limit && !all && total > limit + 2 ? limit : Infinity
  let left = cap
  return (
    <Stack gap={14}>
      {Object.entries(entry.sections)
        .filter(([, items]) => items.length > 0)
        .map(([section, items]) => {
          const shown = items.slice(0, Math.max(0, left))
          left -= shown.length
          if (shown.length === 0) return null
          const s = SECTION[section.toLowerCase()]
          return (
            <div key={section}>
              <Badge variant="light" color={s?.color ?? 'gray'} size="sm" mb={4}>
                {s ? s[lang] : section}
              </Badge>
              {shown.map((item, i) => (
                <ReleaseItem key={section + i} text={item} lang={lang} />
              ))}
            </div>
          )
        })}
      {cap < total && (
        <Button variant="light" size="compact-sm" style={{ alignSelf: 'flex-start' }} onClick={() => setAll(true)}>
          {TEXT[lang].showAll(total)}
        </Button>
      )}
    </Stack>
  )
}

/** Shown on a version whose text is English in a German page. */
function EnglishOnly({ entry, lang }: { entry: ChangelogEntry; lang: Lang }) {
  if (lang === 'en' || entry.lang !== 'en') return null
  return (
    <Badge variant="outline" color="gray" size="xs">
      {TEXT[lang].englishOnly}
    </Badge>
  )
}

function releaseTitle(entry: ChangelogEntry, entries: ChangelogEntry[], lang: Lang) {
  if (!isUnreleased(entry)) return `v${entry.version}`
  const prev = entries.find((e) => !isUnreleased(e))
  return TEXT[lang].unreleased(prev?.version)
}

/**
 * The newest release open at the top, older ones below as a list that
 * opens one version at a time and loads `pageSize` more on request.
 */
export function ReleaseNotes({
  entries,
  lang,
  pageSize = 5,
  latestLimit = 6,
}: {
  entries: ChangelogEntry[]
  lang: Lang
  /** Older versions listed at first, and added per "load older". */
  pageSize?: number
  /** Changes of the newest release shown before "show all". */
  latestLimit?: number
}) {
  const t = TEXT[lang]
  const releases = visibleReleases(entries)
  const [shown, setShown] = useState(pageSize)
  if (releases.length === 0)
    return (
      <Text fz="sm" c="dimmed">
        {t.empty}
      </Text>
    )
  const [latest, ...older] = releases
  const rest = older.length - shown

  return (
    <Stack gap={20}>
      <Paper withBorder radius="lg" p={{ base: 'sm', sm: 'md' }}>
        <Group gap={8} mb={10} wrap="wrap" align="baseline">
          <Text fz="lg" fw={750}>
            {releaseTitle(latest, entries, lang)}
          </Text>
          <Badge variant="light" size="sm">
            {isUnreleased(latest) ? t.unreleasedBadge : t.latest}
          </Badge>
          {latest.date && (
            <Text fz="xs" c="dimmed">
              {formatDate(latest.date, lang)}
            </Text>
          )}
          <EnglishOnly entry={latest} lang={lang} />
        </Group>
        <ReleaseSections entry={latest} lang={lang} limit={latestLimit} />
      </Paper>

      {older.length > 0 && (
        <div>
          <Text fz="xs" fw={700} tt="uppercase" c="dimmed" mb={6} style={{ letterSpacing: '0.06em' }}>
            {t.older}
          </Text>
          <Accordion variant="separated" radius="md" chevronPosition="right">
            {older.slice(0, shown).map((entry) => (
              <Accordion.Item key={entry.version} value={entry.version}>
                <Accordion.Control>
                  <Group gap={8} wrap="wrap" align="baseline">
                    <Text fz="sm" fw={700}>
                      {releaseTitle(entry, entries, lang)}
                    </Text>
                    {entry.date && (
                      <Text fz="xs" c="dimmed">
                        {formatDate(entry.date, lang)}
                      </Text>
                    )}
                    <Text fz="xs" c="dimmed">
                      · {t.changes(itemCount(entry))}
                    </Text>
                    <EnglishOnly entry={entry} lang={lang} />
                  </Group>
                </Accordion.Control>
                <Accordion.Panel>
                  <ReleaseSections entry={entry} lang={lang} />
                </Accordion.Panel>
              </Accordion.Item>
            ))}
          </Accordion>
          {rest > 0 && (
            <Button variant="subtle" size="compact-sm" mt={8} onClick={() => setShown((n) => n + pageSize)}>
              {t.loadOlder(rest)}
            </Button>
          )}
        </div>
      )}
    </Stack>
  )
}

const pick = (texts: Record<string, string> | null | undefined, lang: Lang) =>
  !texts ? '' : texts[lang] ?? texts.en ?? texts.de ?? Object.values(texts)[0] ?? ''

const STATUS_COLOR: Record<RoadmapStatus, string> = {
  now: 'violet',
  next: 'blue',
  later: 'gray',
  done: 'green',
}

function RoadmapCard({ item, lang }: { item: RoadmapItem; lang: Lang }) {
  const summary = pick(item.summary, lang)
  return (
    <Paper withBorder radius="md" p="sm" h="100%">
      <Stack gap={6}>
        {pick(item.area, lang) && (
          <Badge variant="light" color={STATUS_COLOR[item.status]} size="xs" style={{ alignSelf: 'flex-start' }}>
            {pick(item.area, lang)}
          </Badge>
        )}
        <Text fz="sm" fw={650} style={{ overflowWrap: 'anywhere' }}>
          {pick(item.title, lang)}
        </Text>
        {summary && (
          <Text fz="sm" c="var(--hb-text-2)" style={{ overflowWrap: 'anywhere' }}>
            {summary}
          </Text>
        )}
        {item.link && (
          <Anchor href={item.link} target="_blank" rel="noopener noreferrer" fz="xs">
            <Group gap={4} wrap="nowrap">
              {item.link.replace(/^https:\/\//, '').slice(0, 48)}
              <IconExternalLink size={12} />
            </Group>
          </Anchor>
        )}
      </Stack>
    </Paper>
  )
}

function RoadmapGroup({
  title,
  hint,
  color,
  count,
  children,
}: {
  title: string
  hint: string
  color: string
  count: number
  children: ReactNode
}) {
  return (
    <div>
      <Group gap={8} mb={2} align="center">
        <Box w={10} h={10} style={{ borderRadius: 99, background: `var(--mantine-color-${color}-filled)` }} />
        <Text fz="md" fw={750}>
          {title}
        </Text>
        <Badge variant="default" size="sm" radius="sm">
          {count}
        </Badge>
      </Group>
      <Text fz="xs" c="dimmed" mb={8}>
        {hint}
      </Text>
      {children}
    </div>
  )
}

/**
 * The roadmap: in progress, up next, later (as cards) and done (a short
 * list with the version each shipped in). `wide` puts two cards per row.
 */
export function Roadmap({ items, lang, wide = false }: { items: RoadmapItem[]; lang: Lang; wide?: boolean }) {
  const t = TEXT[lang]
  if (items.length === 0)
    return (
      <Text fz="sm" c="dimmed">
        {t.roadmapEmpty}
      </Text>
    )
  const of = (s: RoadmapStatus) => items.filter((i) => i.status === s)
  const open = (['now', 'next', 'later'] as const).filter((s) => of(s).length > 0)
  const done = of('done')

  return (
    <Stack gap={24}>
      {open.map((s) => (
        <RoadmapGroup key={s} title={t[s]} hint={t[`${s}Hint`]} color={STATUS_COLOR[s]} count={of(s).length}>
          <SimpleGrid cols={wide ? { base: 1, sm: 2, lg: 3 } : 1} spacing="sm">
            {of(s).map((item) => (
              <RoadmapCard key={item.id} item={item} lang={lang} />
            ))}
          </SimpleGrid>
        </RoadmapGroup>
      ))}
      {done.length > 0 && (
        <RoadmapGroup title={t.done} hint={t.doneHint} color={STATUS_COLOR.done} count={done.length}>
          <Stack gap={0}>
            {done.map((item) => (
              <Group
                key={item.id}
                gap={10}
                py={8}
                wrap="nowrap"
                align="flex-start"
                style={{ borderTop: '1px solid var(--hb-border)' }}
              >
                <IconCircleCheck size={18} color="var(--mantine-color-green-filled)" style={{ flexShrink: 0, marginTop: 2 }} />
                <div style={{ minWidth: 0, flex: 1 }}>
                  <Group gap={6} wrap="wrap" align="baseline">
                    <Text fz="sm" fw={600} style={{ overflowWrap: 'anywhere' }}>
                      {pick(item.title, lang)}
                    </Text>
                    {item.version && (
                      <Text fz="xs" c="dimmed">
                        {t.shippedIn(item.version)}
                      </Text>
                    )}
                  </Group>
                  {pick(item.summary, lang) && (
                    <Text fz="xs" c="dimmed" style={{ overflowWrap: 'anywhere' }}>
                      {pick(item.summary, lang)}
                    </Text>
                  )}
                </div>
              </Group>
            ))}
          </Stack>
        </RoadmapGroup>
      )}
    </Stack>
  )
}
