import { useState, useMemo } from 'react'
import {
  Badge,
  Button,
  Switch,
  Paper,
  Textarea,
  TextInput,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { zod4Resolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useT, zmsg } from '@/locales/i18n'
import {
  IconPlus,
  IconClock,
  IconBolt,
  IconPencil,
  IconTrash,
  IconSearch,
} from '@tabler/icons-react'
import { useToast, useAuth } from '@/context/AppContext'
import {
  PageHead,
  Modal,
  Field,
  MemberSlideOver,
  type SlideOverMember,
  ConfirmModal,
  usePagination,
  Pagination,
  useSubmitOnce,
} from '@/components/ui'
import type { Group } from '@/types'
import {
  listGroups,
  createGroup,
  updateGroup,
  deleteGroup,
  addGroupMember,
  removeGroupMember,
} from '@/api/groups'
import { listGroupMembers } from '@/api/members'
import { MemberPicker } from '@/components/MemberPicker'
import { useMemberSearch } from '@/data/members'
import { qk } from '@/data/keys'

/* ── Group Detail Panel ──────────────────────── */
function GroupDetailPanel({
  group,
  onClose,
}: {
  group: Group
  onClose: () => void
}) {
  const { notify } = useToast()
  const { hasPermission } = useAuth()
  const { t } = useT()
  const queryClient = useQueryClient()
  // A role held for this group only counts here too.
  const canAdd = hasPermission('groups.groups.add_member', group.id)
  const canRemove = hasPermission('groups.groups.remove_member', group.id)
  const { data: members = [], isLoading: loading } = useQuery({
    queryKey: qk.groups.members(group.id),
    queryFn: () => listGroupMembers(group.id),
  })
  const [searchQuery, setSearchQuery] = useState('')
  const { data: searchData } = useMemberSearch(searchQuery, { enabled: searchQuery.length >= 2 })

  const slideMembers: SlideOverMember[] = useMemo(
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
      .map((m) => ({
        id: m.id,
        name: m.name,
        email: m.email,
        avatarColor: m.avatarColor,
        tier: m.tier,
      }))
  }, [searchData, members, searchQuery])

  const handleAdd = (m: SlideOverMember) => {
    addGroupMember(group.id, m.id)
      .then(() => {
        queryClient.invalidateQueries({
          queryKey: qk.groups.members(group.id),
        })
        notify(
          'success',
          t('groups.member.added'),
          t('groups.member.addedMsg', { member: m.name, group: group.name }),
        )
      })
      .catch((err: unknown) =>
        notify(
          'error',
          t('common.error'),
          err instanceof Error
            ? err.message
            : t('common.unknownError', 'Unbekannter Fehler'),
        ),
      )
  }

  const handleRemove = (m: SlideOverMember) => {
    removeGroupMember(group.id, m.id)
      .then(() => {
        queryClient.invalidateQueries({
          queryKey: qk.groups.members(group.id),
        })
        notify(
          'info',
          t('groups.member.removed'),
          t('groups.member.removedMsg', { member: m.name, group: group.name }),
        )
      })
      .catch((err: unknown) =>
        notify(
          'error',
          t('common.error'),
          err instanceof Error
            ? err.message
            : t('common.unknownError', 'Unbekannter Fehler'),
        ),
      )
  }

  return (
    <MemberSlideOver
      title={group.name}
      subtitle={group.description}
      icon={
        <div
          style={{
            width: 12,
            height: 12,
            borderRadius: 3,
            background: group.color,
          }}
        />
      }
      members={slideMembers}
      loading={loading}
      addLabel={t('groups.addMember', 'Mitglied hinzufügen')}
      addPlaceholder={t('groups.searchMembersToAdd', 'Mitglieder suchen …')}
      searchResults={canAdd ? searchResults : undefined}
      onAdd={canAdd ? handleAdd : undefined}
      onAddSearch={canAdd ? setSearchQuery : undefined}
      onRemove={canRemove ? handleRemove : undefined}
      showRemove={canRemove}
      onClose={onClose}
    />
  )
}

