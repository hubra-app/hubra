import { useQuery } from '@tanstack/react-query'
import { Table, Paper, Group, Text, Button, SimpleGrid } from '@mantine/core'
import { useT } from '@/locales/i18n'
import { useNav } from '@/context/AppContext'
import { useInvoices } from '@/data/lists'
import { StatTile } from '@/components/ui'
import { getFinanceOverview, listTransactions } from '@/api/finance'
import { formatCHF, formatCHFWhole, formatDate } from '@/format'
import { qk } from '@/data/keys'
import { CategorySummaryCard } from './CategorySummaryCard'

/* ── Finance Overview ────────────────────────── */
export function FinanceOverviewTab() {
  const { go } = useNav()
  const { invoices } = useInvoices()
  const { t, i18n } = useT()
  const { data: overview } = useQuery({
    queryKey: qk.financeOverview,
    queryFn: () => getFinanceOverview(),
  })
  const { data: recentTx = [] } = useQuery({
    queryKey: qk.transactions.recent,
    queryFn: () => listTransactions({ pageSize: 5 }),
  })

  const months = overview?.months ?? []
  const maxVal = Math.max(...months.map((m) => m.inc + m.exp), 1)
  const openInvoiceCount = invoices.filter((i) => i.status !== 'Paid').length

  return (
    <div>


      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
          gap: 14,
          marginBottom: 24,
        }}
      >
        <StatTile
          label={t('finance.balance', 'Saldo')}
          value={
            overview ? formatCHFWhole(overview.balance) : '—'
          }
          sub={t('finance.asOfToday', 'Stand heute')}
        />
        <StatTile
          label={t('finance.incomeMtd', 'Einnahmen diesen Monat')}
          value={
            overview ? formatCHFWhole(overview.incomeMTD, true) : '—'
          }
          sub={t('dashboard.thisMonth', 'Diesen Monat')}
          accent="#1f9d57"
        />
        <StatTile
          label={t('finance.expensesMtd', 'Ausgaben diesen Monat')}
          value={
            overview ? formatCHFWhole(-Math.abs(overview.expensesMTD)) : '—'
          }
          sub={t('dashboard.thisMonth', 'Diesen Monat')}
          accent="#ff4d3d"
        />
        <StatTile
          label={t('finance.net', 'Netto')}
          value={
            overview ? formatCHFWhole(overview.netMTD, true) : '—'
          }
          sub={t('finance.incomeMinusExpenses', 'Einnahmen minus Ausgaben')}
          accent="var(--mantine-color-acc-7)"
        />
        <StatTile
          label={t('common.openInvoices', 'Offene Rechnungen')}
          value={String(openInvoiceCount)}
          sub={t('finance.awaitingPayment', 'Zahlung ausstehend')}
          accent={openInvoiceCount > 0 ? '#ff4d3d' : '#1f9d57'}
          onClick={() => go('/app/finance/invoices')}
        />
      </div>

      <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
        {/* Bar chart */}
        <Paper withBorder shadow="sm" radius="lg">
          <Group
            p="md"
            gap="sm"
            style={{ borderBottom: '1px solid var(--hb-border)' }}
          >
            <Text fw={700} fz="md">
              {t('finance.overview12month', 'Letzte 12 Monate')}
            </Text>
          </Group>
          <div style={{ padding: '20px 20px 16px' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'flex-end',
                gap: 6,
                height: 140,
              }}
            >
              {months.map((m) => {
                const inH = (m.inc / maxVal) * 120
                const exH = (m.exp / maxVal) * 120
                return (
                  <div
                    key={m.m}
                    style={{
                      flex: 1,
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      gap: 2,
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        gap: 1,
                        width: '100%',
                        justifyContent: 'flex-end',
                        height: 120,
                      }}
                    >
                      <div
                        style={{
                          width: '100%',
                          background: '#1f9d57',
                          borderRadius: '3px 3px 0 0',
                          height: inH,
                          opacity: 0.85,
                        }}
                      />
                      <div
                        style={{
                          width: '100%',
                          background: '#ff4d3d',
                          borderRadius: 0,
                          height: exH,
                          opacity: 0.7,
                          marginTop: 1,
                        }}
                      />
                    </div>
                    <div
                      style={{
                        fontSize: 10,
                        color: 'var(--hb-text-3)',
                        marginTop: 4,
                      }}
                    >
                      {m.month
                        ? new Date(m.year ?? 2000, m.month - 1, 1).toLocaleString(
                            i18n.language,
                            { month: 'short' },
                          )
                        : m.m}
                    </div>
                  </div>
                )
              })}
            </div>
            <div style={{ display: 'flex', gap: 16, marginTop: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: 2,
                    background: '#1f9d57',
                  }}
                />
                <span
                  style={{
                    fontSize: 'var(--mantine-font-size-xs)',
                    color: 'var(--hb-text-2)',
                  }}
                >
                  {t('finance.income', 'Einnahmen')}
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: 2,
                    background: '#ff4d3d',
                  }}
                />
                <span
                  style={{
                    fontSize: 'var(--mantine-font-size-xs)',
                    color: 'var(--hb-text-2)',
                  }}
                >
                  {t('finance.expenses', 'Ausgaben')}
                </span>
              </div>
            </div>
          </div>
        </Paper>

        {/* Recent transactions */}
        <Paper withBorder shadow="sm" radius="lg">
          <Group
            p="md"
            gap="sm"
            style={{ borderBottom: '1px solid var(--hb-border)' }}
          >
            <Text fw={700} fz="md">
              {t('finance.recentTransactions', 'Letzte Buchungen')}
            </Text>
            <Button
              size="sm"
              variant="subtle"
              style={{ marginLeft: 'auto', color: 'var(--mantine-color-acc-7)' }}
              onClick={() => go('/app/finance/transactions')}
            >
              {t('finance.viewAll', 'Alle ansehen')}
            </Button>
          </Group>
          <div style={{ overflowX: 'auto' }}>
            <Table highlightOnHover className="responsive-table">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{t('common.description', 'Beschreibung')}</Table.Th>
                  <Table.Th>{t('finance.amount', 'Betrag')}</Table.Th>
                  <Table.Th>{t('common.date', 'Datum')}</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {recentTx.length === 0 ? (
                  <Table.Tr>
                    <Table.Td
                      colSpan={3}
                      style={{
                        textAlign: 'center',
                        color: 'var(--hb-text-3)',
                        padding: '24px',
                        fontSize: 'var(--mantine-font-size-sm)',
                      }}
                    >
                      {t('finance.noTransactions', 'Keine Buchungen gefunden.')}
                    </Table.Td>
                  </Table.Tr>
                ) : (
                  recentTx.map((tx) => (
                    <Table.Tr
                      key={tx.id}
                      onClick={() => go(`/app/finance/transactions?tx=${tx.id}`)}
                      style={{ cursor: 'pointer' }}
                    >
                      <Table.Td
                        data-label={t('finance.description', 'Beschreibung')}
                        style={{ maxWidth: 200 }}
                      >
                        <div
                          style={{
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {tx.description}
                        </div>
                        <div
                          style={{
                            fontSize: 'var(--mantine-font-size-xs)',
                            color: 'var(--hb-text-3)',
                          }}
                        >
                          {tx.category}
                        </div>
                      </Table.Td>
                      <Table.Td data-label={t('finance.amount', 'Betrag')}>
                        <span
                          className="num"
                          style={{
                            fontWeight: 700,
                            color: tx.type === 'income' ? '#1f9d57' : '#ff4d3d',
                          }}
                        >
                          {tx.type === 'income' ? '+' : ''}CHF{' '}
                          {formatCHF(Math.abs(tx.amount))}
                        </span>
                      </Table.Td>
                      <Table.Td data-label={t('finance.date', 'Datum')}>
                        <span
                          className="num"
                          style={{
                            color: 'var(--hb-text-2)',
                            fontSize: 'var(--mantine-font-size-xs)',
                          }}
                        >
                          {formatDate(tx.date)}
                        </span>
                      </Table.Td>
                    </Table.Tr>
                  ))
                )}
              </Table.Tbody>
            </Table>
          </div>
        </Paper>
      </SimpleGrid>

      <CategorySummaryCard />
    </div>
  )
}
