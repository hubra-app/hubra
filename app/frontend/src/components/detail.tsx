/* Building blocks for full detail pages (member, group, transaction, ...).
 *
 * Every detail page has the same shape: a back link, a header card with the
 * record's name, badges, actions and a strip of key figures, then cards of
 * label/value rows beside tabbed content. The member page set the pattern;
 * the others reuse these parts so they look and behave the same. */
import type { ReactNode } from 'react'
import { Button, Paper, Text, Title } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { IconArrowLeft } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useNav, useAuth } from '@/context/AppContext'
import { formatDateTime } from '@/format'
import { listAuditLog, type AuditLogPage } from '@/api/settings'
import { qk } from '@/data/keys'
import { Avatar } from './display'
import { LoadingSpinner } from './feedback'

/** "← Back to …" above the header card. */
export function DetailBack({ to, label }: { to: string; label: string }) {
  const { go } = useNav()
  return (
    <Button
      size="sm"
      variant="subtle"
      px={6}
      leftSection={<IconArrowLeft size={16} />}
      onClick={() => go(to)}
      style={{ marginBottom: 12, marginLeft: -6 }}
      data-testid="detail-back"
    >
      {label}
    </Button>
  )
}

/** The record at a glance: picture/icon, name, badges, actions, key figures. */
export function DetailHeader({
  media,
  title,
  chip,
  subtitle,
  badges,
  actions,
  facts,
}: {
  media?: ReactNode
  title: ReactNode
  /** A small grey label after the title, e.g. "Nr. 12". */
  chip?: ReactNode
  subtitle?: ReactNode
  badges?: ReactNode
  actions?: ReactNode
  /** DetailFact elements, shown in a strip under the name. */
  facts?: ReactNode
}) {
  return (
    <Paper withBorder p={{ base: 16, sm: 20 }} mb={16} data-testid="detail-header">
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
        {media}
        <div style={{ flex: '1 1 260px', minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <Title order={1} fz={{ base: 24, sm: 30 }} style={{ overflowWrap: 'anywhere' }}>
              {title}
            </Title>
            {chip && (
              <span
                className="num"
                style={{
                  fontSize: 'var(--mantine-font-size-xs)',
                  color: 'var(--hb-text-3)',
                  background: 'var(--hb-surface-2)',
                  borderRadius: 6,
                  padding: '2px 8px',
                }}
              >
                {chip}
              </span>
            )}
          </div>
          {subtitle && (
            <Text size="sm" mt={4} style={{ color: 'var(--hb-text-2)' }}>
              {subtitle}
            </Text>
          )}
          {badges && (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginTop: 8 }}>
              {badges}
            </div>
          )}
        </div>
        {actions && (
          <div className="page-actions" style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {actions}
          </div>
        )}
      </div>
      {facts && (
        <div className="member-facts" data-testid="detail-facts">
          {facts}
        </div>
      )}
    </Paper>
  )
}

/** A square coloured tile with an icon or letter, for records without a photo. */
export function DetailIcon({ color, children }: { color: string; children: ReactNode }) {
  return (
    <div
      aria-hidden
      style={{
        width: 64,
        height: 64,
        borderRadius: 14,
        background: color,
        color: 'white',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
        fontSize: 26,
        fontWeight: 700,
      }}
    >
      {children}
    </div>
  )
}

/** One key figure in the header strip. */
export function DetailFact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: 'var(--mantine-font-size-xs)', color: 'var(--hb-text-2)', marginBottom: 2 }}>
        {label}
      </div>
      <div style={{ fontSize: 'var(--mantine-font-size-md)', fontWeight: 600, color: 'var(--hb-text)' }}>
        {children}
      </div>
    </div>
  )
}

/** A card of label/value rows (the narrow column on detail pages). */
export function DetailSection({
  icon,
  title,
  right,
  children,
}: {
  icon?: ReactNode
  title: string
  right?: ReactNode
  children: ReactNode
}) {
  return (
    <Paper withBorder style={{ padding: 0, overflow: 'hidden' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '12px 16px',
          borderBottom: '1px solid var(--hb-border)',
          fontSize: 'var(--mantine-font-size-sm)',
          fontWeight: 700,
          color: 'var(--hb-text)',
        }}
      >
        {icon && <span style={{ color: 'var(--mantine-color-acc-7)', display: 'flex' }}>{icon}</span>}
        <span style={{ flex: 1 }}>{title}</span>
        {right}
      </div>
      <div className="member-rows">{children}</div>
    </Paper>
  )
}

