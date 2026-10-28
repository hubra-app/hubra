import { useState, useMemo } from 'react'
import { Button, Select, Paper } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useT } from '@/locales/i18n'
import { useToast, useData, useAuth } from '@/context/AppContext'
import { Avatar, Modal, Field } from '@/components/ui'
import type { Application } from '@/types'
import {
  listApplications,
  approveApplication,
  declineApplication,
} from '@/api/applications'
import { getLookups, lookupsQuery } from '@/api/lookups'
import { formatDateTime } from '@/format'
import { LeaveRequests } from './LeaveRequests'
import { roleLabel } from '@/roles'

/* ── Applications ───────────────────────────── */
export function ApplicationsTab() {
  const { notify } = useToast()
  const { setPendingApplicationCount, setMemberCount } = useData()
  const { hasPermission } = useAuth()
  const { t } = useT()
  const queryClient = useQueryClient()
  const canApprove = hasPermission('applications.applications.approve')
  const canDecline = hasPermission('applications.applications.decline')
  const { data: apps = [] } = useQuery({
    queryKey: ['applications'],
    queryFn: () => listApplications(),
  })
  const { data: lookupsData } = useQuery({
    ...lookupsQuery,
  })
  const allTiers = useMemo(
    () => (lookupsData ? [...lookupsData.tiersByName.keys()] : []),
    [lookupsData],
  )
  const allRoles = useMemo(
    () => (lookupsData ? [...lookupsData.rolesByName.keys()] : ['Member']),
    [lookupsData],
  )

  const [approveTarget, setApproveTarget] = useState<Application | null>(null)
  const [approveTier, setApproveTier] = useState('')
  const [approveRole, setApproveRole] = useState('Member')
  const [approving, setApproving] = useState(false)

  const openApprove = (app: Application) => {
    setApproveTarget(app)
    setApproveTier(app.wantsTier || allTiers[0] || '')
    setApproveRole('Member')
  }

  const confirmApprove = async () => {
    if (!approveTarget) return
    setApproving(true)
    try {
      const { tiersByName } = await getLookups()
      const tierId = tiersByName.get(approveTier)
      if (!tierId) throw new Error(`Unknown tier: ${approveTier}`)
      await approveApplication(approveTarget.id, tierId, approveRole)
      queryClient.invalidateQueries({ queryKey: ['applications'] })
      setPendingApplicationCount()
      setMemberCount((prev) => prev + 1)
      setApproveTarget(null)
      notify(
        'success',
        t('members.applications.applicationApproved', 'Antrag angenommen'),
        t('members.applications.applicationApprovedMsg', {
          name: approveTarget.name,
        }),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekannter Fehler'),
      )
    } finally {
      setApproving(false)
    }
  }

  const decline = async (id: string, name: string) => {
    try {
      await declineApplication(id)
      queryClient.invalidateQueries({ queryKey: ['applications'] })
      setPendingApplicationCount()
      notify(
        'info',
        t('members.applications.applicationDeclined', 'Antrag abgelehnt'),
        t('members.applications.applicationDeclinedMsg', { name }),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekannter Fehler'),
      )
    }
  }

  return (
    <div>
      <Paper withBorder shadow="sm" radius="lg">
        {apps.length === 0 ? (
          <div style={{ padding: 48, textAlign: 'center', color: '#8c86a0' }}>
            <div style={{ fontSize: 32, marginBottom: 12 }}>✓</div>
            <div
              style={{
                fontSize: 'var(--mantine-font-size-sm)',
                fontWeight: 500,
              }}
            >
              {t(
                'members.applications.noPendingApplications',
                'Keine offenen Anträge',
              )}
            </div>
          </div>
        ) : (
          apps.map((app) => (
            <div
              key={app.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 14,
                padding: '14px 20px',
                borderBottom: '1px solid #e6e3ef',
              }}
            >
              <Avatar name={app.name} color={app.avatarColor} size={38} />
              <div style={{ flex: 1 }}>
                <div
                  style={{
                    fontSize: 'var(--mantine-font-size-sm)',
                    fontWeight: 600,
                    color: '#1a1625',
                  }}
                >
                  {app.name}
                </div>
                <div
                  style={{
                    fontSize: 'var(--mantine-font-size-xs)',
                    color: '#5e5873',
                  }}
                >
                  {app.email}
                  {app.wantsTier && (
                    <>
                      {' · '}
                      {t('members.applications.wants', 'möchte')} <strong>{app.wantsTier}</strong>
                    </>
                  )}
                </div>
              </div>
              <span
                className="num"
                style={{
                  fontSize: 'var(--mantine-font-size-xs)',
                  color: '#8c86a0',
                }}
              >
                {formatDateTime(app.appliedAt)}
              </span>
              {canDecline && (
                <Button
                  size="sm"
                  variant="default"
                  onClick={() => decline(app.id, app.name)}
                >
                  {t('members.applications.decline', 'Ablehnen')}
                </Button>
              )}
              {canApprove && (
                <Button
                  size="sm"
                  variant="filled"
                  onClick={() => openApprove(app)}
                >
                  {t('members.applications.approve', 'Annehmen')}
                </Button>
              )}
            </div>
          ))
        )}
      </Paper>

      <LeaveRequests />

      <Modal
        open={!!approveTarget}
        onClose={() => setApproveTarget(null)}
        title={t('members.applications.approveTitle', 'Antrag annehmen')}
        subtitle={approveTarget?.name}
        footer={
          <>
            <Button variant="default" onClick={() => setApproveTarget(null)}>
              {t('common.cancel')}
            </Button>
            <Button
              variant="filled"
              onClick={confirmApprove}
              disabled={approving || !approveTier}
            >
              {approving
                ? t('members.applications.approving', 'Wird angenommen …')
                : t(
                    'members.applications.approveAndCreate',
                    'Annehmen und Mitglied erstellen',
                  )}
            </Button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Field label={t('members.tier', 'Stufe')}>
            <Select
              data={allTiers.map((tierItem) => ({
                value: tierItem,
                label: tierItem,
              }))}
              value={approveTier}
              onChange={(v) => v && setApproveTier(v)}
              searchable
            />
          </Field>
          <Field label={t('common.roles', 'Rollen')}>
            <Select
              data={allRoles.map((r) => ({ value: r, label: roleLabel(r) }))}
              value={approveRole}
              onChange={(v) => v && setApproveRole(v)}
              searchable
            />
          </Field>
        </div>
      </Modal>
    </div>
  )
}
