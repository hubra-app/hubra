import { categoryColors } from '@hubra/ui'
import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Group, Paper, TextInput, Badge } from '@mantine/core'
import { useT } from '@/locales/i18n'
import { IconPlus, IconTrash, IconPencil, IconLock } from '@tabler/icons-react'
import { useToast, useAuth } from '@/context/AppContext'
import { Modal, Field, ConfirmModal, EmptyState, SimpleList } from '@/components/ui'
import type { TransactionCategory } from '@/types'
import {
  listTxCategories,
  createTxCategory,
  updateTxCategory,
  deleteTxCategory,
} from '@/api/finance'
import { qk } from '@/data/keys'

/* ── Transaction Categories ──────────────────── */
export function TransactionCategoriesTab() {
  const { t } = useT()
  const { notify } = useToast()
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const canCreate = hasPermission(
    'finance.transaction_categories.create',
  )
  const canUpdate = hasPermission(
    'finance.transaction_categories.update',
  )
  const canDelete = hasPermission(
    'finance.transaction_categories.delete',
  )
  const { data: cats = [], isLoading: loading } = useQuery({
    queryKey: qk.transactions.categories,
    queryFn: () => listTxCategories(),
  })
  const [addOpen, setAddOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<TransactionCategory | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<TransactionCategory | null>(
    null,
  )
  const [cName, setCName] = useState('')
  const [cColor, setCColor] = useState<string>(categoryColors.blue)

  const openAdd = () => {
    setCName('')
    setCColor(categoryColors.blue)
    setAddOpen(true)
  }
  // A new club has no categories: offer the usual ones in one go.
  const [starting, setStarting] = useState(false)
  const createStarterSet = async () => {
    const starter = [
      { name: t('finance.starter.fees', 'Mitgliederbeiträge'), color: categoryColors.purple },
      { name: t('finance.starter.donations', 'Spenden'), color: categoryColors.green },
      { name: t('finance.starter.events', 'Anlässe'), color: categoryColors.blue },
      { name: t('finance.starter.material', 'Material'), color: categoryColors.orange },
      { name: t('finance.starter.rent', 'Miete'), color: categoryColors.red },
      { name: t('finance.starter.other', 'Diverses'), color: 'var(--hb-text-3)' },
    ]
    setStarting(true)
    try {
      for (const c of starter) await createTxCategory(c)
      notify(
        'success',
        t('finance.starterCreated', 'Kategorien angelegt'),
        t('finance.starterCreatedMsg', 'Du kannst sie jederzeit umbenennen oder löschen.'),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('finance.couldNotCreateCategory', 'Kategorie konnte nicht erstellt werden.'),
        err instanceof Error ? err.message : undefined,
      )
    } finally {
      queryClient.invalidateQueries({ queryKey: qk.transactions.categories })
      setStarting(false)
    }
  }
  const openEdit = (c: TransactionCategory) => {
    setEditTarget(c)
    setCName(c.name)
    setCColor(c.color)
  }

  const saveAdd = async () => {
    if (!cName) return
    try {
      await createTxCategory({ name: cName, color: cColor })
      queryClient.invalidateQueries({ queryKey: qk.transactions.categories })
      setAddOpen(false)
      notify(
        'success',
        t('finance.category.created', 'Kategorie erstellt'),
        t('finance.category.createdMsg', '«{{name}}» ist jetzt verfügbar.', {
          name: cName,
        }),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error', 'Fehler'),
        err instanceof Error
          ? err.message
          : t(
              'finance.couldNotCreateCategory',
              'Kategorie konnte nicht erstellt werden.',
            ),
      )
    }
  }

  const saveEdit = async () => {
    if (!editTarget) return
    try {
      await updateTxCategory(editTarget.id, {
        name: cName,
        color: cColor,
      })
      queryClient.invalidateQueries({ queryKey: qk.transactions.categories })
      setEditTarget(null)
      notify(
        'success',
        t('finance.category.updated', 'Kategorie gespeichert'),
        t('finance.category.savedMsg', '«{{name}}» wurde gespeichert.', {
          name: cName,
        }),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error', 'Fehler'),
        err instanceof Error
          ? err.message
          : t(
              'finance.couldNotUpdateCategory',
              'Kategorie konnte nicht gespeichert werden.',
            ),
      )
    }
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    try {
      await deleteTxCategory(deleteTarget.id)
      queryClient.invalidateQueries({ queryKey: qk.transactions.categories })
      notify(
        'info',
        t('finance.category.deleted', 'Kategorie gelöscht.'),
        t('finance.category.removedMsg', '«{{name}}» wurde gelöscht.', {
          name: deleteTarget.name,
        }),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error', 'Fehler'),
        err instanceof Error
          ? err.message
          : t(
              'finance.couldNotDeleteCategory',
              'Kategorie konnte nicht gelöscht werden.',
            ),
      )
    }
  }

  const catForm = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div
        style={{ display: 'grid', gridTemplateColumns: '1fr 72px', gap: 12 }}
      >
        <Field label={t('finance.category.name', 'Name')}>
          <TextInput
            value={cName}
            onChange={(e) => setCName(e.target.value)}
            placeholder={t('finance.category.namePlaceholder', 'z. B. Material')}
          />
        </Field>
        <Field label={t('finance.category.color', 'Farbe')}>
          <TextInput
            type="color"
            value={cColor}
            onChange={(e) => setCColor(e.target.value)}
            style={{ height: 38, padding: '2px 6px', cursor: 'pointer' }}
          />
        </Field>
      </div>
    </div>
  )

  return (
    <div>
      {canCreate && (
        <Group justify="flex-end" mb={16} className="page-actions">
          <Button variant="filled" onClick={openAdd}>
            <IconPlus size={16} />
            {t('finance.newCategory', 'Neue Kategorie')}
          </Button>
        </Group>
      )}
      {!loading && cats.length === 0 && canCreate ? (
        <Paper withBorder>
          <EmptyState
            title={t('finance.noCategories', 'Noch keine Kategorien.')}
            description={t(
              'finance.noCategoriesWhy',
              'Jede Buchung gehört zu einer Kategorie. Lege eigene an oder starte mit einer Auswahl.',
            )}
          />
          <Group justify="center" gap="xs" pb="xl" px="md" mt={-32}>
            <Button onClick={createStarterSet} loading={starting}>
              {t('finance.createStarterCategories', 'Übliche Kategorien anlegen')}
            </Button>
          </Group>
        </Paper>
      ) : (
        <SimpleList
          items={cats}
          loading={loading}
          emptyMessage={t('finance.noCategories', 'Noch keine Kategorien.')}
          getKey={(c) => c.id}
          row={(c) => ({
            leading: (
              <span
                style={{ width: 12, height: 12, borderRadius: 3, background: c.color }}
                aria-hidden
              />
            ),
            title: c.name,
            meta: c.isDefault ? (
              <Badge variant="light" color="acc" radius="xl" style={{ fontSize: 'var(--mantine-font-size-xs)' }}>
                {t('finance.category.default', 'Standard')}
              </Badge>
            ) : (
              <span style={{ fontSize: 'var(--mantine-font-size-xs)', color: 'var(--hb-text-3)' }}>
                {t('finance.category.custom', 'Eigene')}
              </span>
            ),
            actions:
              canUpdate || canDelete ? (
                <>
                  {canUpdate && (
                    <Button
                      size="sm"
                      variant="subtle"
                      onClick={() => openEdit(c)}
                      disabled={c.isDefault}
                      aria-label={t('common.edit', 'Bearbeiten')}
                      title={
                        c.isDefault
                          ? t('finance.defaultCannotEdit', 'Standardkategorien können nicht bearbeitet werden')
                          : t('common.edit', 'Bearbeiten')
                      }
                    >
                      {c.isDefault ? (
                        <IconLock size={16} style={{ color: 'var(--hb-text-3)' }} />
                      ) : (
                        <IconPencil size={16} />
                      )}
                    </Button>
                  )}
                  {canDelete && (
                    <Button
                      size="sm"
                      variant="subtle"
                      style={{ color: c.isDefault ? 'var(--hb-text-3)' : 'var(--mantine-color-red-text)' }}
                      onClick={() => {
                        if (!c.isDefault) setDeleteTarget(c)
                      }}
                      disabled={c.isDefault}
                      aria-label={t('common.delete', 'Löschen')}
                      title={
                        c.isDefault
                          ? t('finance.defaultCannotDelete', 'Standardkategorien können nicht gelöscht werden')
                          : t('common.delete', 'Löschen')
                      }
                    >
                      <IconTrash size={16} />
                    </Button>
                  )}
                </>
              ) : undefined,
          })}
        />
      )}

      <Modal
        onSubmit={(e) => {
          e?.preventDefault()
          saveAdd()
        }}
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title={t('finance.newCategory', 'Neue Kategorie')}
        footer={
          <>
            <Button variant="default" onClick={() => setAddOpen(false)}>
              {t('common.cancel', 'Abbrechen')}
            </Button>
            <Button variant="filled" type="submit">
              {t('common.create', 'Erstellen')}
            </Button>
          </>
        }
      >
        {catForm}
      </Modal>
      <Modal
        onSubmit={(e) => {
          e?.preventDefault()
          saveEdit()
        }}
        open={!!editTarget}
        onClose={() => setEditTarget(null)}
        title={t('finance.editCategory', 'Kategorie bearbeiten')}
        subtitle={editTarget?.name}
        footer={
          <>
            <Button variant="default" onClick={() => setEditTarget(null)}>
              {t('common.cancel', 'Abbrechen')}
            </Button>
            <Button variant="filled" type="submit">
              {t('common.save', 'Speichern')}
            </Button>
          </>
        }
      >
        {catForm}
      </Modal>
      <ConfirmModal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title={t('finance.deleteCategoryTitle', '«{{name}}» löschen?', {
          name: deleteTarget?.name ?? '',
        })}
        body={t(
          'finance.deleteCategoryBody',
          'Buchungen mit dieser Kategorie sind danach ohne Kategorie.',
        )}
        onConfirm={confirmDelete}
      />
    </div>
  )
}
