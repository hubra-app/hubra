import { useMemo, useState } from 'react'
import { ActionIcon, Anchor, Badge, Button, Group as Row, Paper, Select, Stack, Text } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { IconBolt, IconClock, IconInfoCircle, IconPencil, IconStar, IconTrash, IconX } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useAuth, useNav, useToast } from '@/context/AppContext'
import { ConfirmModal, LoadingSpinner, MemberRoster, Tabs, type SlideOverMember } from '@/components/ui'
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
import { addGroupMember, deleteGroup, listGroupFunctions, listGroups, removeGroupMember } from '@/api/groups'
import { assignHolder, listFunctions, removeHolder } from '@/api/functions'
import { MemberPicker } from '@/components/MemberPicker'
import { roleLabel } from '@/roles'
import { listGroupMembers } from '@/api/members'
import { useMemberSearch } from '@/data/members'
import { qk } from '@/data/keys'
import { GroupFormModal, VisibilityBadge } from './GroupFormModal'

/* ── One group, as its own page ───────────────── */
export function GroupDetailScreen() {
  const { t } = useT()
  const { id } = useParams<{ id: string }>()
  const { go } = useNav()
  const { notify } = useToast()
  const { currentUser, hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const [tab, setTab] = useState('members')
  const [editOpen, setEditOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  const { data: groups, isLoading } = useQuery({
    queryKey: qk.groups.all,
    queryFn: () => listGroups(),
  })
  const group = groups?.find((g) => g.id === id)
  const { data: members = [], isLoading: membersLoading } = useQuery({
    queryKey: qk.groups.members(id ?? ''),
    queryFn: () => listGroupMembers(id!),
    enabled: !!group,
  })
  const { data: searchData } = useMemberSearch(searchQuery, { enabled: searchQuery.length >= 2 })
  const { data: groupFunctions = [] } = useQuery({
    queryKey: [...qk.groups.members(id ?? ''), 'functions'],
    queryFn: () => listGroupFunctions(id!),
    enabled: !!group,
  })
  const canAssign = hasPermission('functions.functions.update')
  const { data: allFunctions = [] } = useQuery({
    queryKey: qk.functions,
    queryFn: () => listFunctions(),
    enabled: !!group && canAssign,
  })
  const [pickFunction, setPickFunction] = useState<string | null>(null)
  const [pickMember, setPickMember] = useState<string | null>(null)

  const roster: SlideOverMember[] = useMemo(
    () =>
      members.map((m) => ({
        id: m.id,
        name: m.name,
        email: m.email,
        avatarColor: m.avatarColor,
        tier: m.tier,
      })),
    [members],
  )
  const searchResults = useMemo(() => {
    if (!searchData || searchQuery.length < 2) return undefined
    const inGroup = new Set(members.map((m) => m.id))
    return searchData.members
      .filter((m) => !inGroup.has(m.id))
      .map((m) => ({ id: m.id, name: m.name, email: m.email, avatarColor: m.avatarColor, tier: m.tier }))
  }, [searchData, members, searchQuery])

  const back = '/app/groups'
  const backLabel = t('groups.backToGroups', 'Zurück zu den Gruppen')
  if (isLoading) return <LoadingSpinner message={t('common.loading', 'Wird geladen …')} />
  if (!group) {
    return (
      <DetailNotFound
        back={back}
        backLabel={backLabel}
        message={t('groups.notFound', 'Diese Gruppe gibt es nicht (mehr) oder du siehst sie nicht.')}
      />
    )
  }

  // A role held for this group only counts here too, and so does leading it.
  const leads = currentUser != null && group.leadId === Number(currentUser.id)
  const canEdit = leads || hasPermission('groups.groups.update') || hasPermission('groups.groups.update', group.id)
  const canDelete = hasPermission('groups.groups.delete')
  const canAdd = leads || hasPermission('groups.groups.add_member', group.id)
  const canRemove = leads || hasPermission('groups.groups.remove_member', group.id)
  const canSeeMembers = hasPermission('members.members.read')
  const canAudit = hasPermission('audit.audit.read')
  const refreshMembers = () => {
    queryClient.invalidateQueries({ queryKey: qk.groups.members(group.id) })
    queryClient.invalidateQueries({ queryKey: qk.groups.all })
  }
  const fail = (err: unknown) =>
    notify('error', t('common.error'), err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'))

  const add = (m: SlideOverMember) =>
    addGroupMember(group.id, m.id)
      .then(() => {
        refreshMembers()
        notify('success', t('groups.member.added'), t('groups.member.addedMsg', { member: m.name, group: group.name }))
      })
      .catch(fail)
  const remove = (m: SlideOverMember) =>
    removeGroupMember(group.id, m.id)
      .then(() => {
        refreshMembers()
        notify('info', t('groups.member.removed'), t('groups.member.removedMsg', { member: m.name, group: group.name }))
      })
      .catch(fail)
  const destroy = async () => {
    try {
      await deleteGroup(group.id)
      queryClient.invalidateQueries({ queryKey: qk.groups.all })
      queryClient.invalidateQueries({ queryKey: qk.lookups })
      notify('info', t('groups.group.deleted'), t('groups.group.deletedMsg', { name: group.name }))
      go(back)
    } catch (err) {
      fail(err)
    }
  }

  const groupFunctionOptions = allFunctions
    .filter((f) => f.perGroup)
    .map((f) => ({ value: String(f.id), label: f.name }))
  const refreshFunctions = () => {
    queryClient.invalidateQueries({ queryKey: [...qk.groups.members(group.id), 'functions'] })
    queryClient.invalidateQueries({ queryKey: qk.functions })
  }
  const assign = () => {
    if (!pickFunction || !pickMember) return
    assignHolder(Number(pickFunction), Number(pickMember), Number(group.id))
      .then(() => {
        refreshFunctions()
        setPickMember(null)
        notify('success', t('common.saved', 'Gespeichert'), t('groups.functions.assigned', 'Funktion vergeben'))
      })
      .catch(fail)
  }
  const unassign = (functionId: number, memberId: number) =>
    removeHolder(functionId, memberId, Number(group.id))
      .then(() => {
        refreshFunctions()
        notify('info', t('common.removed', 'Entfernt'), t('groups.functions.removed', 'Funktion entzogen'))
      })
      .catch(fail)

  const tabs = [
    { id: 'members', label: t('common.members', 'Mitglieder') },
    { id: 'functions', label: t('groups.functions.tab', 'Funktionen') },
    ...(canAudit ? [{ id: 'activity', label: t('members.detail.activity') }] : []),
  ]

  return (
    <div>
      <DetailBack to={back} label={backLabel} />
      <DetailHeader
        media={
          <DetailIcon color={group.color}>
            <IconBolt size={30} />
          </DetailIcon>
        }
        title={group.name}
        subtitle={group.description || undefined}
        badges={
          <>
            <VisibilityBadge visibility={group.visibility ?? 'visible'} />
            {group.isDefault && (
              <Badge variant="light" color="yellow" leftSection={<IconStar size={12} />} style={{ textTransform: 'none' }}>
                {t('groups.default.badge', 'Für neue Mitglieder')}
              </Badge>
            )}
            {group.sessions && (
              <Badge variant="light" leftSection={<IconClock size={12} />} style={{ textTransform: 'none' }}>
                {group.sessions}
              </Badge>
            )}
          </>
        }
        actions={
          <>
            {canEdit && (
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
            <DetailFact label={t('common.members', 'Mitglieder')}>
              <span className="num" data-testid="group-member-count">
                {membersLoading ? group.members : members.length}
              </span>
            </DetailFact>
            <DetailFact label={t('groups.lead', 'Gruppenleitung')}>{group.lead || '—'}</DetailFact>
            <DetailFact label={t('groups.sessions', 'Treffen')}>{group.sessions || '—'}</DetailFact>
          </>
        }
      />

      <div className="detail-grid">
        <DetailSection icon={<IconInfoCircle size={16} />} title={t('groups.detail.about', 'Gruppe')}>
          <DetailRow label={t('groups.lead', 'Gruppenleitung')}>
            {group.lead && group.leadId != null && canSeeMembers ? (
              <Anchor size="sm" onClick={() => go(`/app/members/${group.leadId}`)}>
                {group.lead}
              </Anchor>
            ) : (
              group.lead || <DetailEmpty />
            )}
          </DetailRow>
          <DetailRow label={t('groups.visibility.label', 'Sichtbarkeit')}>
            {t(`groups.visibility.${group.visibility ?? 'visible'}`)}
          </DetailRow>
          <DetailRow label={t('groups.sessions', 'Treffen')}>{group.sessions || <DetailEmpty />}</DetailRow>
          <DetailRow label={t('groups.roles.label', 'Gibt die Rollen')}>
            {group.roles?.length ? group.roles.map((r) => roleLabel(r.name)).join(', ') : <DetailEmpty />}
          </DetailRow>
          <DetailRow label={t('groups.tiers.label', 'Mitglieder dieser Stufen')}>
            {group.tiers?.length ? group.tiers.map((tier) => tier.name).join(', ') : <DetailEmpty />}
          </DetailRow>
          <DetailRow label={t('groups.default.short', 'Neue Mitglieder')}>
            {group.isDefault
              ? t('groups.default.yes', 'kommen in diese Gruppe')
              : t('groups.default.no', 'nicht automatisch')}
          </DetailRow>
          {group.parentGroupName && (
            <DetailRow label={t('groups.detail.parent', 'Gehört zu')}>
              {group.parentGroupId != null ? (
                <Anchor size="sm" onClick={() => go(`/app/groups/${group.parentGroupId}`)}>
                  {group.parentGroupName}
                </Anchor>
              ) : (
                group.parentGroupName
              )}
            </DetailRow>
          )}
          {group.emailAlias && (
            <DetailRow label={t('groups.detail.mail', 'Mailadresse')} mono>
              {group.emailAlias}
            </DetailRow>
          )}
        </DetailSection>

        <Paper withBorder p={{ base: 16, sm: 20 }} pt={8}>
          <Tabs tabs={tabs} activeTab={tab} onTabChange={setTab} />
          {tab === 'members' && (
            <MemberRoster
              members={roster}
              loading={membersLoading}
              addLabel={t('groups.addMember', 'Mitglied hinzufügen')}
              addPlaceholder={t('groups.searchMembersToAdd', 'Mitglieder suchen …')}
              searchResults={canAdd ? searchResults : undefined}
              onAdd={canAdd ? add : undefined}
              onAddSearch={canAdd ? setSearchQuery : undefined}
              onRemove={canRemove ? remove : undefined}
              onOpen={canSeeMembers ? (m) => go(`/app/members/${m.id}`) : undefined}
              testId="group-members"
            />
          )}
          {tab === 'functions' && (
            <Stack gap={10} mt={12} data-testid="group-functions">
              {groupFunctions.length === 0 && (
                <Text size="sm" c="dimmed">
                  {t(
                    'groups.functions.empty',
                    'Keine Funktion in dieser Gruppe besetzt. Gruppenfunktionen (zum Beispiel Trainer/in) legst du unter Mitglieder › Funktionen an.',
                  )}
                </Text>
              )}
              {groupFunctions.map((f) => (
                <Row key={`${f.functionId}:${f.memberId}`} justify="space-between" wrap="nowrap">
                  <div style={{ minWidth: 0 }}>
                    <Text size="sm" fw={600}>
                      {f.functionName}
                    </Text>
                    <Text size="sm">
                      {canSeeMembers ? (
                        <Anchor size="sm" onClick={() => go(`/app/members/${f.memberId}`)}>
                          {f.memberName}
                        </Anchor>
                      ) : (
                        f.memberName
                      )}
                      {f.roleNames.length > 0 && (
                        <Text span size="xs" c="dimmed">
                          {' · '}
                          {t('groups.functions.rolesHere', 'hier: {{roles}}', {
                            roles: f.roleNames.map(roleLabel).join(', '),
                          })}
                        </Text>
                      )}
                    </Text>
                  </div>
                  {canAssign && (
                    <ActionIcon
                      variant="subtle"
                      color="red"
                      aria-label={t('common.remove', 'Entfernen')}
                      onClick={() => unassign(f.functionId, f.memberId)}
                    >
                      <IconX size={16} />
                    </ActionIcon>
                  )}
                </Row>
              ))}
              {canAssign && groupFunctionOptions.length > 0 && (
                <Row align="flex-end" gap={8} wrap="wrap">
                  <Select
                    style={{ flex: '1 1 160px' }}
                    label={t('groups.functions.function', 'Funktion')}
                    data={groupFunctionOptions}
                    value={pickFunction}
                    onChange={setPickFunction}
                    data-testid="group-function-pick"
                  />
                  <div style={{ flex: '1 1 200px' }}>
                    <Text size="sm" fw={500} mb={4}>
                      {t('groups.functions.person', 'Person')}
                    </Text>
                    <MemberPicker value={pickMember ?? ''} onChange={(v) => setPickMember(v || null)} />
                  </div>
                  <Button onClick={assign} disabled={!pickFunction || !pickMember} data-testid="group-function-assign">
                    {t('functions.assignHolder', 'Person zuweisen')}
                  </Button>
                </Row>
              )}
            </Stack>
          )}
          {tab === 'activity' && <RecordActivity type="Group" id={group.id} testId="group-activity" />}
        </Paper>
      </div>

      {editOpen && <GroupFormModal key={group.id} target={group} onClose={() => setEditOpen(false)} />}
      <ConfirmModal
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        title={t('groups.confirmDelete.title', '«{{name}}» löschen?', { name: group.name })}
        body={t(
          'groups.confirmDelete.body',
          'Die Mitglieder bleiben erhalten, sie werden nur aus der Gruppe entfernt.',
        )}
        onConfirm={destroy}
      />
    </div>
  )
}
