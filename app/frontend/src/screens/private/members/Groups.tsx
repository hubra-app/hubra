import { useState } from 'react'
import { Badge, Button, SegmentedControl, Text, Paper, TextInput, UnstyledButton } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useT } from '@/locales/i18n'
import {
  IconPlus,
  IconClock,
  IconBolt,
  IconPencil,
  IconTrash,
  IconSearch,
} from '@tabler/icons-react'
import { useToast, useAuth, useNav } from '@/context/AppContext'
import { PageHead, ConfirmModal, usePagination, Pagination } from '@/components/ui'
import type { Group, GroupVisibility } from '@/types'
import { listGroups, deleteGroup } from '@/api/groups'
import { qk } from '@/data/keys'
import { GroupFormModal, VisibilityBadge } from './GroupFormModal'
import { VISIBILITIES } from './groupVisibility'

/* ── Groups ─────────────────────────────────── */
/** The groups; `embedded` leaves out the heading, for the tab under Mitglieder. */
export function GroupsScreen({ embedded = false }: { embedded?: boolean }) {
  const { notify } = useToast()
  const { currentUser, hasPermission } = useAuth()
  const { t } = useT()
  const queryClient = useQueryClient()
  const canCreate = hasPermission('groups.groups.create')
  const canUpdate = hasPermission('groups.groups.update')
  const leads = (g: Group) =>
    currentUser != null && g.leadId === Number(currentUser.id)
  const canDelete = hasPermission('groups.groups.delete')
  const { data: groups = [] } = useQuery({
    queryKey: qk.groups.all,
    queryFn: () => listGroups(),
  })
  const { go } = useNav()
  // The form: closed (null), a new group ('new') or one to change.
  const [formTarget, setFormTarget] = useState<Group | 'new' | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Group | null>(null)

  const [search, setSearch] = useState('')
  const [shown, setShown] = useState<'all' | GroupVisibility>('all')
  const filtered = groups.filter((g) => {
    const q = search.toLowerCase()
    return (
      (shown === 'all' || (g.visibility ?? 'visible') === shown) &&
      (!q ||
        g.name.toLowerCase().includes(q) ||
        g.description.toLowerCase().includes(q))
    )
  })
  const pg = usePagination(filtered, 10)

  const openAdd = () => setFormTarget('new')
  const openEdit = (g: Group) => setFormTarget(g)

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

  return (
    <div>
      {embedded ? (
        canCreate && (
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
            <Button variant="filled" onClick={openAdd}>
              <IconPlus size={16} />
              {t('groups.addGroup')}
            </Button>
          </div>
        )
      ) : (
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
      )}
      <Paper withBorder style={{ marginBottom: 0 }}>
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
          <SegmentedControl
            aria-label={t('groups.visibility.label', 'Sichtbarkeit')}
            value={shown}
            onChange={(v) => setShown(v as 'all' | GroupVisibility)}
            data={[
              { value: 'all', label: t('groups.visibility.all', 'Alle') },
              ...VISIBILITIES.map((v) => ({
                value: v,
                label: t(`groups.visibility.${v}`),
              })),
            ]}
          />
        </div>
        <Pagination {...pg} top />
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(min(280px, 100%), 1fr))',
            gap: 14,
            padding: 16,
          }}
        >
          {pg.paged.map((g) => (
            <Paper
              key={g.id}
              withBorder
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
                  <div style={{ minWidth: 0 }}>
                    <UnstyledButton
                      onClick={() => go(`/app/groups/${g.id}`)}
                      style={{
                        fontSize: 'var(--mantine-font-size-md)',
                        fontWeight: 700,
                        color: 'var(--hb-text)',
                      }}
                    >
                      {g.name}
                    </UnstyledButton>
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
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 14 }}>
                  <VisibilityBadge visibility={g.visibility ?? 'visible'} />
                  {g.sessions && (
                    <Badge variant="light">
                      <IconClock size={12} />
                      {g.sessions}
                    </Badge>
                  )}
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  {(canUpdate || hasPermission('groups.groups.update', g.id) || leads(g)) && (
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
                      style={{ color: 'var(--mantine-color-red-text)' }}
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
                    onClick={() => go(`/app/groups/${g.id}`)}
                  >
                    {t('groups.memberCount', '{{count}} Mitglieder', { count: g.members })} →
                  </Button>
                </div>
              </div>
            </Paper>
          ))}
          {pg.paged.length === 0 && !canCreate && (
            <Text size="sm" c="dimmed" ta="center" py="xl" style={{ gridColumn: '1 / -1' }}>
              {search
                ? t('groups.noMatch', 'Keine Gruppen gefunden.')
                : t('groups.empty', 'Noch keine Gruppen.')}
            </Text>
          )}
          {canCreate && (
          <Paper
            component="button"
            type="button"
            withBorder
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
            <IconPlus size={24} style={{ color: 'var(--hb-text-3)', marginBottom: 8 }} />
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
      {formTarget && (
        <GroupFormModal
          key={formTarget === 'new' ? 'new' : formTarget.id}
          target={formTarget}
          onClose={() => setFormTarget(null)}
        />
      )}
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
