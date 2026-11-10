import { categoryColors, colorText } from '@hubra/ui'
import { useState, useEffect, useRef } from 'react'
import { useQueries, useQuery } from '@tanstack/react-query'
import { TextInput, Box, Text, Stack, Kbd } from '@mantine/core'
import { useHotkeys } from '@mantine/hooks'
import { IconSearch } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useNav, useApp } from '@/context/AppContext'
import { searchClub } from '@/api/search'
import { formatDate } from '@/format'
import { listAuditLog } from '@/api/settings'
import type { SearchResult } from './nav'
import { useSidebarNav } from './useSidebarNav'
import { qk } from '@/data/keys'
import { usePluginSearches } from '@/plugins'

// One shared empty list, so an unloaded query keeps the same value each render.
const NONE: never[] = []

export function GlobalSearch({
  fullWidth = false,
  onDone,
}: {
  /** Phones: fills the bar, focuses itself and reports when it is done. */
  fullWidth?: boolean
  onDone?: () => void
} = {}) {
  const { t } = useT()
  const { go } = useNav()
  const { hasPermission } = useApp()
  // Pages too, hidden ones included, so nothing is out of reach.
  const { customizable: pages } = useSidebarNav()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [dropOpen, setDropOpen] = useState(false)
  // Load what the search looks through only once someone uses it.
  const [used, setUsed] = useState(false)
  const searchRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  // Arrow keys move through the results, Enter opens the highlighted one.
  const [active, setActive] = useState(0)
  // Ctrl+K / Cmd+K jumps to the search from anywhere.
  useHotkeys([['mod+K', () => inputRef.current?.focus()]])
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [term, setTerm] = useState('')

  // Members, groups, events, posts, polls, invoices and what plugins offer
  // through `<module>.search`, searched on the server (each module checks
  // the member's rights).
  const { data: server } = useQuery({
    queryKey: qk.search.club(term.trim().toLowerCase()),
    enabled: term.trim().length >= 2,
    queryFn: ({ signal }) => searchClub(term.trim(), signal),
    staleTime: 30_000,
  })
  // Lists plugins add in the browser (Inventory, …), each loaded once.
  const pluginSearches = usePluginSearches()
  const pluginLists = useQueries({
    queries: pluginSearches.map((s) => ({
      queryKey: [...qk.search.plugin, s.plugin, s.id],
      enabled: used,
      queryFn: s.load,
      staleTime: 60_000,
    })),
  })
  const pluginData = pluginLists.map((q) => q.data)
  const { data: auditPage } = useQuery({
    queryKey: qk.search.audit,
    enabled: used && hasPermission('audit.audit.read'),
    queryFn: () => listAuditLog({ pageSize: 200 }),
    staleTime: 60_000,
  })

  const runSearch = (q: string) => {
    if (q.trim().length < 2) {
      setResults([])
      setDropOpen(false)
      return
    }
    const lower = q.trim().toLowerCase()

    // Per kind at most three, as before; the server sends up to five.
    const perKind = new Map<string, number>()
    const serverResults: SearchResult[] = []
    for (const hit of server?.hits ?? NONE) {
      const n = perKind.get(hit.kind) ?? 0
      if (n >= 3) continue
      perKind.set(hit.kind, n + 1)
      serverResults.push({
        kind: hit.kind,
        id: hit.id,
        label: hit.label,
        sub:
          hit.kind === 'poll'
            ? hit.sub === 'open'
              ? t('shell.search.pollOpen', 'Offen')
              : t('shell.search.pollClosed', 'Geschlossen')
            : [hit.date ? formatDate(hit.date) : null, hit.sub].filter(Boolean).join(' · ') || undefined,
        path: hit.path,
      })
    }
    const pluginResults: SearchResult[] = pluginSearches.flatMap((s, i) =>
      (pluginData[i] ?? NONE)
        .filter((hit) =>
          [hit.label, hit.sub, hit.keywords].some((v) => v?.toLowerCase().includes(lower)),
        )
        .slice(0, 3)
        .map((hit) => ({
          kind: `${s.plugin}:${s.id}` as const,
          id: String(hit.id),
          label: hit.label,
          sub: hit.sub,
          path: hit.path,
        })),
    )
    const pageResults: SearchResult[] = pages
      .filter((p) => p.label.toLowerCase().includes(lower))
      .slice(0, 3)
      .map((p) => ({ kind: 'page', id: p.path, label: p.label, path: p.path }))
    const auditResults: SearchResult[] = (auditPage?.entries ?? [])
      .filter(
        (e) =>
          e.actor.toLowerCase().includes(lower) ||
          e.action.toLowerCase().includes(lower) ||
          e.target.toLowerCase().includes(lower),
      )
      .slice(0, 3)
      .map((e) => ({
        kind: 'audit',
        id: e.id,
        label: e.action,
        sub: `${e.actor} · ${e.target}`,
        path: `/app/audit-log/${e.id}`,
      }))

    setResults([...pageResults, ...serverResults, ...pluginResults, ...auditResults])
    setActive(0)
    setDropOpen(true)
  }

  // Search with the answers of this render: they arrive after the letters
  // are typed, so search again once they do instead of keeping "no results".
  const sources = [term, server, auditPage, ...pluginData]
  const [searched, setSearched] = useState(sources)
  if (sources.some((s, i) => s !== searched[i])) {
    setSearched(sources)
    runSearch(term)
  }

  const handleQueryChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const q = e.target.value
    setQuery(q)
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => setTerm(q), 200)
  }

  const clearSearch = () => {
    if (timerRef.current) clearTimeout(timerRef.current)
    setQuery('')
    setTerm('')
  }

  const handleResultClick = (r: SearchResult) => {
    go(r.path)
    clearSearch()
    setResults([])
    setDropOpen(false)
    onDone?.()
  }

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setDropOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const kindLabel: Record<string, string> = {
    member: t('common.member'),
    group: t('shell.searchKind.group'),
    event: t('shell.searchKind.event'),
    invoice: t('shell.searchKind.invoice'),
    poll: t('shell.searchKind.poll'),
    post: t('shell.searchKind.post', 'Beitrag'),
    audit: t('shell.searchKind.audit'),
    page: t('shell.searchKind.page'),
  }
  for (const s of pluginSearches) kindLabel[`${s.plugin}:${s.id}`] = t(s.label)
  const kindColors: Record<string, { bg: string; color: string }> = {
    member: { bg: `color-mix(in srgb, ${categoryColors.pink} 12%, var(--hb-surface))`, color: colorText(categoryColors.pink) },
    group: { bg: `color-mix(in srgb, ${categoryColors.royal} 12%, var(--hb-surface))`, color: colorText(categoryColors.royal) },
    event: { bg: `color-mix(in srgb, ${categoryColors.green} 12%, var(--hb-surface))`, color: colorText(categoryColors.green) },
    invoice: { bg: `color-mix(in srgb, ${categoryColors.orange} 12%, var(--hb-surface))`, color: colorText(categoryColors.orange) },
    poll: { bg: `color-mix(in srgb, ${categoryColors.red} 12%, var(--hb-surface))`, color: colorText(categoryColors.red) },
    post: { bg: `color-mix(in srgb, ${categoryColors.royal} 12%, var(--hb-surface))`, color: colorText(categoryColors.royal) },
    audit: { bg: `color-mix(in srgb, ${categoryColors.slate} 12%, var(--hb-surface))`, color: colorText(categoryColors.slate) },
    page: { bg: 'var(--hb-surface-2)', color: 'var(--hb-text-2)' },
  }
  for (const s of pluginSearches) if (s.color) kindColors[`${s.plugin}:${s.id}`] = s.color

  return (
    <Box
      ref={searchRef}
      className={fullWidth ? undefined : 'mantine-visible-from-sm'}
      style={{ position: 'relative', flexShrink: 0, flex: fullWidth ? 1 : undefined }}
    >
      <TextInput
        size="sm"
        w={fullWidth ? '100%' : 280}
        autoFocus={fullWidth}
        leftSection={
          <IconSearch
            size={16}
            style={{ color: 'var(--mantine-color-dimmed)' }}
          />
        }
        placeholder={t('shell.search.placeholder')}
        value={query}
        onChange={handleQueryChange}
        onFocus={() => {
          setUsed(true)
          if (results.length > 0) setDropOpen(true)
        }}
        ref={inputRef}
        rightSection={
          !query ? (
            <Kbd size="xs" style={{ whiteSpace: 'nowrap' }}>
              {/Mac|iPhone|iPad/.test(navigator.platform) ? '⌘K' : 'Ctrl K'}
            </Kbd>
          ) : undefined
        }
        rightSectionWidth={56}
        onKeyDown={(e) => {
          if (e.key === 'Escape') {
            setDropOpen(false)
            clearSearch()
            inputRef.current?.blur()
            onDone?.()
          } else if (e.key === 'ArrowDown' && results.length) {
            e.preventDefault()
            setDropOpen(true)
            setActive((i) => (i + 1) % results.length)
          } else if (e.key === 'ArrowUp' && results.length) {
            e.preventDefault()
            setActive((i) => (i - 1 + results.length) % results.length)
          } else if (e.key === 'Enter' && dropOpen && results[active]) {
            e.preventDefault()
            handleResultClick(results[active])
            inputRef.current?.blur()
          }
        }}
        styles={{ input: { height: 38 } }}
      />
      {dropOpen && results.length > 0 && (
        <Box
          style={{
            position: 'absolute',
            top: '110%',
            left: 0,
            width: fullWidth ? '100%' : 380,
            background: 'var(--hb-surface)',
            border: '1px solid var(--hb-border)',
            borderRadius: 10,
            boxShadow: '0 8px 24px rgba(0,0,0,.12)',
            zIndex: 800,
            overflow: 'hidden',
            padding: '8px 0',
          }}
        >
          {results.map((r, i) => (
            <Box
              key={`${r.kind}-${r.id}`}
              component="button"
              onClick={() => handleResultClick(r)}
              onMouseEnter={() => setActive(i)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: '12px 16px',
                width: '100%',
                textAlign: 'left',
                background: i === active ? 'var(--hb-surface-2)' : 'transparent',
                border: 'none',
                cursor: 'pointer',
                borderBottom: '1px solid var(--hb-border)',
              }}
            >
              <span
                style={{
                  fontSize: 'var(--mantine-font-size-xs)',
                  fontWeight: 600,
                  borderRadius: 4,
                  padding: '3px 7px',
                  flexShrink: 0,
                  background:
                    kindColors[r.kind]?.bg ?? 'var(--hb-surface-2)',
                  color:
                    kindColors[r.kind]?.color ?? 'var(--mantine-color-dimmed)',
                }}
              >
                {kindLabel[r.kind] ?? t(`shell.searchKind.${r.kind}`, r.kind)}
              </span>
              <Stack gap={0} style={{ flex: 1, minWidth: 0 }}>
                <Text
                  fz="md"
                  fw={500}
                  style={{
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {r.label}
                </Text>
                {r.sub && (
                  <Text
                    fz="sm"
                    c="dimmed"
                    mt={2}
                    style={{
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {r.sub}
                  </Text>
                )}
              </Stack>
            </Box>
          ))}
        </Box>
      )}
      {dropOpen && query.length >= 2 && results.length === 0 && (
        <Box
          style={{
            position: 'absolute',
            top: '110%',
            left: 0,
            width: 280,
            background: 'var(--hb-surface)',
            border: '1px solid var(--hb-border)',
            borderRadius: 10,
            boxShadow: '0 8px 24px rgba(0,0,0,.12)',
            zIndex: 800,
            padding: 16,
            textAlign: 'center',
            color: 'var(--mantine-color-dimmed)',
            fontSize: 'var(--mantine-font-size-sm)',
          }}
        >
          {t('shell.search.noResults', { query })}
        </Box>
      )}
    </Box>
  )
}
