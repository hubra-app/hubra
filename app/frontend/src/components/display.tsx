import { useState, useEffect } from 'react'
import i18n from 'i18next'
import {
  Avatar as MantineAvatar,
  Badge,
  Text,
  Group,
  Box,
  Indicator,
  TextInput,
  UnstyledButton,
  Button,
} from '@mantine/core'

import { IconSearch, IconPlus, IconX } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import type { ReactNode } from 'react'
import { SlideOver, LoadingSpinner, EmptyState } from './feedback'
import { Pagination } from './layout'
import { usePagination } from './hooks'

function avatarContrast(hex: string): string {
  const h = hex.replace('#', '')
  const r = parseInt(h.substring(0, 2), 16)
  const g = parseInt(h.substring(2, 4), 16)
  const b = parseInt(h.substring(4, 6), 16)
  return 0.2126 * r + 0.7152 * g + 0.0722 * b > 140
    ? 'var(--mantine-color-ink-8)'
    : '#ffffff'
}

function statusDotColor(lastSeen: string): string {
  if (!lastSeen) return ''
  const diff = Date.now() - new Date(lastSeen).getTime()
  const min = Math.floor(diff / 60000)
  if (min < 15) return '#22c55e'
  if (min < 60) return '#f59e0b'
  return '#ef4444'
}

