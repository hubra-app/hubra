import {
  Text,
  Title,
  Group,
  Stack,
  Box,
  Paper,
  SimpleGrid,
  UnstyledButton,
  Select,
  Pagination as MantinePagination,
} from '@mantine/core'
import type { ReactNode } from 'react'

export function PageHead({
  eyebrow,
  title,
  desc,
  actions,
}: {
  eyebrow?: string
  title: string
  desc?: string
  actions?: ReactNode
}) {
  return (
    <Group
      justify="space-between"
      align="flex-start"
      gap={16}
      mb={24}
      wrap="wrap"
    >
      <Stack gap={4}>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <Title order={1} style={{ margin: 0 }}>
          {title}
        </Title>
        {desc && (
          <Text size="sm" c="dimmed" mt={4}>
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
  accent,
  onClick,
}: {
  label: string
  value: string | number
  sub?: string
  accent?: string
  onClick?: () => void
}) {
  return (
    <UnstyledButton onClick={onClick} style={{ display: 'block' }}>
      <Paper
        withBorder
        shadow="sm"
        radius="lg"
        p="lg"
        style={{ width: '100%' }}
      >
        <Text size="sm" fw={600} c="dimmed" mb={8}>
          {label}
        </Text>
        <Text
          className="num"
          fz={26}
          fw={700}
          lh={1}
          mb={4}
          c={accent || undefined}
        >
          {value}
        </Text>
        {sub && (
          <Text size="sm" c="dimmed">
            {sub}
          </Text>
        )}
      </Paper>
    </UnstyledButton>
  )
}

/* ── Card ───────────────────────────────────── */

export function Card({
  children,
  style,
}: {
  children: ReactNode
  style?: React.CSSProperties
}) {
  return (
    <Paper withBorder shadow="sm" radius="lg" style={style}>
      {children}
    </Paper>
  )
}

function CardHeader({
  title,
  children,
  style,
}: {
  title?: ReactNode
  children?: ReactNode
  style?: React.CSSProperties
}) {
  return (
    <Group
      justify="space-between"
      align="center"
      gap="sm"
      p="md"
      style={{
        borderBottom: '1px solid var(--mantine-color-gray-3)',
        ...style,
      }}
    >
      {title && (
        <Text fw={700} fz="md">
          {title}
        </Text>
      )}
      {children}
    </Group>
  )
}

Card.Header = CardHeader

/* ── StatGrid ───────────────────────────────── */

export function StatGrid({
  children,
  columns = 4,
  style,
}: {
  children: ReactNode
  columns?: number
  style?: React.CSSProperties
}) {
  return (
    <SimpleGrid
      cols={{ base: 1, xs: 2, md: columns }}
      spacing="md"
      mb={24}
      style={style}
    >
      {children}
    </SimpleGrid>
  )
}

/* ── CardGrid + CardItem ─────────────────────── */

export function CardGrid({
  children,
  columns = 3,
}: {
  children: ReactNode
  columns?: number
}) {
  return (
    <SimpleGrid cols={{ base: 1, xs: 2, md: columns }} spacing="md">
      {children}
    </SimpleGrid>
  )
}

export function CardItem({
  colorBar,
  icon,
  title,
  subtitle,
  children,
  footer,
  onClick,
}: {
  colorBar?: string
  icon?: ReactNode
  title: ReactNode
  subtitle?: ReactNode
  children?: ReactNode
  footer?: ReactNode
  onClick?: () => void
}) {
  return (
    <Paper
      withBorder
      shadow="sm"
      radius="lg"
      style={{ overflow: 'hidden', cursor: onClick ? 'pointer' : undefined }}
      onClick={onClick}
    >
      {colorBar && <div style={{ height: 4, background: colorBar }} />}
      <div style={{ padding: '18px 20px' }}>
        {(icon || title) && (
          <Group gap={10} mb={12} align="flex-start" wrap="nowrap">
            {icon && <Box style={{ flexShrink: 0 }}>{icon}</Box>}
            <Box style={{ minWidth: 0 }}>
              <Text fz="md" fw={700}>
                {title}
              </Text>
              {subtitle && (
                <Text fz="sm" c="dimmed">
                  {subtitle}
                </Text>
              )}
            </Box>
          </Group>
        )}
        {children}
        {footer && (
          <Box
            pt={12}
            mt={12}
            style={{
              borderTop: '1px solid var(--mantine-color-gray-3)',
            }}
          >
            {footer}
          </Box>
        )}
      </div>
    </Paper>
  )
}

/* ── Pagination ──────────────────────────────── */
const PER_PAGE_OPTS = [10, 25, 50, 100]

export function Pagination({
  page,
  perPage,
  total,
  totalPages,
  goPage,
  setPerPage,
  top,
}: {
  page: number
  perPage: number
  total: number
  totalPages: number
  goPage: (p: number) => void
  setPerPage: (n: number) => void
  top?: boolean
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
        data={PER_PAGE_OPTS.map((n) => ({
          value: String(n),
          label: String(n),
        }))}
        style={{ width: 80 }}
      />
      <Text size="sm" c="dimmed" flex={1}>
        {start}–{end} of {total}
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
