import type { ReactNode } from 'react'
import { Title, Text, Group, Stack, SimpleGrid, Paper, UnstyledButton } from '@mantine/core'
import { Select, Pagination as MantinePagination } from '@mantine/core'
import { tr } from '@/lang'

export function PageHead({
  eyebrow,
  title,
  desc,
  actions,
}: {
  eyebrow?: string
  title: ReactNode
  desc?: ReactNode
  actions?: ReactNode
}) {
  return (
    <Group justify="space-between" align="flex-end" gap={16} mb={28} wrap="wrap">
      <Stack gap={6}>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <Title order={1} style={{ margin: 0 }}>
          {title}
        </Title>
        {desc && (
          <Text size="md" c="dimmed" maw={720}>
            {desc}
          </Text>
        )}
      </Stack>
      {actions && (
        <Group gap="xs" wrap="wrap" align="center">
          {actions}
        </Group>
      )}
    </Group>
  )
}

export function StatTile({
  label,
  value,
  sub,
}: {
  label: string
  value: string | number
  sub?: string
}) {
  return (
    <Paper withBorder p="lg">
      <Text size="sm" fw={600} c="dimmed" mb={8}>
        {label}
      </Text>
      <Text className="num" fz={28} fw={600} lh={1} mb={4}>
        {value}
      </Text>
      {sub && <Text size="sm" c="dimmed">{sub}</Text>}
    </Paper>
  )
}

export function StatGrid({
  children,
  columns = 4,
}: {
  children: ReactNode
  columns?: number
}) {
  return (
    <SimpleGrid cols={{ base: 2, md: columns }} spacing="md" mb={24}>
      {children}
    </SimpleGrid>
  )
}

export interface TabDef {
  id: string
  label: string
}

export function Tabs({
  tabs,
  activeTab,
  onTabChange,
}: {
  tabs: TabDef[]
  activeTab: string
  onTabChange: (id: string) => void
}) {
  return (
    <Group gap={4} mb={20} wrap="wrap">
      {tabs.map((tab) => (
        <UnstyledButton
          key={tab.id}
          onClick={() => onTabChange(tab.id)}
          px={14}
          py={8}
          fw={tab.id === activeTab ? 700 : 400}
          c={tab.id === activeTab ? '#1a1625' : 'dimmed'}
          style={{
            borderRadius: 8,
            background: tab.id === activeTab ? 'rgba(116,65,224,0.15)' : 'transparent',
          }}
        >
          {tab.label}
        </UnstyledButton>
      ))}
    </Group>
  )
}

const PER_PAGE_OPTS = [10, 25, 50, 100]

export function Pagination({
  page,
  perPage,
  total,
  totalPages,
  goPage,
  setPerPage,
}: {
  page: number
  perPage: number
  total: number
  totalPages: number
  goPage: (p: number) => void
  setPerPage: (n: number) => void
}) {
  if (total === 0) return null
  const start = (page - 1) * perPage + 1
  const end = Math.min(page * perPage, total)
  return (
    <Group gap="xs" px="md" py="xs" wrap="wrap">
      <Select
        size="sm"
        value={String(perPage)}
        onChange={(v) => setPerPage(Number(v))}
        data={PER_PAGE_OPTS.map((n) => ({ value: String(n), label: String(n) }))}
        style={{ width: 80 }}
      />
      <Text size="sm" c="dimmed" flex={1}>
        {start}–{end} {tr('von', 'of')} {total}
      </Text>
      <MantinePagination
        value={page}
        onChange={goPage}
        total={totalPages}
        size="sm"
        withEdges
        boundaries={1}
      />
    </Group>
  )
}