export function Avatar({
  name,
  color,
  size = 32,
  lastSeen,
}: {
  name: string
  color: string
  size?: number
  lastSeen?: string
}) {
  const initials = name
    .split(' ')
    .map((w: string) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()
  const dotColor = lastSeen ? statusDotColor(lastSeen) : undefined

  if (dotColor) {
    return (
      <Indicator inline size={10} offset={-1} color={dotColor} withBorder>
        <MantineAvatar
          size={size}
          radius="xl"
          color={color}
          styles={{
            root: { backgroundColor: color, color: avatarContrast(color) },
            placeholder: { color: avatarContrast(color) },
          }}
        >
          {initials}
        </MantineAvatar>
      </Indicator>
    )
  }

  return (
    <MantineAvatar
      size={size}
      radius="xl"
      styles={{
        root: { backgroundColor: color, color: avatarContrast(color) },
        placeholder: { color: avatarContrast(color) },
      }}
    >
      {initials}
    </MantineAvatar>
  )
}

export function Tag({
  children,
  color,
}: {
  children: ReactNode
  color?: string
}) {
  return (
    <Badge
      variant="light"
      size="md"
      color={color || 'gray'}
      styles={
        color
          ? {
              root: {
                backgroundColor: color + '1a',
                color,
                borderColor: color + '66',
              },
            }
          : undefined
      }
    >
      {children}
    </Badge>
  )
}

const TIER_COLORS: Record<string, string> = {
  Maker: '#2596be',
  Pro: '#1f61d8',
  Student: '#fe64ac',
  Workshop: '#fece2b',
}
export function TierTag({ tier }: { tier: string }) {
  const c = TIER_COLORS[tier] || '#857f99'
  return <Tag color={c}>{tier}</Tag>
}

const STATUS_COLORS: Record<string, string> = {
  active: '#1f9d57',
  trial: '#c2870f',
  inactive: '#857f99',
  suspended: '#ff4d3d',
}
export function StatusBadge({ status }: { status: string }) {
  const c = STATUS_COLORS[status] || '#857f99'
  return (
    <Group gap={7} wrap="nowrap">
      <Box
        style={{
          width: 7,
          height: 7,
          borderRadius: '50%',
          backgroundColor: c,
          flexShrink: 0,
        }}
      />
      <Text size="sm" fw={600} c={c}>
        {i18n.t(`status.${status}`, status.charAt(0).toUpperCase() + status.slice(1))}
      </Text>
    </Group>
  )
}

export function InvoicePill({ status }: { status: string }) {
  const color =
    status === 'Paid' ? 'green' : status === 'Overdue' ? 'red' : 'yellow'
  return (
    <Badge variant="light" color={color} radius="xl" size="md">
      {i18n.t(`status.${status}`, status)}
    </Badge>
  )
}

function msAgo(ts: string): number {
  return Date.now() - new Date(ts).getTime()
}

export function LastSeenBadge({ lastSeen }: { lastSeen: string }) {
  if (!lastSeen)
    return (
      <Text size="sm" c="dimmed">
        —
      </Text>
    )

  const diff = msAgo(lastSeen)
  const min = Math.floor(diff / 60000)

  let label: string
  if (min < 1) label = i18n.t('time.justNow', 'Gerade eben')
  else if (min < 60) label = i18n.t('time.minutesAgo', 'vor {{n}} Min.', { n: min })
  else if (min < 1440) label = i18n.t('time.hoursAgo', 'vor {{n}} Std.', { n: Math.floor(min / 60) })
  else label = i18n.t('time.daysAgo', 'vor {{n}} Tagen', { n: Math.floor(min / 1440) })

  return (
    <Text size="sm" c="dimmed">
      {label}
    </Text>
  )
}

export interface SlideOverMember {
  id: string
  name: string
  email: string
  avatarColor: string
  tier?: string
}

export function MemberSlideOver({
  title,
  subtitle,
  icon,
  members,
  loading,
  addLabel,
  addPlaceholder,
  searchResults,
  onAdd,
  onAddSearch,
  onRemove,
  showRemove = false,
  onClose,
  footer,
}: {
  title: string
  subtitle?: string
  icon?: ReactNode
  members: SlideOverMember[]
  loading?: boolean
  addLabel?: string
  addPlaceholder?: string
  searchResults?: SlideOverMember[]
  onAdd?: (member: SlideOverMember) => void
  onAddSearch?: (query: string) => void
  onRemove?: (member: SlideOverMember) => void
  showRemove?: boolean
  onClose: () => void
  footer?: ReactNode
}) {
  const { t } = useT()
  const [search, setSearch] = useState('')
  const [addSearch, setAddSearch] = useState('')
  const pg = usePagination(members, 10)

  useEffect(() => {
    const timer = setTimeout(() => onAddSearch?.(addSearch), 250)
    return () => clearTimeout(timer)
  }, [addSearch, onAddSearch])

  return (
    <SlideOver title={title} subtitle={subtitle} icon={icon} onClose={onClose}>
      {onAdd && (
        <div
          style={{
            padding: '12px 0',
            borderBottom: '1px solid var(--hb-border)',
          }}
        >
          {addLabel && (
            <div
              style={{
                fontSize: 'var(--mantine-font-size-xs)',
                fontWeight: 600,
                color: 'var(--mantine-color-ink-4)',
                marginBottom: 6,
                textTransform: 'uppercase',
              }}
            >
              {addLabel}
            </div>
          )}
          <div style={{ position: 'relative' }}>
            <TextInput
              size="sm"
              style={{ paddingLeft: 32 }}
              placeholder={addPlaceholder ?? t('common.search', 'Suchen')}
              value={addSearch}
              onChange={(e) => setAddSearch(e.target.value)}
            />
            <IconSearch
              size={14}
              style={{
                position: 'absolute',
                left: 10,
                top: '50%',
                transform: 'translateY(-50%)',
                color: 'var(--mantine-color-ink-3)',
              }}
            />
          </div>
          {searchResults && searchResults.length > 0 && (
            <div
              style={{
                marginTop: 4,
                border: '1px solid var(--hb-border)',
                borderRadius: 8,
                overflow: 'hidden',
                background: 'var(--hb-surface)',
              }}
            >
              {searchResults.slice(0, 6).map((m) => (
                <UnstyledButton
                  key={m.id}
                  onClick={() => {
                    onAdd(m)
                    setAddSearch('')
                  }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    width: '100%',
                    padding: '8px 12px',
                    borderBottom: '1px solid var(--hb-border)',
                  }}
                >
                  <Avatar name={m.name} color={m.avatarColor} size={24} />
                  <div style={{ textAlign: 'left', flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        fontSize: 'var(--mantine-font-size-sm)',
                        fontWeight: 600,
                        color: 'var(--mantine-color-ink-8)',
                      }}
                    >
                      {m.name}
                    </div>
                    <div
                      style={{
                        fontSize: 'var(--mantine-font-size-xs)',
                        color: 'var(--mantine-color-ink-4)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {m.email}
                    </div>
                  </div>
                  <IconPlus size={14} color="#1f9d57" />
                </UnstyledButton>
              ))}
            </div>
          )}
        </div>
      )}

      <div style={{ flex: 1, overflowY: 'auto' }}>
        {loading ? (
          <LoadingSpinner message={t('common.loading', 'Wird geladen …')} />
        ) : members.length === 0 ? (
          <EmptyState
            title={
              search
                ? t('common.noResults', 'Keine Ergebnisse.')
                : t('common.empty', 'Nicht verfügbar.')
            }
          />
        ) : (
          pg.paged.map((m) => (
            <div
              key={m.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: '12px 0',
                borderBottom: '1px solid var(--hb-border)',
              }}
            >
              <Avatar name={m.name} color={m.avatarColor} size={32} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontSize: 'var(--mantine-font-size-sm)',
                    fontWeight: 600,
                    color: 'var(--mantine-color-ink-8)',
                  }}
                >
                  {m.name}
                </div>
                <div
                  style={{
                    fontSize: 'var(--mantine-font-size-xs)',
                    color: 'var(--mantine-color-ink-4)',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {m.email}
                </div>
              </div>
              {m.tier && <TierTag tier={m.tier} />}
              {showRemove && onRemove && (
                <Button
                  size="sm"
                  variant="subtle"
                  style={{ color: 'var(--mantine-color-red-6)', flexShrink: 0 }}
                  onClick={() => onRemove(m)}
                >
                  <IconX size={13} />
                </Button>
              )}
            </div>
          ))
        )}
      </div>

      <div style={{ borderTop: '1px solid var(--hb-border)' }}>
        <div style={{ padding: '12px 0', position: 'relative' }}>
          <TextInput
            size="sm"
            style={{ paddingLeft: 32 }}
            placeholder={t('common.filter', 'Filter')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <IconSearch
            size={14}
            style={{
              position: 'absolute',
              left: 10,
              top: '50%',
              transform: 'translateY(-50%)',
              color: 'var(--mantine-color-ink-3)',
            }}
          />
        </div>
        {members.length > 0 && (
          <Pagination
            page={pg.page}
            perPage={pg.perPage}
            total={pg.total}
            totalPages={pg.totalPages}
            goPage={pg.goPage}
            setPerPage={pg.setPerPage}
          />
        )}
        <div
          style={{
            padding: '8px 0',
            fontSize: 'var(--mantine-font-size-xs)',
            color: 'var(--mantine-color-ink-3)',
          }}
        >
          {members.length} {t('common.members', 'Mitglieder')}
        </div>
      </div>

      {footer}
    </SlideOver>
  )
}
