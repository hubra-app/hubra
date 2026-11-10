import { useState } from 'react'
import { Button, Group } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useT } from '@/locales/i18n'
import { IconPlus, IconPencil, IconTrash, IconUserCog } from '@tabler/icons-react'
import { useToast, useAuth, useNav } from '@/context/AppContext'
import { ConfirmModal, LoadingSpinner, EmptyState, CardGrid, CardItem } from '@/components/ui'
import type { ClubFunction } from '@/types'
import { listFunctions, deleteFunction } from '@/api/functions'
import { qk } from '@/data/keys'
import { lookupsQuery } from '@/api/lookups'
import { roleLabel } from '@/roles'
import { FunctionFormModal } from './FunctionFormModal'

export function FunctionsTab() {
  const { notify } = useToast()
  const { hasPermission } = useAuth()
  const { t } = useT()
  const queryClient = useQueryClient()
  const canCreate = hasPermission('functions.functions.create')
  const canUpdate = hasPermission('functions.functions.update')
  const canDelete = hasPermission('functions.functions.delete')
  const { data: functions = [], isLoading: loading } = useQuery({
    queryKey: qk.functions,
    queryFn: () => listFunctions(),
  })
  const { go } = useNav()
  // The form: closed (null), a new function ('new') or one to change.
  const [formTarget, setFormTarget] = useState<ClubFunction | 'new' | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<ClubFunction | null>(null)
  const { data: lookups } = useQuery(lookupsQuery)
  const roleNames = (ids: number[]) =>
    ids
      .map((id) => lookups?.roles.get(id))
      .filter((name): name is string => !!name)
      .map(roleLabel)
      .join(', ') || null

  const openAdd = () => setFormTarget('new')
  const openEdit = (fn: ClubFunction) => setFormTarget(fn)

  const confirmDelete = async () => {
    if (!deleteTarget) return
    try {
      await deleteFunction(deleteTarget.id)
      queryClient.invalidateQueries({ queryKey: qk.functions })
      notify(
        'info',
        t('functions.deleted', 'Gelöscht'),
        t('functions.deletedMsg', 'Die Funktion wurde gelöscht.'),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    }
  }

  return (
    <div>
      {canCreate && (
        <Group justify="flex-end" mb={16} className="page-actions">
          <Button variant="filled" onClick={openAdd}>
            <IconPlus size={16} />
            {t('common.add', 'Hinzufügen')}
          </Button>
        </Group>
      )}
      {loading ? (
        <LoadingSpinner message={t('common.loading', 'Wird geladen …')} />
      ) : functions.length === 0 ? (
        <EmptyState
          title={t('functions.empty', 'Noch keine Funktionen.')}
          description={t(
            'functions.emptyHint',
            'Funktionen sind die Ämter im Verein, zum Beispiel Präsidium oder Kassier. Lege sie an und weise ihnen Mitglieder zu.',
          )}
        />
      ) : (
        <CardGrid columns={3}>
          {functions.map((fn) => (
            <CardItem
              key={fn.id}
              icon={
                <div
                  style={{
                    width: 40,
                    height: 40,
                    borderRadius: 10,
                    background: 'var(--hb-surface-2)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <IconUserCog size={18} color="var(--hb-text-2)" />
                </div>
              }
              title={fn.name}
              onClick={() => go(`/app/members/functions/${fn.id}`)}
              subtitle={
                [
                  fn.perGroup ? t('functions.perGroupBadge', 'Gruppenfunktion') : null,
                  fn.description,
                  roleNames(fn.grantsRoleIds)
                    ? t('functions.givesRoles', 'Gibt die Rollen {{roles}}', {
                        roles: roleNames(fn.grantsRoleIds),
                      })
                    : null,
                ]
                  .filter(Boolean)
                  .join(' · ') || undefined
              }
              footer={
                // The card opens the function; its buttons do only their own thing.
                <div style={{ display: 'flex', gap: 8 }} onClick={(e) => e.stopPropagation()}>
                  <Button
                    size="sm"
                    variant="subtle"
                    style={{ flex: 1 }}
                    onClick={() => go(`/app/members/functions/${fn.id}`)}
                  >
                    <IconUserCog size={16} />
                    {t('functions.holders', 'Besetzt durch')} (
                    {fn.perGroup ? fn.holders.length : `${fn.holders.length}/${fn.maxHolders}`})
                  </Button>
                  {canUpdate && (
                    <Button
                      size="sm"
                      variant="subtle"
                      onClick={() => openEdit(fn)}
                    >
                      <IconPencil size={16} />
                    </Button>
                  )}
                  {canDelete && (
                    <Button
                      size="sm"
                      variant="subtle"
                      style={{ color: 'var(--mantine-color-red-text)' }}
                      onClick={() => setDeleteTarget(fn)}
                    >
                      <IconTrash size={16} />
                    </Button>
                  )}
                </div>
              }
            >
              {fn.holders.length > 0 ? (
                <div
                  style={{
                    display: 'flex',
                    gap: 8,
                    flexWrap: 'wrap',
                    marginBottom: 4,
                  }}
                >
                  {fn.holders.map((h) => (
                    <span
                      key={`${h.memberId}:${h.groupId ?? ''}`}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 4,
                        fontSize: 'var(--mantine-font-size-xs)',
                        color: 'var(--hb-text)',
                        background: 'var(--hb-surface-2)',
                        borderRadius: 6,
                        padding: '3px 8px',
                      }}
                    >
                      {h.groupName ? `${h.memberName} · ${h.groupName}` : h.memberName}
                    </span>
                  ))}
                </div>
              ) : (
                <div
                  style={{
                    fontSize: 'var(--mantine-font-size-xs)',
                    color: 'var(--hb-text-3)',
                  }}
                >
                  {t('functions.noHolder', 'Unbesetzt')}
                </div>
              )}
            </CardItem>
          ))}
        </CardGrid>
      )}

      {formTarget && (
        <FunctionFormModal
          key={formTarget === 'new' ? 'new' : formTarget.id}
          target={formTarget}
          onClose={() => setFormTarget(null)}
        />
      )}
      <ConfirmModal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title={t('functions.deleteTitle', 'Funktion löschen?')}
        body={t(
          'functions.deleteBody',
          'Die Funktion wird gelöscht. Ihre Mail-Adressen werden entfernt.',
        )}
        onConfirm={confirmDelete}
      />
    </div>
  )
}
