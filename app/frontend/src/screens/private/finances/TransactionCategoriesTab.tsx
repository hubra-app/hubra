import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Table, Button, Group, Paper, TextInput, Badge } from '@mantine/core'
import { useT } from '@/locales/i18n'
import { IconPlus, IconTrash, IconPencil, IconLock } from '@tabler/icons-react'
import { useToast, useAuth } from '@/context/AppContext'
import { Modal, Field, ConfirmModal } from '@/components/ui'
import type { TransactionCategory } from '@/types'
import {
  listTxCategories,
  createTxCategory,
  updateTxCategory,
  deleteTxCategory,
} from '@/api/finance'

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
    queryKey: ['transaction-categories'],
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
  const openEdit = (c: TransactionCategory) => {
    setEditTarget(c)
    setCName(c.name)
    setCColor(c.color)
  }

  const saveAdd = async () => {
    if (!cName) return
    try {
      await createTxCategory({ name: cName, color: cColor })
      queryClient.invalidateQueries({ queryKey: ['transaction-categories'] })
      setAddOpen(false)
      notify(
        'success',
        t('finance.category.created', 'Kategorie erstellt'),
        t('finance.category.createdMsg', '"{{name}}" isch jetzt verfüegbar.', {
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
              'Kategorie chonnt nöd erstellt wärde.',
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
      queryClient.invalidateQueries({ queryKey: ['transaction-categories'] })
      setEditTarget(null)
      notify(
        'success',
        t('finance.category.updated', 'Kategorie aktualisiert'),
        t('finance.category.savedMsg', '"{{name}}" isch gspeicheret.', {
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
              'Kategorie chonnt nöd aktualisiert wärde.',
            ),
      )
    }
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    try {
      await deleteTxCategory(deleteTarget.id)
      queryClient.invalidateQueries({ queryKey: ['transaction-categories'] })
      notify(
        'info',
        t('finance.category.deleted', 'Kategorie gösche'),
        t('finance.category.removedMsg', '"{{name}}" isch entfern worde.', {
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
              'Kategorie chonnt nöd gösche wärde.',
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
            placeholder={t('finance.category.namePlaceholder', 'z.B. Material')}
          />
        </Field>
        <Field label={t('finance.category.color', 'Farb')}>
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
        <Group justify="flex-end" mb={16}>
          <Button variant="filled" onClick={openAdd}>
            <IconPlus size={16} />
            {t('finance.newCategory', 'Neui Kategorie')}
          </Button>
        </Group>
      )}
      <Paper withBorder shadow="sm" radius="lg">
        <div style={{ overflowX: 'auto' }}>
          <Table highlightOnHover className="responsive-table">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('finance.category', 'Kategorie')}</Table.Th>
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
                      color: '#99a2ac',
                      padding: '24px',
                      fontSize: 'var(--mantine-font-size-sm)',
                    }}
                  >
                    {t('finance.loading', 'Wird glade…')}
                  </Table.Td>
                </Table.Tr>
              ) : cats.length === 0 ? (
                <Table.Tr>
                  <Table.Td
                    colSpan={3}
                    style={{
                      textAlign: 'center',
                      color: '#99a2ac',
                      padding: '24px',
                      fontSize: 'var(--mantine-font-size-sm)',
                    }}
                  >
                    {t('finance.noCategories', 'No cheni Kategorie.')}
                  </Table.Td>
                </Table.Tr>
              ) : (
                cats.map((c) => (
                  <Table.Tr key={c.id}>
                    <Table.Td data-label={t('finance.category', 'Kategorie')}>
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
                            color: '#99a2ac',
                          }}
                        >
                          {t('finance.category.custom', 'Benutzerdefiniert')}
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
                                    'Standard-Kategorie chann nöd bearbeitet wärde',
                                  )
                                : undefined
                            }
                          >
                            {c.isDefault ? (
                              <IconLock
                                size={16}
                                style={{ color: '#99a2ac' }}
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
                              color: c.isDefault ? '#99a2ac' : '#ff4d3d',
                            }}
                            onClick={() => {
                              if (!c.isDefault) setDeleteTarget(c)
                            }}
                            disabled={c.isDefault}
                            title={
                              c.isDefault
                                ? t(
                                    'finance.defaultCannotDelete',
                                    'Standard-Kategorie chann nöd gösche wärde',
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

      <Modal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title={t('finance.newCategory', 'Neui Kategorie')}
        footer={
          <>
            <Button variant="default" onClick={() => setAddOpen(false)}>
              {t('common.cancel', 'Abbreche')}
            </Button>
            <Button variant="filled" onClick={saveAdd}>
              {t('common.create', 'Erstelle')}
            </Button>
          </>
        }
      >
        {catForm}
      </Modal>
      <Modal
        open={!!editTarget}
        onClose={() => setEditTarget(null)}
        title={t('finance.editCategory', 'Kategorie bearbeite')}
        subtitle={editTarget?.name}
        footer={
          <>
            <Button variant="default" onClick={() => setEditTarget(null)}>
              {t('common.cancel', 'Abbreche')}
            </Button>
            <Button variant="filled" onClick={saveEdit}>
              {t('common.save', 'Speichere')}
            </Button>
          </>
        }
      >
        {catForm}
      </Modal>
      <ConfirmModal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title={t('finance.deleteCategoryTitle', '"{{name}}" lösche?', {
          name: deleteTarget?.name ?? '',
        })}
        body={t(
          'finance.deleteCategoryBody',
          'Transaktione, wo die Kategorie bruched, wärded unkategorisiert.',
        )}
        onConfirm={confirmDelete}
      />
    </div>
  )
}