export function DetailRow({
  label,
  mono,
  borderless,
  children,
}: {
  label: string
  mono?: boolean
  borderless?: boolean
  children: ReactNode
}) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: 12,
        padding: '10px 16px',
        borderBottom: borderless ? 'none' : '1px solid var(--hb-border)',
      }}
    >
      <span style={{ fontSize: 'var(--mantine-font-size-xs)', color: 'var(--hb-text-2)', flexShrink: 0 }}>
        {label}
      </span>
      <span
        className={mono ? 'num' : ''}
        style={{
          fontSize: 'var(--mantine-font-size-sm)',
          color: 'var(--hb-text)',
          fontWeight: 500,
          minWidth: 0,
          overflowWrap: 'anywhere',
          textAlign: 'right',
        }}
      >
        {children}
      </span>
    </div>
  )
}

/** A dash for an empty value. */
export function DetailEmpty() {
  return <span style={{ fontSize: 'var(--mantine-font-size-sm)', color: 'var(--hb-text-3)' }}>—</span>
}

export function DetailMuted({ children }: { children: ReactNode }) {
  return (
    <Text size="sm" c="dimmed">
      {children}
    </Text>
  )
}

/** A record that does not exist (any more) or that the viewer may not see. */
export function DetailNotFound({ back, backLabel, message }: { back: string; backLabel: string; message: string }) {
  return (
    <div>
      <DetailBack to={back} label={backLabel} />
      <Paper withBorder p={40} ta="center" data-testid="detail-not-found">
        <Text size="sm" c="dimmed">
          {message}
        </Text>
      </Paper>
    </div>
  )
}

/** Audit entries as a list; each opens its own entry page. */
export function ActivityList({ page, testId }: { page: AuditLogPage | undefined; testId?: string }) {
  const { t } = useT()
  const { go } = useNav()
  if (!page?.entries.length) {
    return <DetailMuted>{t('members.detail.noActivity', 'Noch keine Einträge')}</DetailMuted>
  }
  return (
    <div data-testid={testId}>
      {page.entries.map((e, i, all) => (
        <div
          key={e.id}
          role="link"
          tabIndex={0}
          onClick={() => go(`/app/audit-log/${e.id}`)}
          onKeyDown={(ev) => {
            if (ev.key === 'Enter') go(`/app/audit-log/${e.id}`)
          }}
          style={{
            display: 'flex',
            gap: 12,
            alignItems: 'center',
            padding: '10px 0',
            cursor: 'pointer',
            borderBottom: i === all.length - 1 ? 'none' : '1px solid var(--hb-border)',
          }}
        >
          <Avatar name={e.actor} color={e.avatarColor} size={28} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 'var(--mantine-font-size-sm)' }}>
              <strong>{e.actor}</strong> {t(`audit.actions.${e.action.replace(/ /g, '_')}`, e.action)}
            </div>
            {e.targetLabel && (
              <Text size="xs" c="dimmed" truncate>
                {e.targetLabel}
              </Text>
            )}
          </div>
          <Text size="xs" c="dimmed" style={{ whiteSpace: 'nowrap' }}>
            {formatDateTime(e.time)}
          </Text>
        </div>
      ))}
    </div>
  )
}

/** Who can read the audit log, and the entries about one record. */
function useRecordActivity(type: string, id: string | undefined, active: boolean) {
  const { hasPermission } = useAuth()
  const allowed = hasPermission('audit.audit.read')
  const query = useQuery({
    queryKey: qk.audit.target(type, id),
    queryFn: () => listAuditLog({ target: { type, id: id! }, pageSize: 25 }),
    enabled: allowed && active && !!id,
  })
  return { allowed, ...query }
}

/** The activity tab body: a spinner while loading, then the list. */
export function RecordActivity({
  type,
  id,
  testId = 'record-activity',
}: {
  type: string
  id: string | undefined
  testId?: string
}) {
  const q = useRecordActivity(type, id, true)
  if (!q.allowed) return null
  return q.isLoading ? <LoadingSpinner /> : <ActivityList page={q.data} testId={testId} />
}
