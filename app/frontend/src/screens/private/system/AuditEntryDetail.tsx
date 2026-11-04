import { Anchor, Badge, Paper } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { IconHistory, IconTarget, IconUser } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useNav } from '@/context/AppContext'
import { formatDateTime } from '@/format'
import { getAuditEntry } from '@/api/settings'
import { qk } from '@/data/keys'
import { recordPath } from './auditPaths'
import { Avatar, LoadingSpinner, Tag } from '@/components/ui'
import {
  DetailBack,
  DetailEmpty,
  DetailHeader,
  DetailFact,
  DetailIcon,
  DetailNotFound,
  DetailRow,
  DetailSection,
  RecordActivity,
} from '@/components/detail'

/* ── One audit log entry, as its own page ─────── */
export function AuditEntryDetailScreen() {
  const { t } = useT()
  const { go } = useNav()
  const { id } = useParams<{ id: string }>()
  const { data: e, isLoading, error } = useQuery({
    queryKey: qk.audit.entry(id),
    queryFn: () => getAuditEntry(id!),
    enabled: !!id,
  })
  const back = '/app/audit-log'
  const backLabel = t('audit.backToLog', 'Zurück zum Protokoll')

  if (isLoading) return <LoadingSpinner message={t('common.loading', 'Wird geladen …')} />
  if (error || !e) {
    return (
      <DetailNotFound
        back={back}
        backLabel={backLabel}
        message={t('audit.loadFailed', 'Eintrag konnte nicht geladen werden')}
      />
    )
  }
  const action = t(`audit.actions.${e.action}`, e.action.replace(/_/g, ' '))
  const target = recordPath(e.targetType, e.targetId)

  return (
    <div>
      <DetailBack to={back} label={backLabel} />
      <DetailHeader
        media={
          <DetailIcon color="var(--mantine-color-acc-7)">
            <IconHistory size={30} />
          </DetailIcon>
        }
        title={action}
        chip={t('audit.entryTitle', 'Eintrag #{{id}}', { id: e.id })}
        subtitle={e.targetLabel ?? undefined}
        badges={
          <Badge variant="light" color="green" radius="xl" style={{ textTransform: 'none' }}>
            {e.action.replace(/_/g, ' ')}
          </Badge>
        }
        facts={
          <>
            <DetailFact label={t('audit.timestamp', 'Zeitpunkt')}>
              <span className="num">{formatDateTime(e.time)}</span>
            </DetailFact>
            <DetailFact label={t('audit.actor', 'Person')}>
              {e.actorName ?? t('audit.systemActor', 'System (automatisch)')}
            </DetailFact>
            {e.targetType && (
              <DetailFact label={t('common.type', 'Typ')}>{e.targetType}</DetailFact>
            )}
          </>
        }
      />

      <div className="detail-grid">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <DetailSection icon={<IconUser size={16} />} title={t('audit.actor', 'Person')}>
            {e.actorName ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px' }}>
                <Avatar name={e.actorName} color={e.actorAvatarColor} size={32} />
                <div style={{ minWidth: 0 }}>
                  {e.actorId != null ? (
                    <Anchor size="sm" fw={600} onClick={() => go(`/app/members/${e.actorId}`)}>
                      {e.actorName}
                    </Anchor>
                  ) : (
                    <div style={{ fontWeight: 600 }}>{e.actorName}</div>
                  )}
                  {e.actorId != null && (
                    <div style={{ fontSize: 'var(--mantine-font-size-xs)', color: 'var(--hb-text-3)' }}>
                      {t('audit.memberId', 'Mitglied #{{id}}', { id: e.actorId })}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <DetailRow label={t('audit.actor', 'Person')}>
                {t('audit.systemActor', 'System (automatisch)')}
              </DetailRow>
            )}
          </DetailSection>

          <DetailSection icon={<IconTarget size={16} />} title={t('audit.target', 'Ziel')}>
            <DetailRow label={t('common.type', 'Typ')}>
              {e.targetType ? <Tag>{e.targetType}</Tag> : <DetailEmpty />}
            </DetailRow>
            <DetailRow label={t('audit.label', 'Bezeichnung')}>
              {target && e.targetLabel ? (
                <Anchor size="sm" onClick={() => go(target)} data-testid="audit-target-link">
                  {e.targetLabel}
                </Anchor>
              ) : (
                (e.targetLabel ?? <DetailEmpty />)
              )}
            </DetailRow>
            <DetailRow label={t('audit.id', 'ID')} mono>
              {e.targetId ?? <DetailEmpty />}
            </DetailRow>
            <DetailRow label={t('audit.entryId', 'Eintrags-ID')} mono>
              #{e.id}
            </DetailRow>
          </DetailSection>
        </div>

        <Paper withBorder p={{ base: 16, sm: 20 }}>
          <div
            style={{
              fontSize: 'var(--mantine-font-size-sm)',
              fontWeight: 600,
              color: 'var(--hb-text-2)',
              marginBottom: 8,
            }}
          >
            {t('audit.sameRecord', 'Weitere Einträge zu diesem Ziel')}
          </div>
          {e.targetType && e.targetId != null ? (
            <RecordActivity type={e.targetType} id={String(e.targetId)} />
          ) : (
            <DetailEmpty />
          )}
        </Paper>
      </div>
    </div>
  )
}
