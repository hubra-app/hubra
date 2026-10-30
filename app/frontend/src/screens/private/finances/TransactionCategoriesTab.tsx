import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Table, Button, Group, Paper, TextInput, Badge } from '@mantine/core'
import { useT } from '@/locales/i18n'
import { IconPlus, IconTrash, IconPencil, IconLock } from '@tabler/icons-react'
import { useToast, useAuth } from '@/context/AppContext'
import { Modal, Field, ConfirmModal, EmptyState } from '@/components/ui'
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
    'transaction_categories.transaction_categories.create',
  )
  const canUpdate = hasPermission(
    'transaction_categories.transaction_categories.update',
  )
  const canDelete = hasPermission(
    'transaction_categories.transaction_categories.delete',
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
  const [cColor, setCColor] = useState('#2596be')

  const openAdd = () => {
    setCName('')
    setCColor('#2596be')
    setAddOpen(true)
  }
  // A new club has no categories: offer the usual ones in one go.
  const [starting, setStarting] = useState(false)
  const createStarterSet = async () => {
    const starter = [
      { name: t('finance.starter.fees', 'Mitgliederbeiträge'), color: '#7441e0' },
      { name: t('finance.starter.donations', 'Spenden'), color: '#1f9d57' },
      { name: t('finance.starter.events', 'Anlässe'), color: '#2596be' },
      { name: t('finance.starter.material', 'Material'), color: '#f59e0b' },
      { name: t('finance.starter.rent', 'Miete'), color: '#ff4d3d' },
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
        <Paper withBorder shadow="sm" radius="lg">
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
        <Paper withBorder shadow="sm" radius="lg">
          <div style={{ overflowX: 'auto' }}>
            <Table highlightOnHover className="responsive-table">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>{t('finance.categoryLabel', 'Kategorie')}</Table.Th>
                  <Table.Th>{t('common.type', 'Typ')}</Table.Th>
                  <Table.Th style={{ width: 80 }}></Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {loading ? (
                  <Table.Tr>
                    <Table.Td
                      colSpan={3}
                      style={{
                        textAlign: 'center',
                        color: 'var(--hb-text-3)',
                        padding: '24px',
                        fontSize: 'var(--mantine-font-size-sm)',
                      }}
                    >
                      {t('finance.loading', 'Wird geladen …')}
                    </Table.Td>
                  </Table.Tr>
                ) : cats.length === 0 ? (
                  <Table.Tr>
                    <Table.Td
                      colSpan={3}
                      style={{
                        textAlign: 'center',
                        color: 'var(--hb-text-3)',
                        padding: '24px',
                        fontSize: 'var(--mantine-font-size-sm)',
                      }}
                    >
                      {t('finance.noCategories', 'Noch keine Kategorien.')}
                    </Table.Td>
                  </Table.Tr>
                ) : (
                  cats.map((c) => (
                    <Table.Tr key={c.id}>
                      <Table.Td data-label={t('finance.categoryLabel', 'Kategorie')}>
                        <div
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 10,
                          }}
                        >
                          <div
                            style={{
                              width: 12,
                              height: 12,
                              borderRadius: 3,
                              background: c.color,
                              flexShrink: 0,
                            }}
                          />
                          <span style={{ fontWeight: 500 }}>{c.name}</span>
                        </div>
                      </Table.Td>
                      <Table.Td data-label={t('common.type', 'Typ')}>
                        {c.isDefault ? (
                          <Badge
                            variant="light"
                            color="cyan"
                            radius="xl"
                            style={{ fontSize: 'var(--mantine-font-size-xs)' }}
                          >
                            {t('finance.category.default', 'Standard')}
                          </Badge>
                        ) : (
                          <span
                            style={{
                              fontSize: 'var(--mantine-font-size-xs)',
                              color: 'var(--hb-text-3)',
                            }}
                          >
                            {t('finance.category.custom', 'Eigene')}
                          </span>
                        )}
                      </Table.Td>
                      <Table.Td data-label="">
                        <div style={{ display: 'flex', gap: 4 }}>
                          {canUpdate && (
                            <Button
                              size="sm"
                              variant="subtle"
                              onClick={() => openEdit(c)}
                              disabled={c.isDefault}
                              title={
                                c.isDefault
                                  ? t(
                                      'finance.defaultCannotEdit',
                                      'Standardkategorien können nicht bearbeitet werden',
                                    )
                                  : undefined
                              }
                            >
                              {c.isDefault ? (
                                <IconLock
                                  size={16}
                                  style={{ color: 'var(--hb-text-3)' }}
                                />
                              ) : (
                                <IconPencil size={16} />
                              )}
                            </Button>
                          )}
                          {canDelete && (
                            <Button
                              size="sm"
                              variant="subtle"
                              style={{
                                color: c.isDefault ? '#8c86a0' : '#ff4d3d',
                              }}
                              onClick={() => {
                                if (!c.isDefault) setDeleteTarget(c)
                              }}
                              disabled={c.isDefault}
                              title={
                                c.isDefault
                                  ? t(
                                      'finance.defaultCannotDelete',
                                      'Standardkategorien können nicht gelöscht werden',
                                    )
                                  : undefined
                              }
                            >
                              <IconTrash size={16} />
                            </Button>
                          )}
                        </div>
                      </Table.Td>
                    </Table.Tr>
                  ))
                )}
              </Table.Tbody>
            </Table>
          </div>
        </Paper>
      )}

      <Modal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title={t('finance.newCategory', 'Neue Kategorie')}
        footer={
          <>
            <Button variant="default" onClick={() => setAddOpen(false)}>
              {t('common.cancel', 'Abbrechen')}
            </Button>
            <Button variant="filled" onClick={saveAdd}>
              {t('common.create', 'Erstellen')}
            </Button>
          </>
        }
      >
        {catForm}
      </Modal>
      <Modal
        open={!!editTarget}
        onClose={() => setEditTarget(null)}
        title={t('finance.editCategory', 'Kategorie bearbeiten')}
        subtitle={editTarget?.name}
        footer={
          <>
            <Button variant="default" onClick={() => setEditTarget(null)}>
              {t('common.cancel', 'Abbrechen')}
            </Button>
            <Button variant="filled" onClick={saveEdit}>
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
