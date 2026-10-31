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
  ActionIcon,
} from '@mantine/core'

import { IconSearch, IconPlus, IconX } from '@tabler/icons-react'
import { textOn } from '@hubra/ui'
import { useT } from '@/locales/i18n'
import type { ReactNode } from 'react'
import { SlideOver, PanelSection, LoadingSpinner } from './feedback'
import { Pagination } from './layout'
import { usePagination } from './hooks'

// Fixed ink, not a theme token: the avatar colour is the same in dark mode,
// where the text tokens turn light.
const avatarContrast = (color: string) => textOn(color)

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

/** One member line in a side panel: avatar, name, a second line and
 * whatever goes at the end (a tag, a remove button). */
export function PanelMemberRow({
  name,
  detail,
  avatarColor,
  right,
}: {
  name: string
  detail?: ReactNode
  avatarColor?: string
  right?: ReactNode
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '10px 0',
        borderBottom: '1px solid var(--hb-border)',
      }}
    >
      <Avatar name={name} color={avatarColor ?? '#857f99'} size={32} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <Text fz="sm" fw={600} truncate style={{ color: 'var(--hb-text)' }}>
          {name}
        </Text>
        {detail && (
          <Text fz="xs" truncate style={{ color: 'var(--hb-text-3)' }}>
            {detail}
          </Text>
        )}
      </div>
      {right}
    </div>
  )
}

/** A member search field whose matches can be picked from a list below it. */
export function MemberAddSearch({
  value,
  onChange,
  placeholder,
  results,
  onPick,
  disabled,
}: {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  results: { id: string; name: string; email?: string; avatarColor?: string }[]
  onPick: (member: { id: string; name: string }) => void
  disabled?: boolean
}) {
  const { t } = useT()
  return (
    <div>
      <TextInput
        size="sm"
        leftSection={<IconSearch size={16} />}
        placeholder={placeholder ?? t('common.searchMembers', 'Mitglieder suchen …')}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
      />
      {results.length > 0 && (
        <div
          style={{
            marginTop: 6,
            border: '1px solid var(--hb-border)',
            borderRadius: 8,
            overflow: 'hidden',
            background: 'var(--hb-surface)',
          }}
        >
          {results.slice(0, 6).map((m, i) => (
            <UnstyledButton
              key={m.id}
              className="hb-hover"
              onClick={() => onPick(m)}
              disabled={disabled}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                width: '100%',
                padding: '8px 12px',
                borderTop: i ? '1px solid var(--hb-border)' : undefined,
              }}
            >
              <Avatar name={m.name} color={m.avatarColor ?? '#857f99'} size={24} />
              <div style={{ flex: 1, minWidth: 0, textAlign: 'left' }}>
                <Text fz="sm" fw={600} truncate style={{ color: 'var(--hb-text)' }}>
                  {m.name}
                </Text>
                {m.email && (
                  <Text fz="xs" truncate style={{ color: 'var(--hb-text-3)' }}>
                    {m.email}
                  </Text>
                )}
              </div>
              <IconPlus size={16} color="var(--mantine-color-green-7)" />
            </UnstyledButton>
          ))}
        </div>
      )}
    </div>
  )
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
  const q = search.trim().toLowerCase()
  const shown = q
    ? members.filter(
        (m) => m.name.toLowerCase().includes(q) || m.email.toLowerCase().includes(q),
      )
    : members
  const pg = usePagination(shown, 10)

  useEffect(() => {
    const timer = setTimeout(() => onAddSearch?.(addSearch), 250)
    return () => clearTimeout(timer)
  }, [addSearch, onAddSearch])

  return (
    <SlideOver
      title={title}
      subtitle={subtitle}
      icon={icon}
      onClose={onClose}
      padded={false}
      footer={
        pg.totalPages > 1 || footer ? (
          <>
            {pg.totalPages > 1 && (
              <Pagination
                page={pg.page}
                perPage={pg.perPage}
                total={pg.total}
                totalPages={pg.totalPages}
                goPage={pg.goPage}
                setPerPage={pg.setPerPage}
              />
            )}
            {footer}
          </>
        ) : undefined
      }
    >
      {onAdd && (
        <PanelSection label={addLabel}>
          <MemberAddSearch
            value={addSearch}
            onChange={setAddSearch}
            placeholder={addPlaceholder}
            results={searchResults ?? []}
            onPick={(m) => {
              const picked = (searchResults ?? []).find((r) => r.id === m.id)
              if (picked) onAdd(picked)
              setAddSearch('')
            }}
          />
        </PanelSection>
      )}

      <PanelSection
        border={false}
        label={t('common.members', 'Mitglieder')}
        right={
          <Text fz="xs" className="num" style={{ color: 'var(--hb-text-3)' }}>
            {q ? `${shown.length} / ${members.length}` : members.length}
          </Text>
        }
      >
        {members.length > 10 && (
          <TextInput
            size="sm"
            mb={4}
            leftSection={<IconSearch size={16} />}
            placeholder={t('common.filter', 'Filter')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        )}
        {loading ? (
          <LoadingSpinner message={t('common.loading', 'Wird geladen …')} />
        ) : shown.length === 0 ? (
          <Text fz="sm" ta="center" py="xl" style={{ color: 'var(--hb-text-3)' }}>
            {q
              ? t('common.noResults', 'Keine Ergebnisse.')
              : t('common.noMembersYet', 'Noch keine Mitglieder.')}
          </Text>
        ) : (
          pg.paged.map((m) => (
            <PanelMemberRow
              key={m.id}
              name={m.name}
              detail={m.email}
              avatarColor={m.avatarColor}
              right={
                <>
                  {m.tier && <TierTag tier={m.tier} />}
                  {showRemove && onRemove && (
                    <ActionIcon
                      variant="subtle"
                      color="red"
                      onClick={() => onRemove(m)}
                      aria-label={t('common.remove', 'Entfernen')}
                    >
                      <IconX size={16} />
                    </ActionIcon>
                  )}
                </>
              }
            />
          ))
        )}
      </PanelSection>
    </SlideOver>
  )
}
