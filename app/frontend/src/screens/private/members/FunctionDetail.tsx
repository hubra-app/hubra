import { useMemo, useState } from 'react'
import { Anchor, Button, Paper } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { IconInfoCircle, IconMail, IconPencil, IconTrash, IconUserCog } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useAuth, useData, useNav, useToast } from '@/context/AppContext'
import { ConfirmModal, LoadingSpinner, MemberRoster, Tabs, Tag, type SlideOverMember } from '@/components/ui'
import {
  DetailBack,
  DetailEmpty,
  DetailFact,
  DetailHeader,
  DetailIcon,
  DetailNotFound,
  DetailRow,
  DetailSection,
  RecordActivity,
} from '@/components/detail'
import { assignHolder, deleteFunction, listFunctions, removeHolder } from '@/api/functions'
import { lookupsQuery } from '@/api/lookups'
import { useMemberSearch } from '@/data/members'
import { qk } from '@/data/keys'
import { formatDate } from '@/format'
import { roleLabel } from '@/roles'
import { FunctionFormModal } from './FunctionFormModal'

/* ── One club function (office), as its own page ── */
export function FunctionDetailScreen() {
  const { t } = useT()
  const { id } = useParams<{ id: string }>()
  const { go } = useNav()
  const { notify } = useToast()
  const { modules } = useData()
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const canUpdate = hasPermission('functions.functions.update')
  const canDelete = hasPermission('functions.functions.delete')
  const canSeeMembers = hasPermission('members.members.read')
  const canAudit = hasPermission('audit.audit.read')
  const [tab, setTab] = useState('holders')
  const [editOpen, setEditOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  const { data: functions, isLoading } = useQuery({
    queryKey: qk.functions,
    queryFn: () => listFunctions(),
  })
  const fn = functions?.find((f) => String(f.id) === id)
  const { data: lookups } = useQuery(lookupsQuery)
  const { data: searchData } = useMemberSearch(searchQuery, { enabled: searchQuery.length >= 2 })

  const holders: SlideOverMember[] = useMemo(
    () =>
      (fn?.holders ?? []).map((h) => ({
        id: String(h.memberId),
        name: h.memberName,
        email: h.assignedAt ? t('members.detail.since', 'seit {{date}}', { date: formatDate(h.assignedAt) }) : '',
        avatarColor: 'var(--hb-text-2)',
      })),
    [fn, t],
  )
  const searchResults = useMemo(() => {
    if (!searchData || searchQuery.length < 2) return undefined
    const held = new Set(holders.map((h) => h.id))
    return searchData.members
      .filter((m) => !held.has(m.id))
      .map((m) => ({ id: m.id, name: m.name, email: m.email, avatarColor: m.avatarColor }))
  }, [searchData, holders, searchQuery])

  const back = '/app/members/functions'
  const backLabel = t('functions.backToFunctions', 'Zurück zu den Funktionen')
  if (isLoading) return <LoadingSpinner message={t('common.loading', 'Wird geladen …')} />
  if (!fn) {
    return (
      <DetailNotFound
        back={back}
        backLabel={backLabel}
        message={t('functions.notFound', 'Diese Funktion gibt es nicht (mehr).')}
      />
    )
  }

  const role =
    fn.grantsRoleId != null && lookups?.roles.get(fn.grantsRoleId)
      ? roleLabel(lookups.roles.get(fn.grantsRoleId)!)
      : null
  const full = fn.holders.length >= fn.maxHolders
  const refresh = () => queryClient.invalidateQueries({ queryKey: qk.functions })
  const fail = (err: unknown) =>
    notify('error', t('common.error'), err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'))

  const add = (m: SlideOverMember) =>
    assignHolder(fn.id, Number(m.id))
      .then(() => {
        refresh()
        notify('success', t('common.saved', 'Gespeichert'), `${m.name} → ${fn.name}`)
      })
      .catch(fail)
  const remove = (m: SlideOverMember) =>
    removeHolder(fn.id, Number(m.id))
      .then(() => {
        refresh()
        notify('info', t('common.removed', 'Entfernt'), `${m.name} ← ${fn.name}`)
      })
      .catch(fail)
  const destroy = async () => {
    try {
      await deleteFunction(fn.id)
      refresh()
      notify('info', t('functions.deleted', 'Gelöscht'), t('functions.deletedMsg', 'Die Funktion wurde gelöscht.'))
      go(back)
    } catch (err) {
      fail(err)
    }
  }

  const tabs = [
    { id: 'holders', label: t('functions.holders', 'Besetzt durch') },
    ...(canAudit ? [{ id: 'activity', label: t('members.detail.activity') }] : []),
  ]

  return (
    <div>
      <DetailBack to={back} label={backLabel} />
      <DetailHeader
        media={
          <DetailIcon color="var(--mantine-color-acc-7)">
            <IconUserCog size={30} />
          </DetailIcon>
        }
        title={fn.name}
        subtitle={fn.description || undefined}
        badges={
          <>
            {role && <Tag color="var(--mantine-color-acc-text)">{t('functions.givesRole', 'Gibt die Rolle {{role}}', { role })}</Tag>}
            {fn.holders.length === 0 && <Tag>{t('functions.noHolder', 'Unbesetzt')}</Tag>}
          </>
        }
        actions={
          <>
            {canUpdate && (
              <Button variant="default" leftSection={<IconPencil size={16} />} onClick={() => setEditOpen(true)}>
                {t('common.edit')}
              </Button>
            )}
            {canDelete && (
              <Button
                variant="default"
                leftSection={<IconTrash size={16} />}
                style={{ color: 'var(--mantine-color-red-text)' }}
                onClick={() => setDeleteOpen(true)}
              >
                {t('common.delete', 'Löschen')}
              </Button>
            )}
          </>
        }
        facts={
          <>
            <DetailFact label={t('functions.holders', 'Besetzt durch')}>
              <span className="num" data-testid="function-holder-count">
                {fn.holders.length} / {fn.maxHolders}
              </span>
            </DetailFact>
            <DetailFact label={t('functions.grantsRole', 'Gibt die Rolle')}>{role ?? '—'}</DetailFact>
          </>
        }
      />

      <div className="detail-grid">
        <DetailSection icon={<IconInfoCircle size={16} />} title={t('functions.detail.about', 'Funktion')}>
          <DetailRow label={t('functions.maxHolders', 'Max. Anzahl Personen')} mono>
            {fn.maxHolders}
          </DetailRow>
          <DetailRow label={t('functions.grantsRole', 'Gibt die Rolle')}>{role ?? <DetailEmpty />}</DetailRow>
          {modules.mail && (
            <DetailRow label={t('mail.mail', 'Mail')}>
              <Anchor size="sm" onClick={() => go('/app/mail?tab=functions')}>
                <IconMail size={13} style={{ verticalAlign: -2, marginRight: 4 }} />
                {t('mail.admin.openInMailAdmin', 'In der Mail-Verwaltung öffnen')}
              </Anchor>
            </DetailRow>
          )}
        </DetailSection>

        <Paper withBorder p={{ base: 16, sm: 20 }} pt={8}>
          {tabs.length > 1 && <Tabs tabs={tabs} activeTab={tab} onTabChange={setTab} />}
          {tab === 'holders' && (
            <MemberRoster
              title={t('functions.holders', 'Besetzt durch')}
              members={holders}
              emptyText={t('functions.noHolder', 'Unbesetzt')}
              addLabel={t('functions.assignHolder', 'Person zuweisen')}
              addPlaceholder={t('functions.searchMembers', 'Mitglieder suchen …')}
              searchResults={canUpdate && !full ? searchResults : undefined}
              onAdd={canUpdate && !full ? add : undefined}
              onAddSearch={canUpdate && !full ? setSearchQuery : undefined}
              onRemove={canUpdate ? remove : undefined}
              onOpen={canSeeMembers ? (m) => go(`/app/members/${m.id}`) : undefined}
              testId="function-holders"
            />
          )}
          {tab === 'activity' && <RecordActivity type="Function" id={String(fn.id)} testId="function-activity" />}
        </Paper>
      </div>

      {editOpen && <FunctionFormModal key={fn.id} target={fn} onClose={() => setEditOpen(false)} />}
      <ConfirmModal
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        title={t('functions.deleteTitle', 'Funktion löschen?')}
        body={t('functions.deleteBody', 'Die Funktion wird gelöscht. Ihre Mail-Adressen werden entfernt.')}
        onConfirm={destroy}
      />
    </div>
  )
}