/* ── Groups ─────────────────────────────────── */
const groupSchema = z.object({
  name: z.string().min(1, zmsg('common.nameRequired', 'Name ist erforderlich')),
  description: z.string(),
  color: z.string(),
  sessions: z.string(),
  tools: z.number(),
  leadId: z.string(),
  selfJoin: z.boolean(),
})
type GroupForm = z.infer<typeof groupSchema>

export function GroupsScreen() {
  const { notify } = useToast()
  const { hasPermission } = useAuth()
  const { t } = useT()
  const queryClient = useQueryClient()
  const canCreate = hasPermission('groups.groups.create')
  const canUpdate = hasPermission('groups.groups.update')
  const canDelete = hasPermission('groups.groups.delete')
  const { data: groups = [] } = useQuery({
    queryKey: qk.groups.all,
    queryFn: () => listGroups(),
  })
  const [addOpen, setAddOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<Group | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Group | null>(null)
  const [detailGroup, setDetailGroup] = useState<Group | null>(null)

  const form = useForm<GroupForm>({
    validate: zod4Resolver(groupSchema),
    initialValues: {
      name: '',
      description: '',
      color: '#2596be',
      sessions: '',
      tools: 0,
      leadId: '',
      selfJoin: false,
    },
  })

  const [search, setSearch] = useState('')
  const filtered = groups.filter((g) => {
    const q = search.toLowerCase()
    return (
      !q ||
      g.name.toLowerCase().includes(q) ||
      g.description.toLowerCase().includes(q)
    )
  })
  const pg = usePagination(filtered, 10)

  const openAdd = () => {
    form.setValues({
      name: '',
      description: '',
      color: '#2596be',
      sessions: '',
      tools: 0,
      leadId: '',
      selfJoin: false,
    })
    setAddOpen(true)
  }
  const openEdit = (g: Group) => {
    setEditTarget(g)
    form.setValues({
      name: g.name,
      description: g.description,
      color: g.color,
      sessions: g.sessions,
      tools: g.tools,
      leadId: '',
      selfJoin: g.selfJoin ?? false,
    })
  }

  const saveAdd = async (data: GroupForm) => {
    try {
      await createGroup({
        name: data.name,
        description: data.description,
        color: data.color,
        sessions: data.sessions,
        tools: data.tools,
        leadId: data.leadId ? Number(data.leadId) : undefined,
        selfJoin: data.selfJoin,
      })
      queryClient.invalidateQueries({ queryKey: qk.groups.all })
      queryClient.invalidateQueries({ queryKey: qk.lookups })
      setAddOpen(false)
      notify(
        'success',
        t('groups.group.saved'),
        t('groups.group.createdMsg', { name: data.name }),
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
  const [submitAdd, adding] = useSubmitOnce(saveAdd)

  const saveEdit = async (data: GroupForm) => {
    if (!editTarget) return
    try {
      await updateGroup(editTarget.id, {
        name: data.name,
        description: data.description,
        color: data.color,
        sessions: data.sessions,
        tools: data.tools,
        ...(data.leadId ? { leadId: Number(data.leadId) } : {}),
        selfJoin: data.selfJoin,
      })
      queryClient.invalidateQueries({ queryKey: qk.groups.all })
      queryClient.invalidateQueries({ queryKey: qk.lookups })
      setEditTarget(null)
      notify(
        'success',
        t('groups.group.saved'),
        t('groups.group.updatedMsg', { name: data.name }),
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

  const confirmDelete = async () => {
    if (!deleteTarget) return
    try {
      await deleteGroup(deleteTarget.id)
      queryClient.invalidateQueries({ queryKey: qk.groups.all })
      queryClient.invalidateQueries({ queryKey: qk.lookups })
      notify(
        'info',
        t('groups.group.deleted'),
        t('groups.group.deletedMsg', { name: deleteTarget.name }),
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

  const groupForm = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Field label={t('groups.group.name', 'Name der Gruppe')}>
        <TextInput
          {...form.getInputProps('name')}
          placeholder={t('groups.group.namePlaceholder', 'z. B. Keramik')}
        />
      </Field>
      <Field label={t('common.description', 'Beschreibung')}>
        <Textarea
          rows={3}
          {...form.getInputProps('description')}
          placeholder={t(
            'common.descriptionPlaceholder',
            'Kurze Beschreibung …',
          )}
        />
      </Field>
      <Field label={t('common.color', 'Farbe')}>
        <TextInput
          type="color"
          {...form.getInputProps('color')}
          style={{ height: 38, padding: '2px 6px', cursor: 'pointer' }}
        />
      </Field>
      <Field label={t('groups.lead', 'Gruppenleitung')}>
        <MemberPicker
          noneLabel={t('groups.noLead', 'Keine Leitung')}
          {...form.getInputProps('leadId')}
          onChange={(id) => form.setFieldValue('leadId', id ?? '')}
        />
      </Field>
      <div
        className="grid-2"
        style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}
      >
        <Field
          label={t('groups.sessions', 'Treffen')}
          hint={t('groups.sessionsHint', 'z. B. 2× pro Woche')}
        >
          <TextInput
            {...form.getInputProps('sessions')}
            placeholder={t('groups.sessionsPlaceholder', '3× pro Woche')}
          />
        </Field>
        <Field label={t('groups.tools', 'Werkzeuge')}>
          <TextInput
            type="number"
            min={0}
            {...form.getInputProps('tools', { valueAsNumber: true })}
            placeholder="0"
          />
        </Field>
      </div>
      <Switch
        label={t('groups.selfJoin', 'Mitglieder können selbst beitreten und austreten')}
        description={t(
          'groups.selfJoinHint',
          'Für Interessengruppen. Mitglieder finden sie unter «Mein Konto».',
        )}
        {...form.getInputProps('selfJoin', { type: 'checkbox' })}
      />
    </div>
  )

  return (
    <div>
      <PageHead
        title={t('groups.title')}
        desc={t('groups.count', '{{count}} Gruppen', { count: groups.length })}
        actions={
          canCreate && (
            <Button variant="filled" onClick={openAdd}>
              <IconPlus size={16} />
              {t('groups.addGroup')}
            </Button>
          )
        }
      />
      <Paper withBorder shadow="sm" radius="lg" style={{ marginBottom: 0 }}>
        <div
          style={{
            padding: '14px 16px',
            borderBottom: '1px solid var(--hb-border)',
            display: 'flex',
            gap: 10,
            flexWrap: 'wrap',
            alignItems: 'center',
          }}
        >
          <TextInput
            style={{ flex: '1 1 220px' }}
            leftSection={<IconSearch size={16} />}
            placeholder={t('groups.search', 'Gruppen suchen …')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Pagination {...pg} top />
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
            gap: 14,
            padding: 16,
          }}
        >
          {pg.paged.map((g) => (
            <Paper
              key={g.id}
              withBorder
              shadow="sm"
              radius="lg"
              style={{ overflow: 'hidden' }}
            >
              <div style={{ height: 4, background: g.color }} />
              <div style={{ padding: '18px 20px' }}>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 12,
                    marginBottom: 12,
                  }}
                >
                  <div
                    style={{
                      width: 42,
                      height: 42,
                      borderRadius: 10,
                      background: g.color,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                    }}
                  >
                    <IconBolt size={20} color="white" />
                  </div>
                  <div>
                    <div
                      style={{
                        fontSize: 'var(--mantine-font-size-md)',
                        fontWeight: 700,
                        color: 'var(--hb-text)',
                      }}
                    >
                      {g.name}
                    </div>
                    {g.lead && (
                      <div
                        style={{
                          fontSize: 'var(--mantine-font-size-sm)',
                          color: 'var(--hb-text-2)',
                        }}
                      >
                        {t('groups.ledBy', 'Geleitet von')} {g.lead}
                      </div>
                    )}
                  </div>
                </div>
                <p
                  style={{
                    fontSize: 'var(--mantine-font-size-sm)',
                    color: 'var(--hb-text-2)',
                    margin: '0 0 14px',
                    lineHeight: 1.5,
                  }}
                >
                  {g.description ||
                    t('groups.noDescription', 'Keine Beschreibung.')}
                </p>
                <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
                  {g.sessions && (
                    <Badge variant="light">
                      <IconClock size={12} />
                      {g.sessions}
                    </Badge>
                  )}
                  {g.tools > 0 && (
                    <Badge variant="light">
                      <IconBolt size={12} />
                      {g.tools} {t('groups.tools', 'Werkzeuge')}
                    </Badge>
                  )}
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  {(canUpdate || hasPermission('groups.groups.update', g.id)) && (
                    <Button
                      size="sm"
                      variant="subtle"
                      aria-label={t('common.edit', 'Bearbeiten')}
                      title={t('common.edit', 'Bearbeiten')}
                      onClick={() => openEdit(g)}
                    >
                      <IconPencil size={16} />
                    </Button>
                  )}
                  {canDelete && (
                    <Button
                      size="sm"
                      variant="subtle"
                      style={{ color: '#ff4d3d' }}
                      aria-label={t('common.delete', 'Löschen')}
                      title={t('common.delete', 'Löschen')}
                      onClick={() => setDeleteTarget(g)}
                    >
                      <IconTrash size={16} />
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="subtle"
                    style={{ color: 'var(--mantine-color-acc-7)', marginLeft: 'auto' }}
                    onClick={() => setDetailGroup(g)}
                  >
                    {t('groups.memberCount', '{{count}} Mitglieder', { count: g.members })} →
                  </Button>
                </div>
              </div>
            </Paper>
          ))}
          {canCreate && (
          <Paper
            component="button"
            type="button"
            withBorder
            shadow="sm"
            radius="lg"
            style={{
              font: 'inherit',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: 28,
              cursor: 'pointer',
              border: '1.5px dashed var(--hb-border)',
              background: 'transparent',
            }}
            onClick={openAdd}
          >
            <IconPlus size={22} style={{ color: '#b7b0c9', marginBottom: 8 }} />
            <span
              style={{
                fontSize: 'var(--mantine-font-size-sm)',
                color: 'var(--hb-text-3)',
              }}
            >
              {t('groups.addGroup')}
            </span>
          </Paper>
          )}
        </div>
        <Pagination {...pg} />
      </Paper>
      {detailGroup && (
        <GroupDetailPanel
          group={detailGroup}
          onClose={() => setDetailGroup(null)}
        />
      )}

      <Modal
        onSubmit={form.onSubmit(submitAdd)}
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title={t('groups.addGroup')}
        footer={
          <>
            <Button variant="default" onClick={() => setAddOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button variant="filled" type="submit" loading={adding}>
              {t('groups.createGroup', 'Gruppe erstellen')}
            </Button>
          </>
        }
      >
        {groupForm}
      </Modal>
      <Modal
        onSubmit={form.onSubmit(saveEdit)}
        open={!!editTarget}
        onClose={() => setEditTarget(null)}
        title={t('groups.editGroup')}
        subtitle={editTarget?.name}
        footer={
          <>
            <Button variant="default" onClick={() => setEditTarget(null)}>
              {t('common.cancel')}
            </Button>
            <Button variant="filled" type="submit">
              {t('common.save')}
            </Button>
          </>
        }
      >
        {groupForm}
      </Modal>
      <ConfirmModal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title={t('groups.confirmDelete.title', '«{{name}}» löschen?', {
          name: deleteTarget?.name ?? '',
        })}
        body={t(
          'groups.confirmDelete.body',
          'Die Mitglieder bleiben erhalten, sie werden nur aus der Gruppe entfernt.',
        )}
        onConfirm={confirmDelete}
      />
    </div>
  )
}
