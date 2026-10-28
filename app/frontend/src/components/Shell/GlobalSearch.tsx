import { useState, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { TextInput, Box, Text, Stack } from '@mantine/core'
import { IconSearch } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useNav, useApp } from '@/context/AppContext'
import { useEvents, useInvoices, usePolls } from '@/data/lists'
import { listMembers } from '@/api/members'
import { listGroups } from '@/api/groups'
import { listTransactions } from '@/api/finance'
import { listInventory } from '@/api/inventory'
import { listAuditLog } from '@/api/settings'
import type { SearchResult } from './nav'

export function GlobalSearch() {
  const { t } = useT()
  const { go } = useNav()
  // A switched-off module answers 403: only search what is on.
  const { modules, hasPermission } = useApp()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [dropOpen, setDropOpen] = useState(false)
  // Load what the search looks through only once someone uses it.
  const [used, setUsed] = useState(false)
  const { events } = useEvents({ enabled: used })
  const { polls } = usePolls({ enabled: used })
  const { invoices } = useInvoices({ enabled: used })
  const searchRef = useRef<HTMLDivElement>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const { data: memberResp } = useQuery({
    queryKey: ['search-members'],
    enabled: used && modules.members === true,
    queryFn: () => listMembers({ pageSize: 200 }),
    staleTime: 60_000,
  })
  const { data: groupList = [] } = useQuery({
    queryKey: ['search-groups'],
    enabled: used && modules.groups === true,
    queryFn: () => listGroups(),
    staleTime: 60_000,
  })
  const { data: txList = [] } = useQuery({
    queryKey: ['search-transactions'],
    enabled: used && modules.finance === true && hasPermission('finance.transactions.read'),
    queryFn: () => listTransactions({ pageSize: 200 }),
    staleTime: 60_000,
  })
  const { data: inventoryList = [] } = useQuery({
    queryKey: ['search-inventory'],
    enabled: used && modules.inventory === true,
    queryFn: () => listInventory(),
    staleTime: 60_000,
  })
  const { data: auditPage } = useQuery({
    queryKey: ['search-audit'],
    enabled: used && hasPermission('audit.audit.read'),
    queryFn: () => listAuditLog({ pageSize: 200 }),
    staleTime: 60_000,
  })

  const runSearch = (q: string) => {
    if (q.length < 2) {
      setResults([])
      setDropOpen(false)
      return
    }
    const lower = q.toLowerCase()

    const evResults: SearchResult[] = events
      .filter((ev) => ev.title.toLowerCase().includes(lower))
      .slice(0, 3)
      .map((ev) => ({
        kind: 'event',
        id: ev.id,
        label: ev.title,
        sub: ev.date,
        path: '/app/operations/events',
      }))
    const pollResults: SearchResult[] = polls
      .filter((p) => p.question.toLowerCase().includes(lower))
      .slice(0, 3)
      .map((p) => ({
        kind: 'poll',
        id: p.id,
        label: p.question,
        sub: p.status === 'open' ? t('shell.search.pollOpen', 'Offen') : t('shell.search.pollClosed', 'Geschlossen'),
        path: '/app/operations/polls',
      }))
    const invoiceResults: SearchResult[] = invoices
      .filter(
        (inv) =>
          inv.member.toLowerCase().includes(lower) ||
          inv.description?.toLowerCase().includes(lower) ||
          inv.status.toLowerCase().includes(lower),
      )
      .slice(0, 3)
      .map((inv) => ({
        kind: 'invoice',
        id: inv.id,
        label: t('shell.search.invoice', 'Rechnung {{id}} – {{member}}', { id: inv.id, member: inv.member }),
        sub: `${t(`status.${inv.status}`, inv.status)} · CHF ${inv.amount}`,
        path: '/app/finance/invoices',
      }))

    const mResults: SearchResult[] = (memberResp?.members ?? [])
      .filter(
        (m) =>
          m.name.toLowerCase().includes(lower) ||
          m.email?.toLowerCase().includes(lower),
      )
      .slice(0, 3)
      .map((m) => ({
        kind: 'member',
        id: m.id,
        label: m.name,
        sub: m.tier,
        path: '/app/members',
      }))
    const gResults: SearchResult[] = groupList
      .filter((g) => g.name.toLowerCase().includes(lower))
      .slice(0, 3)
      .map((g) => ({
        kind: 'group',
        id: g.id,
        label: g.name,
        sub: g.description || undefined,
        path: '/app/groups',
      }))
    const txResults: SearchResult[] = txList
      .filter(
        (tx) =>
          tx.description.toLowerCase().includes(lower) ||
          tx.member.toLowerCase().includes(lower) ||
          tx.category?.toLowerCase().includes(lower),
      )
      .slice(0, 3)
      .map((tx) => ({
        kind: 'transaction',
        id: tx.id,
        label: tx.description,
        sub: `${tx.type} · CHF ${tx.amount}`,
        path: '/app/finance/transactions',
      }))
    const inventoryResults: SearchResult[] = inventoryList
      .filter(
        (item) =>
          item.name.toLowerCase().includes(lower) ||
          item.description?.toLowerCase().includes(lower) ||
          item.category.toLowerCase().includes(lower),
      )
      .slice(0, 3)
      .map((item) => ({
        kind: 'inventory',
        id: item.id,
        label: item.name,
        sub: item.category,
        path: '/app/inventory',
      }))
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
        path: '/app/audit-log',
      }))

    setResults([
      ...mResults,
      ...gResults,
      ...evResults,
      ...pollResults,
      ...invoiceResults,
      ...txResults,
      ...inventoryResults,
      ...auditResults,
    ])
    setDropOpen(true)
  }

  const handleQueryChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const q = e.target.value
    setQuery(q)
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => runSearch(q), 200)
  }

  const handleResultClick = (r: SearchResult) => {
    go(r.path)
    setQuery('')
    setResults([])
    setDropOpen(false)
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
    transaction: t('shell.searchKind.transaction'),
    inventory: t('shell.searchKind.inventory'),
    poll: t('shell.searchKind.poll'),
    audit: t('shell.searchKind.audit'),
  }
  const kindColors: Record<string, { bg: string; color: string }> = {
    member: { bg: '#fdf0f8', color: '#be185d' },
    group: { bg: '#eff6ff', color: '#1d4ed8' },
    event: { bg: '#f0fdf4', color: '#15803d' },
    invoice: { bg: '#f5f1ff', color: '#b45309' },
    transaction: { bg: '#f0fdfa', color: '#0f766e' },
    inventory: { bg: '#eef2ff', color: '#4338ca' },
    poll: { bg: '#fff7ed', color: '#c2410c' },
    audit: { bg: '#f1f5f9', color: '#475569' },
  }

  return (
    <Box
      ref={searchRef}
      className="mantine-visible-from-sm"
      style={{ position: 'relative', flexShrink: 0 }}
    >
      <TextInput
        size="sm"
        w={280}
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
        onKeyDown={(e) => {
          if (e.key === 'Escape') {
            setDropOpen(false)
            setQuery('')
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
            width: 380,
            background: 'var(--mantine-color-white)',
            border: '1px solid var(--mantine-color-gray-3)',
            borderRadius: 10,
            boxShadow: '0 8px 24px rgba(0,0,0,.12)',
            zIndex: 800,
            overflow: 'hidden',
            padding: '8px 0',
          }}
        >
          {results.map((r) => (
            <Box
              key={`${r.kind}-${r.id}`}
              component="button"
              onClick={() => handleResultClick(r)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: '12px 16px',
                width: '100%',
                textAlign: 'left',
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                borderBottom: '1px solid var(--mantine-color-gray-2)',
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
                    kindColors[r.kind]?.bg ?? 'var(--mantine-color-gray-1)',
                  color:
                    kindColors[r.kind]?.color ?? 'var(--mantine-color-dimmed)',
                }}
              >
                {kindLabel[r.kind]}
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
            background: 'var(--mantine-color-white)',
            border: '1px solid var(--mantine-color-gray-3)',
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
