import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Table, Paper, Group, Text, Select } from '@mantine/core'
import { useT } from '@/locales/i18n'
import { getFinanceSummary } from '@/api/finance'
import { formatCHF } from '@/format'
import { qk } from '@/data/keys'

/* ── Income and expenses per category, for one year ── */
export function CategorySummaryCard() {
  const { t } = useT()
  const thisYear = new Date().getFullYear()
  const [year, setYear] = useState(thisYear)
  const { data } = useQuery({
    queryKey: qk.financeSummary(year),
    queryFn: () => getFinanceSummary(`${year}-01-01`, `${year}-12-31`),
  })
  const rows = data?.categories ?? []
  const largest = Math.max(...rows.map((c) => Math.max(c.income, c.expense)), 1)
  const years = Array.from({ length: 6 }, (_, i) => String(thisYear - i))

  return (
    <Paper withBorder shadow="sm" radius="lg" mt="md">
      <Group p="md" gap="sm" style={{ borderBottom: '1px solid var(--hb-border)' }}>
        <Text fw={700} fz="md">
          {t('finance.summary.title', 'Nach Kategorie')}
        </Text>
        <Select
          size="xs"
          w={100}
          ml="auto"
          data={years}
          value={String(year)}
          onChange={(v) => v && setYear(Number(v))}
          allowDeselect={false}
          aria-label={t('finance.summary.year', 'Jahr')}
        />
      </Group>
      <div style={{ overflowX: 'auto' }}>
        <Table className="responsive-table">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{t('finance.summary.category', 'Kategorie')}</Table.Th>
              <Table.Th style={{ textAlign: 'right' }}>
                {t('finance.income', 'Einnahmen')}
              </Table.Th>
              <Table.Th style={{ textAlign: 'right' }}>
                {t('finance.expenses', 'Ausgaben')}
              </Table.Th>
              <Table.Th style={{ textAlign: 'right' }}>{t('finance.net', 'Netto')}</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {rows.length === 0 ? (
              <Table.Tr>
                <Table.Td
                  colSpan={4}
                  style={{
                    textAlign: 'center',
                    color: 'var(--hb-text-3)',
                    padding: 24,
                    fontSize: 'var(--mantine-font-size-sm)',
                  }}
                >
                  {t('finance.noTransactions', 'Keine Buchungen gefunden.')}
                </Table.Td>
              </Table.Tr>
            ) : (
              rows.map((c) => (
                <Table.Tr key={c.id ?? 'none'}>
                  <Table.Td data-label={t('finance.summary.category', 'Kategorie')}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span
                        style={{
                          width: 10,
                          height: 10,
                          borderRadius: 3,
                          flexShrink: 0,
                          background: c.color ?? 'var(--hb-text-3)',
                        }}
                      />
                      <span>
                        {c.name ?? t('finance.summary.uncategorized', 'Ohne Kategorie')}
                      </span>
                      <span style={{ color: 'var(--hb-text-3)', fontSize: 'var(--mantine-font-size-xs)' }}>
                        {c.count}
                      </span>
                    </div>
                    <div style={{ display: 'flex', gap: 2, marginTop: 4, height: 4 }}>
                      <div
                        style={{
                          width: `${(c.income / largest) * 50}%`,
                          background: '#1f9d57',
                          borderRadius: 2,
                        }}
                      />
                      <div
                        style={{
                          width: `${(c.expense / largest) * 50}%`,
                          background: '#ff4d3d',
                          borderRadius: 2,
                        }}
                      />
                    </div>
                  </Table.Td>
                  <Table.Td data-label={t('finance.income', 'Einnahmen')} style={{ textAlign: 'right' }}>
                    <span className="num">{c.income ? formatCHF(c.income) : '–'}</span>
                  </Table.Td>
                  <Table.Td data-label={t('finance.expenses', 'Ausgaben')} style={{ textAlign: 'right' }}>
                    <span className="num">{c.expense ? formatCHF(c.expense) : '–'}</span>
                  </Table.Td>
                  <Table.Td data-label={t('finance.net', 'Netto')} style={{ textAlign: 'right' }}>
                    <span
                      className="num"
                      style={{ fontWeight: 700, color: c.net < 0 ? '#ff4d3d' : '#1f9d57' }}
                    >
                      {formatCHF(c.net)}
                    </span>
                  </Table.Td>
                </Table.Tr>
              ))
            )}
          </Table.Tbody>
          {data && rows.length > 0 && (
            <Table.Tfoot>
              <Table.Tr style={{ fontWeight: 700 }}>
                <Table.Td>{t('finance.summary.total', 'Total')}</Table.Td>
                <Table.Td style={{ textAlign: 'right' }}>
                  <span className="num">{formatCHF(data.income)}</span>
                </Table.Td>
                <Table.Td style={{ textAlign: 'right' }}>
                  <span className="num">{formatCHF(data.expense)}</span>
                </Table.Td>
                <Table.Td style={{ textAlign: 'right' }}>
                  <span className="num">{formatCHF(data.net)}</span>
                </Table.Td>
              </Table.Tr>
            </Table.Tfoot>
          )}
        </Table>
      </div>
    </Paper>
  )
}
