import type { CSSProperties, ReactNode } from 'react'
import {
  Box,
  Group,
  Pagination as MantinePagination,
  Paper,
  Select,
  SimpleGrid,
  Stack,
  Tabs as MantineTabs,
  Text,
  Title,
  UnstyledButton,
} from '@mantine/core'

// Page building blocks the three apps share. Their styles are in ui.css.

export function PageHead({
  eyebrow,
  title,
  desc,
  actions,
  back,
}: {
  /** A small line above the title. */
  eyebrow?: ReactNode
  title: ReactNode
  desc?: ReactNode
  actions?: ReactNode
  back?: ReactNode
}) {
  return (
    <Box mb={24}>
      {back && <Box mb={12}>{back}</Box>}
      <Group justify="space-between" align="flex-end" gap={16} wrap="wrap">
        <Stack gap={6} style={{ minWidth: 0, flex: '1 1 320px' }}>
          {eyebrow && <div className="eyebrow">{eyebrow}</div>}
          <Title order={1} style={{ margin: 0, overflowWrap: 'anywhere' }}>
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
    </Box>
  )
}

export function StatTile({
  label,
  value,
  sub,
  accent,
  icon,
  onClick,
}: {
  label: string
  value: string | number
  sub?: string
  accent?: string
  icon?: ReactNode
  onClick?: () => void
}) {
  const body = (
    <Paper withBorder p="lg" style={{ width: '100%', height: '100%' }}>
      <Group justify="space-between" align="flex-start" wrap="nowrap" mb={10}>
        <Text size="sm" fw={600} c="dimmed">
          {label}
        </Text>
        {icon && (
          <Box c="acc.6" style={{ lineHeight: 0 }}>
            {icon}
          </Box>
        )}
      </Group>
      <Text
        className="stat-value"
        fz={28}
        fw={700}
        lh={1.1}
        c={accent || 'var(--mantine-color-black)'}
      >
        {value}
      </Text>
      {sub && (
        <Text size="sm" c="dimmed" mt={6}>
          {sub}
        </Text>
      )}
    </Paper>
  )
  if (!onClick) return body
  return (
    <UnstyledButton onClick={onClick} style={{ display: 'block', height: '100%' }}>
      {body}
    </UnstyledButton>
  )
}

export function StatGrid({
  children,
  columns = 4,
  style,
}: {
  children: ReactNode
  columns?: number
  style?: CSSProperties
}) {
  return (
    <SimpleGrid cols={{ base: 1, xs: 2, md: columns }} spacing="md" mb={24} style={style}>
      {children}
    </SimpleGrid>
  )
}

export interface TabDef {
  id: string
  label: string
  icon?: ReactNode
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
    <MantineTabs
      value={activeTab}
      onChange={(v) => v && onTabChange(v)}
      mb={24}
      variant="default"
      className="hubra-tabs"
      styles={{
        tab: {
          paddingTop: 12,
          paddingBottom: 12,
          paddingLeft: 14,
          paddingRight: 14,
          fontSize: 'var(--mantine-font-size-sm)',
        },
        list: {
          gap: 4,
        },
      }}
    >
      <MantineTabs.List>
        {tabs.map((t) => (
          <MantineTabs.Tab key={t.id} value={t.id} leftSection={t.icon}>
            {t.label}
          </MantineTabs.Tab>
        ))}
      </MantineTabs.List>
    </MantineTabs>
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
  top,
  rangeLabel = (start, end, total) => `${start}–${end} von ${total}`,
}: {
  page: number
  perPage: number
  total: number
  totalPages: number
  goPage: (p: number) => void
  setPerPage: (n: number) => void
  top?: boolean
  /** The "1–25 of 80" text; German unless the app passes its own. */
  rangeLabel?: (start: number, end: number, total: number) => ReactNode
}) {
  if (total === 0) return null
  const start = (page - 1) * perPage + 1
  const end = Math.min(page * perPage, total)

  return (
    <Group
      gap="xs"
      px="md"
      py="xs"
      style={{
        borderTop: top ? 'none' : '1px solid var(--mantine-color-gray-3)',
        borderBottom: top ? '1px solid var(--mantine-color-gray-3)' : 'none',
        flexWrap: 'wrap',
      }}
    >
      <Select
        size="sm"
        value={String(perPage)}
        onChange={(v) => setPerPage(Number(v))}
        // A screen may page by another size (cards in rows of 3 use 12).
        data={[...new Set([...PER_PAGE_OPTS, perPage])]
          .sort((a, b) => a - b)
          .map((n) => ({
            value: String(n),
            label: String(n),
          }))}
        style={{ width: 80 }}
      />
      <Text size="sm" c="dimmed" flex={1}>
        {rangeLabel(start, end, total)}
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
