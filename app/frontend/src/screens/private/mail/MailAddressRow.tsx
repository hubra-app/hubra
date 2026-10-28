import { Badge } from '@mantine/core'
import { useT } from '@/locales/i18n'
import {
  IconMail,
  IconArrowForwardUp,
  IconAlertTriangle,
  IconCircleCheck,
  IconClock,
  IconCircleX,
} from '@tabler/icons-react'
import type { ManagedMailAddressInfo } from '@/api/mail'
import type { DataColumn } from '@/components/ui'

const SYNC_COLORS: Record<string, string> = {
  ok: '#1f9d57',
  pending: '#c2870f',
  drift: '#e65100',
  error: '#ff4d3d',
}

const SYNC_ICONS: Record<string, typeof IconCircleCheck> = {
  ok: IconCircleCheck,
  pending: IconClock,
  drift: IconAlertTriangle,
  error: IconCircleX,
}

function SyncBadge({
  state,
  error,
}: {
  state?: string | null
  error?: string | null
}) {
  const { t } = useT()
  if (!state || state === 'ok') {
    return (
      <Badge
        variant="light"
        color="green"
        radius="xl"
        style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}
      >
        <IconCircleCheck size={11} />
        {t('mail.admin.syncOk', 'OK')}
      </Badge>
    )
  }
  const Icon = SYNC_ICONS[state] || IconAlertTriangle
  const color = SYNC_COLORS[state] || '#6b7480'
  const labels: Record<string, string> = {
    pending: t('mail.admin.syncPending', 'Ausstehend'),
    drift: t('mail.admin.syncDrift', 'Abwichig'),
    error: t('mail.admin.syncError', 'Fehler'),
  }
  return (
    <Badge
      title={error || undefined}
      variant="light"
      radius="xl"
      styles={{
        root: {
          display: 'inline-flex',
          alignItems: 'center',
          gap: 4,
          background: `${color}15`,
          color,
        },
      }}
    >
      <Icon size={11} />
      {labels[state] || state}
    </Badge>
  )
}

function QuotaBar({
  used,
  total,
}: {
  used: number | null
  total: number | null
}) {
  if (used == null || total == null || total === 0)
    return <span style={{ color: '#99a2ac' }}>—</span>
  const pct = Math.min(100, (used / total) * 100)
  const color = pct > 90 ? '#ff4d3d' : pct > 70 ? '#c2870f' : '#1f9d57'
  const usedMB = (used / 1048576).toFixed(0)
  const totalMB = (total / 1048576).toFixed(0)
  return (
    <div style={{ minWidth: 100 }}>
      <div
        style={{
          fontSize: 'var(--mantine-font-size-xs)',
          color: '#6b7480',
          marginBottom: 2,
        }}
      >
        {usedMB} / {totalMB} MB
      </div>
      <div
        style={{
          height: 6,
          background: '#e3eae6',
          borderRadius: 3,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: '100%',
            background: color,
            borderRadius: 3,
          }}
        />
      </div>
    </div>
  )
}

