import { useState } from 'react'
import { Button, Paper, Title } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useT } from '@/locales/i18n'
import { useParams } from 'react-router-dom'
import { IconArrowLeft, IconPencil, IconLock, IconCircleCheck } from '@tabler/icons-react'
import { useNav, useToast, useAuth } from '@/context/AppContext'
import {
  Avatar,
  TierTag,
  StatusBadge,
  Tag,
  LastSeenBadge,
  LoadingSpinner,
} from '@/components/ui'
import type { Member } from '@/types'
import { getMember, disableMember, enableMember } from '@/api/members'
import { MemberEditModal } from '@/components/MemberEditModal'
import { roleLabels } from '@/roles'
import { qk } from '@/data/keys'

/* ── Member Detail ──────────────────────────── */
export function MemberDetailScreen({
  member: propMember,
}: {
  member?: Member | null
}) {
  const { t } = useT()
  const { id } = useParams<{ id: string }>()
  const { go } = useNav()
  const { notify } = useToast()
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const canUpdate = hasPermission('members.members.update')
  const canDisable = hasPermission('members.members.disable')
  const canEnable = hasPermission('members.members.enable')
  const [tab, setTab] = useState('overview')
  const { data: member } = useQuery({
    queryKey: qk.members.one(id),
    queryFn: () => getMember(id!),
    enabled: !!id,
    initialData: propMember ?? undefined,
  })
  const [editOpen, setEditOpen] = useState(false)
  const [togglingDisable, setTogglingDisable] = useState(false)

  const m = member
  if (!m) return <LoadingSpinner message={t('common.loading', 'Wird geladen …')} />

  const toggleDisable = async () => {
    if (!member) return
    setTogglingDisable(true)
    try {
      const updated = member.isDisabled
        ? await enableMember(member.id)
        : await disableMember(member.id)
      queryClient.invalidateQueries({ queryKey: qk.members.one(id) })
      notify(
        'success',
        updated.isDisabled ? t('members.disabled', 'Mitglied deaktiviert') : t('members.enabled', 'Mitglied aktiviert'),
        `${updated.name} has been ${
          updated.isDisabled ? 'disabled' : 'enabled'
        }.`,
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.updateFailed', 'Aktualisieren fehlgeschlagen'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    } finally {
      setTogglingDisable(false)
    }
  }

  return (
    <div>
      <div style={{ marginBottom: 20 }}>
        <Button
          size="sm"
          variant="subtle"
          px={6}
          leftSection={<IconArrowLeft size={16} />}
          onClick={() => go('/app/members')}
          style={{ marginBottom: 12, marginLeft: -6 }}
        >
          {t('members.detail.backToMembers')}
        </Button>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            flexWrap: 'wrap',
          }}
        >
          <Title order={1} fz={{ base: 26, sm: 32 }}>
            {m.name}
          </Title>
          <span
            className="num"
            style={{
              fontSize: 'var(--mantine-font-size-xs)',
              color: '#8c86a0',
              background: '#ebe8f2',
              borderRadius: 6,
              padding: '2px 8px',
            }}
          >
            {m.id}
          </span>
          <div
            style={{
              marginLeft: 'auto',
              display: 'flex',
              gap: 8,
            }}
          >
            {canUpdate && (
              <Button variant="default" onClick={() => setEditOpen(true)}>
                <IconPencil size={16} /> {t('common.edit')}
              </Button>
            )}
            {((m.isDisabled && canEnable) || (!m.isDisabled && canDisable)) && (
              <Button
                variant="default"
                style={{ color: m.isDisabled ? '#1f9d57' : '#b91c1c' }}
                onClick={toggleDisable}
                disabled={togglingDisable}
              >
                {togglingDisable
                  ? '…'
                  : m.isDisabled
                    ? t('members.detail.enable')
                    : t('members.detail.disable')}
              </Button>
            )}
          </div>
        </div>
      </div>

      <div
        className="detail-grid"
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <Paper
            withBorder
            shadow="sm"
            radius="lg"
            style={{ padding: 20, textAlign: 'center' }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'center',
                marginBottom: 14,
              }}
            >
              <Avatar
                name={m.name}
                color={m.avatarColor}
                size={72}
                lastSeen={m.lastSeen}
              />
            </div>
            <div
              style={{
                fontSize: 'var(--mantine-font-size-md)',
                fontWeight: 700,
                color: '#1a1625',
                marginBottom: 4,
              }}
            >
              {m.name}
            </div>
            <div
              style={{
                fontSize: 'var(--mantine-font-size-sm)',
                color: '#5e5873',
                marginBottom: 4,
              }}
            >
              {m.email}
            </div>
            <div
              style={{
                fontSize: 'var(--mantine-font-size-xs)',
                color: '#6131c4',
                fontFamily: '"JetBrains Mono"',
                marginBottom: 12,
              }}
            >
              {m.publicEmail}
            </div>
            <div
              style={{
                display: 'flex',
                gap: 8,
                justifyContent: 'center',
                flexWrap: 'wrap',
                marginBottom: 16,
              }}
            >
              <StatusBadge status={m.status} />
              <TierTag tier={m.tier} />
              {m.isDisabled && (
                <span
                  style={{
                    background: 'rgba(239,68,68,.15)',
                    border: '1px solid rgba(239,68,68,.3)',
                    borderRadius: 6,
                    padding: '4px 8px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4,
                    fontSize: 'var(--mantine-font-size-xs)',
                    color: '#b91c1c',
                  }}
                >
                  <IconLock size={12} />
                  {t('common.disabled')}
                </span>
              )}
            </div>
            <Button
              variant="default"
              style={{ width: '100%' }}
              onClick={() =>
                notify(
                  'info',
                  t('members.detail.message'),
                  `Opening message to ${m.name}`,
                )
              }
            >
              {t('members.detail.message')}
            </Button>
          </Paper>

          <Paper withBorder shadow="sm" radius="lg" style={{ padding: 0 }}>
            <DetailRow label={t('members.emailVerified')}>
              {m.privateEmailVerified ? (
                <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <IconCircleCheck size={14} color="#1f9d57" />
                  <span
                    style={{
                      fontSize: 'var(--mantine-font-size-sm)',
                      color: '#1f9d57',
                      fontWeight: 500,
                    }}
                  >
                    {t('common.yes')}
                  </span>
                </span>
              ) : (
                <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span
                    style={{
                      fontSize: 'var(--mantine-font-size-sm)',
                      color: '#b91c1c',
                      fontWeight: 500,
                    }}
                  >
                    {t('common.no')}
                  </span>
                </span>
              )}
            </DetailRow>
            <DetailRow label={t('members.clubUsername')} mono>
              {m.clubUsername || <Empty />}
            </DetailRow>
            <DetailRow label={t('common.roles', 'Rollen')}>
              {roleLabels(m.roles)}
            </DetailRow>
            <DetailRow label={t('members.joined')} mono>
              {m.joined || <Empty />}
            </DetailRow>
            <DetailRow label={t('members.lastSeen')}>
              <LastSeenBadge lastSeen={m.lastSeen} />
            </DetailRow>
            {m.toolHours > 0 && (
              <DetailRow label={t('members.detail.toolHours')} mono>
                {m.toolHours}h
              </DetailRow>
            )}
            <DetailRow
              label={t('common.password')}
              borderless={!m.mustChangePassword}
            >
              {m.mustChangePassword ? (
                <span
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 5,
                    color: '#b91c1c',
                    fontSize: 'var(--mantine-font-size-sm)',
                    fontWeight: 500,
                  }}
                >
                  <IconLock size={13} /> {t('members.detail.mustChange')}
                </span>
              ) : (
                <Empty />
              )}
            </DetailRow>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '10px 16px',
                borderTop: '1px solid #e6e3ef',
              }}
            >
              <span
                style={{
                  fontSize: 'var(--mantine-font-size-xs)',
                  color: '#5e5873',
                }}
              >
                {t('members.detail.groups')}
              </span>
              <div
                style={{
                  display: 'flex',
                  gap: 4,
                  flexWrap: 'wrap',
                  justifyContent: 'flex-end',
                }}
              >
                {m.groups.map((g) => (
                  <Tag key={g}>{g}</Tag>
                ))}
              </div>
            </div>
          </Paper>
        </div>

        <Paper withBorder shadow="sm" radius="lg">
          <div
            style={{
              borderBottom: '1px solid #d6d2e3',
              display: 'flex',
              gap: 0,
            }}
          >
            {['overview', 'payments', 'activity'].map((tabKey) => (
              <button
                key={tabKey}
                onClick={() => setTab(tabKey)}
                style={{
                  padding: '14px 20px',
                  fontSize: 'var(--mantine-font-size-sm)',
                  fontWeight: 600,
                  cursor: 'pointer',
                  border: 'none',
                  background: 'transparent',
                  color: tab === tabKey ? '#6131c4' : '#5e5873',
                  borderBottom:
                    tab === tabKey
                      ? '2px solid #6131c4'
                      : '2px solid transparent',
                  transition: 'all .15s',
                }}
              >
                {t(`members.detail.${tabKey}`)}
              </button>
            ))}
          </div>
          <div style={{ padding: 20 }}>
            {tab === 'overview' && (
              <div>
                <div
                  style={{
                    fontSize: 'var(--mantine-font-size-sm)',
                    fontWeight: 600,
                    color: '#5e5873',
                    marginBottom: 8,
                  }}
                >
                  {t('members.detail.notes', 'Notizen')}
                </div>
                <div
                  style={{
                    fontSize: 'var(--mantine-font-size-sm)',
                    color: '#2e2940',
                    background: '#f4f2f9',
                    borderRadius: 9,
                    padding: '12px 14px',
                    lineHeight: 1.6,
                  }}
                >
                  {m.notes || t('members.noNotesYet', 'Noch keine Notizen')}
                </div>
              </div>
            )}
            {tab === 'payments' && (
              <div
                style={{
                  color: '#8c86a0',
                  fontSize: 'var(--mantine-font-size-sm)',
                  padding: '20px 0',
                  textAlign: 'center',
                }}
              >
                {t('members.invoicesSoon', 'Die Rechnungsübersicht pro Mitglied folgt bald.')}
              </div>
            )}
            {tab === 'activity' && (
              <div
                style={{
                  color: '#8c86a0',
                  fontSize: 'var(--mantine-font-size-sm)',
                  padding: '20px 0',
                  textAlign: 'center',
                }}
              >
                {t('members.activitySoon', 'Das Aktivitätsprotokoll folgt bald.')}
              </div>
            )}
          </div>
        </Paper>
      </div>

      <MemberEditModal
        member={m}
        mode="edit"
        open={editOpen}
        onClose={() => setEditOpen(false)}
        onSaved={() => {
          queryClient.invalidateQueries({ queryKey: qk.members.one(id) })
          setEditOpen(false)
        }}
      />
    </div>
  )
}

/* ── Detail helpers ───────────────────────────── */
function Empty() {
  return (
    <span style={{ fontSize: 'var(--mantine-font-size-sm)', color: '#bcc5cd' }}>
      —
    </span>
  )
}

function DetailRow({
  label,
  mono,
  borderless,
  children,
}: {
  label: string
  mono?: boolean
  borderless?: boolean
  children: React.ReactNode
}) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '10px 16px',
        borderBottom: borderless ? 'none' : '1px solid #e6e3ef',
      }}
    >
      <span
        style={{ fontSize: 'var(--mantine-font-size-xs)', color: '#5e5873' }}
      >
        {label}
      </span>
      <span
        className={mono ? 'num' : ''}
        style={{
          fontSize: 'var(--mantine-font-size-sm)',
          color: '#1a1625',
          fontWeight: 500,
        }}
      >
        {children}
      </span>
    </div>
  )
}
