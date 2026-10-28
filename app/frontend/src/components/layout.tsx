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
import { useT } from '@/locales/i18n'
import { clickableProps } from './hooks'

export function PageHead({
  title,
  desc,
  actions,
  back,
}: {
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
        {icon && <Box c="acc.6" style={{ lineHeight: 0 }}>{icon}</Box>}
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

/* ── Card ───────────────────────────────────── */

export function Card({
  children,
  style,
}: {
  children: ReactNode
  style?: React.CSSProperties
}) {
  return (
    <Paper withBorder style={{ overflow: 'hidden', ...style }}>
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
      px="lg"
      py="md"
      wrap="wrap"
      style={{
        borderBottom: '1px solid var(--mantine-color-gray-3)',
        ...style,
      }}
    >
      {title && (
        <Text fw={700} fz="md" ff="heading">
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
      style={{ overflow: 'hidden', cursor: onClick ? 'pointer' : undefined }}
      {...clickableProps(onClick)}
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
  const { t } = useT()
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
        {t('common.rangeOf', '{{start}}–{{end}} von {{total}}', { start, end, total })}
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