export function MailAddressRow({
  entry,
  ownerName,
  onEdit,
}: {
  entry: ManagedMailAddressInfo
  ownerName?: string | null
  onEdit: () => void
}) {
  const { t } = useT()
  const isMailbox = entry.addressType === 'mailbox'
  const forwardTargets = entry.cachedForwardTargets || entry.fixedForwardTargets
  const targetCount = forwardTargets?.length ?? 0

  return (
    <tr
      onClick={onEdit}
      style={{ cursor: 'pointer', transition: 'background .1s' }}
      onMouseEnter={(e) => (e.currentTarget.style.background = '#f4f8f5')}
      onMouseLeave={(e) => (e.currentTarget.style.background = '')}
    >
      <td style={{ fontWeight: 600, color: '#181818' }}>
        {ownerName || entry.displayName || entry.address}
      </td>
      <td style={{ fontSize: 'var(--mantine-font-size-sm)', color: '#2596be' }}>
        {entry.address}
      </td>
      <td>
        <Badge
          variant="light"
          radius="xl"
          styles={{
            root: {
              display: 'inline-flex',
              alignItems: 'center',
              gap: 3,
              background: isMailbox ? '#e8f5e9' : '#e3f2fd',
              color: isMailbox ? '#1f9d57' : '#2596be',
            },
          }}
        >
          {isMailbox ? (
            <IconMail size={10} />
          ) : (
            <IconArrowForwardUp size={10} />
          )}
          {isMailbox
            ? t('mail.admin.mailbox', 'Mailbox')
            : t('mail.admin.alias', 'Alias')}
        </Badge>
      </td>
      <td>
        {isMailbox ? (
          <QuotaBar
            used={entry.quotaUsed ?? null}
            total={entry.quotaTotal ?? null}
          />
        ) : (
          '—'
        )}
      </td>
      <td style={{ fontSize: 'var(--mantine-font-size-xs)', color: '#6b7480' }}>
        {entry.retention != null
          ? `${Math.round(entry.retention / 86400000)}d`
          : t('mail.admin.retentionOff', 'OFF')}
      </td>
      <td style={{ fontSize: 'var(--mantine-font-size-xs)', color: '#6b7480' }}>
        {targetCount > 0 ? (
          <span
            style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}
          >
            <IconArrowForwardUp size={10} />
            {targetCount} {t('mail.admin.targets', 'Targets')}
          </span>
        ) : (
          '—'
        )}
      </td>
      <td>
        {entry.isEnabled ? (
          <Badge variant="light" color="green" radius="xl">
            {t('mail.enabled', 'Aktiviert')}
          </Badge>
        ) : (
          <Badge variant="light" color="red" radius="xl">
            {t('mail.disabled', 'Deaktiviert')}
          </Badge>
        )}
      </td>
      <td>
        <SyncBadge state={entry.syncState} error={entry.syncError} />
      </td>
    </tr>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useMailColumns(
  getOwnerName: (entry: ManagedMailAddressInfo) => string | null | undefined,
): DataColumn<ManagedMailAddressInfo>[] {
  const { t } = useT()
  return [
    {
      key: 'name',
      header: t('common.name', 'Name'),
      render: (entry) => (
        <span style={{ fontWeight: 600, color: '#181818' }}>
          {getOwnerName(entry) || entry.displayName || entry.address}
        </span>
      ),
    },
    {
      key: 'address',
      header: t('mail.address', 'Adrasse'),
      render: (entry) => (
        <span
          style={{
            fontSize: 'var(--mantine-font-size-sm)',
            color: '#2596be',
          }}
        >
          {entry.address}
        </span>
      ),
    },
    {
      key: 'type',
      header: t('mail.admin.type', 'Typ'),
      render: (entry) => {
        const isMailbox = entry.addressType === 'mailbox'
        return (
          <Badge
            variant="light"
            radius="xl"
            styles={{
              root: {
                display: 'inline-flex',
                alignItems: 'center',
                gap: 3,
                background: isMailbox ? '#e8f5e9' : '#e3f2fd',
                color: isMailbox ? '#1f9d57' : '#2596be',
              },
            }}
          >
            {isMailbox ? (
              <IconMail size={10} />
            ) : (
              <IconArrowForwardUp size={10} />
            )}
            {isMailbox
              ? t('mail.admin.mailbox', 'Mailbox')
              : t('mail.admin.alias', 'Alias')}
          </Badge>
        )
      },
    },
    {
      key: 'quota',
      header: t('mail.admin.quota', 'Quota'),
      render: (entry) => {
        const isMailbox =
          entry.addressType === 'mailbox' && entry.ownerType !== 'mail_address'
        return isMailbox ? (
          <QuotaBar
            used={entry.quotaUsed ?? null}
            total={entry.quotaTotal ?? null}
          />
        ) : (
          <span style={{ color: '#99a2ac' }}>{'\u2014'}</span>
        )
      },
    },
    {
      key: 'retention',
      header: t('mail.admin.retention', 'Retention'),
      render: (entry) => {
        if (
          entry.ownerType === 'mail_address' ||
          (entry.isSystem && entry.addressType === 'alias')
        )
          return <span style={{ color: '#99a2ac' }}>{'\u2014'}</span>
        return (
          <span
            style={{
              fontSize: 'var(--mantine-font-size-xs)',
              color: '#6b7480',
            }}
          >
            {entry.retention != null
              ? `${Math.round(entry.retention / 86400000)}d`
              : t('mail.admin.retentionOff', 'OFF')}
          </span>
        )
      },
    },
    {
      key: 'targets',
      header: t('mail.admin.targets', 'Targets'),
      render: (entry) => {
        const forwardTargets =
          entry.forwardTargets ||
          entry.cachedForwardTargets ||
          entry.fixedForwardTargets
        const targetCount = forwardTargets?.length ?? 0
        return targetCount > 0 ? (
          <span
            title={forwardTargets?.join(', ')}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 3,
              fontSize: 'var(--mantine-font-size-xs)',
              color: '#6b7480',
            }}
          >
            <IconArrowForwardUp size={10} />
            {targetCount} {t('mail.admin.targets', 'Targets')}
          </span>
        ) : (
          <span style={{ color: '#99a2ac' }}>{'\u2014'}</span>
        )
      },
    },
    {
      key: 'status',
      header: t('mail.admin.status', 'Status'),
      render: (entry) =>
        entry.isEnabled ? (
          <Badge variant="light" color="green" radius="xl">
            {t('mail.enabled', 'Aktiviert')}
          </Badge>
        ) : (
          <Badge variant="light" color="red" radius="xl">
            {t('mail.disabled', 'Deaktiviert')}
          </Badge>
        ),
    },
    {
      key: 'sync',
      header: t('mail.admin.sync', 'Sync'),
      render: (entry) => (
        <SyncBadge state={entry.syncState} error={entry.syncError} />
      ),
    },
  ]
}
