import { Text, Group, Box, Paper } from '@mantine/core'
import type { ComponentProps, ReactNode } from 'react'
import { Pagination as SharedPagination } from '@hubra/ui'
import { useT } from '@/locales/i18n'
import { clickableProps } from './hooks'
export { PageHead, StatGrid, StatTile } from '@hubra/ui'

export { Card, CardGrid } from '@hubra/ui'

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
              borderTop: '1px solid var(--hb-border)',
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

export function Pagination(props: ComponentProps<typeof SharedPagination>) {
  const { t } = useT()
  return (
    <SharedPagination
      rangeLabel={(start, end, total) =>
        t('common.rangeOf', '{{start}}–{{end}} von {{total}}', { start, end, total })
      }
      labels={{
        perPage: t('common.perPage', 'Einträge pro Seite'),
        first: t('common.pageFirst', 'Erste Seite'),
        previous: t('common.pagePrevious', 'Vorherige Seite'),
        next: t('common.pageNext', 'Nächste Seite'),
        last: t('common.pageLast', 'Letzte Seite'),
      }}
      {...props}
    />
  )
}
