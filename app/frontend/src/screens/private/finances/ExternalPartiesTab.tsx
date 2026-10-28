import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Table, Button, Group, Paper, TextInput } from '@mantine/core'
import { useT } from '@/locales/i18n'
import { IconPlus, IconTrash, IconPencil } from '@tabler/icons-react'
import { useToast, useAuth } from '@/context/AppContext'
import { Modal, Field, ConfirmModal } from '@/components/ui'
import type { ExternalParty } from '@/types'
import {
  listExternalParties,
  createExternalParty,
  updateExternalParty,
  deleteExternalParty,
} from '@/api/finance'

export function ExternalPartiesTab() {
  const { t } = useT()
  const { notify } = useToast()
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const canCreate = hasPermission('finance.external_parties.create')
  const canUpdate = hasPermission('finance.external_parties.update')
  const canDelete = hasPermission('finance.external_parties.delete')
  const { data: parties = [], isLoading: loading } = useQuery({
    queryKey: ['external-parties'],
    queryFn: () => listExternalParties(),
  })
  const [addOpen, setAddOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<ExternalParty | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<ExternalParty | null>(null)
  const [form, setForm] = useState({
    name: '',
    email: '',
    addressStreet: '',
    addressHouseNo: '',
    addressPostalCode: '',
    addressCity: '',
    addressCountry: 'CH',
    notes: '',
  })

  const resetForm = () =>
    setForm({
      name: '',
      email: '',
      addressStreet: '',
      addressHouseNo: '',
      addressPostalCode: '',
      addressCity: '',
      addressCountry: 'CH',
      notes: '',
    })

  const openAdd = () => {
    resetForm()
    setAddOpen(true)
  }

  const openEdit = (p: ExternalParty) => {
    setEditTarget(p)
    setForm({
      name: p.name,
      email: p.email ?? '',
      addressStreet: p.addressStreet ?? '',
      addressHouseNo: p.addressHouseNo ?? '',
      addressPostalCode: p.addressPostalCode ?? '',
      addressCity: p.addressCity ?? '',
      addressCountry: p.addressCountry,
      notes: p.notes ?? '',
    })
  }

  const buildPayload = () => ({
    name: form.name,
    email: form.email || null,
    addressStreet: form.addressStreet || null,
    addressHouseNo: form.addressHouseNo || null,
    addressPostalCode: form.addressPostalCode || null,
    addressCity: form.addressCity || null,
    addressCountry: form.addressCountry || 'CH',
    notes: form.notes || null,
  })

  const saveAdd = async () => {
    if (!form.name) return
    try {
      await createExternalParty(buildPayload())
      queryClient.invalidateQueries({ queryKey: ['external-parties'] })
      setAddOpen(false)
      notify(
        'success',
        t('finance.externalParty.created', 'Externe Partei erstellt'),
        t(
          'finance.externalParty.createdMsg',
          '«{{name}}» ist jetzt verfügbar.',
          {
            name: form.name,
          },
        ),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error', 'Fehler'),
        err instanceof Error
          ? err.message
          : t(
              'finance.externalParty.couldNotCreate',
              'Externe Partei konnte nicht erstellt werden.',
            ),
      )
    }
  }

  const saveEdit = async () => {
    if (!editTarget) return
    try {
      await updateExternalParty(editTarget.id, buildPayload())
      queryClient.invalidateQueries({ queryKey: ['external-parties'] })
      setEditTarget(null)
      notify(
        'success',
        t('finance.externalParty.updated', 'Externe Partei gespeichert'),
        t('finance.externalParty.savedMsg', '«{{name}}» wurde gespeichert.', {
          name: form.name,
        }),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error', 'Fehler'),
        err instanceof Error
          ? err.message
          : t(
              'finance.externalParty.couldNotUpdate',
              'Externe Partei konnte nicht gespeichert werden.',
            ),
      )
    }
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    try {
      await deleteExternalParty(deleteTarget.id)
      queryClient.invalidateQueries({ queryKey: ['external-parties'] })
      notify(
        'info',
        t('finance.externalParty.deleted', 'Externe Partei gelöscht'),
        t(
          'finance.externalParty.removedMsg',
          '«{{name}}» wurde gelöscht.',
          {
            name: deleteTarget.name,
          },
        ),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error', 'Fehler'),
        err instanceof Error
          ? err.message
          : t(
              'finance.externalParty.couldNotDelete',
              'Externe Partei konnte nicht gelöscht werden.',
            ),
      )
    }
  }

  const partyForm = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Field label={t('common.name', 'Name')}>
        <TextInput
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          placeholder={t(
            'finance.externalParty.namePlaceholder',
            'z. B. Muster AG',
          )}
        />
      </Field>
      <Field label={t('common.email', 'E-Mail')}>
        <TextInput
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
          placeholder="billing@example.com"
        />
      </Field>
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12 }}>
        <Field label={t('common.street', 'Strasse')}>
          <TextInput
            value={form.addressStreet}
            onChange={(e) =>
              setForm({ ...form, addressStreet: e.target.value })
            }
          />
        </Field>
        <Field label={t('common.houseNo', 'Nr.')}>
          <TextInput
            value={form.addressHouseNo}
            onChange={(e) =>
              setForm({ ...form, addressHouseNo: e.target.value })
            }
          />
        </Field>
      </div>
      <div
        style={{ display: 'grid', gridTemplateColumns: '1fr 2fr 1fr', gap: 12 }}
      >
        <Field label={t('common.postalCode', 'PLZ')}>
          <TextInput
            value={form.addressPostalCode}
            onChange={(e) =>
              setForm({ ...form, addressPostalCode: e.target.value })
            }
          />
        </Field>
        <Field label={t('common.city', 'Ort')}>
          <TextInput
            value={form.addressCity}
            onChange={(e) => setForm({ ...form, addressCity: e.target.value })}
          />
        </Field>
        <Field label={t('common.country', 'Land')}>
          <TextInput
            value={form.addressCountry}
            onChange={(e) =>
              setForm({ ...form, addressCountry: e.target.value })
            }
            maxLength={2}
          />
        </Field>
      </div>
      <Field label={t('common.notes', 'Notizen')}>
        <TextInput
          value={form.notes}
          onChange={(e) => setForm({ ...form, notes: e.target.value })}
        />
      </Field>
    </div>
  )

  return (
    <div>
      {canCreate && (
        <Group justify="flex-end" mb={16}>
          <Button variant="filled" onClick={openAdd}>
            <IconPlus size={16} />
            {t('finance.externalParty.new', 'Neue Partei')}
          </Button>
        </Group>
      )}
      <Paper withBorder shadow="sm" radius="lg">
        <div style={{ overflowX: 'auto' }}>
          <Table highlightOnHover className="responsive-table">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t('common.name', 'Name')}</Table.Th>
                <Table.Th>{t('common.email', 'E-Mail')}</Table.Th>
                <Table.Th>{t('common.city', 'Ort')}</Table.Th>
                <Table.Th style={{ width: 80 }}></Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {loading ? (
                <Table.Tr>
                  <Table.Td
                    colSpan={4}
                    style={{
                      textAlign: 'center',
                      color: '#8c86a0',
                      padding: '24px',
                      fontSize: 'var(--mantine-font-size-sm)',
                    }}
                  >
                    {t('finance.loading', 'Wird geladen …')}
                  </Table.Td>
                </Table.Tr>
              ) : parties.length === 0 ? (
                <Table.Tr>
                  <Table.Td
                    colSpan={4}
                    style={{
                      textAlign: 'center',
                      color: '#8c86a0',
                      padding: '24px',
                      fontSize: 'var(--mantine-font-size-sm)',
                    }}
                  >
                    {t(
                      'finance.externalParty.none',
                      'Noch keine externen Parteien.',
                    )}
                  </Table.Td>
                </Table.Tr>
              ) : (
                parties.map((p) => (
                  <Table.Tr key={p.id}>
                    <Table.Td data-label={t('common.name', 'Name')}>
                      <span style={{ fontWeight: 500 }}>{p.name}</span>
                    </Table.Td>
                    <Table.Td data-label={t('common.email', 'E-Mail')}>
                      <span
                        style={{
                          fontSize: 'var(--mantine-font-size-sm)',
                          color: '#5e5873',
                        }}
                      >
                        {p.email ?? '—'}
                      </span>
                    </Table.Td>
                    <Table.Td data-label={t('common.city', 'Ort')}>
                      <span
                        style={{
                          fontSize: 'var(--mantine-font-size-sm)',
                          color: '#5e5873',
                        }}
                      >
                        {p.addressCity ?? '—'}
                      </span>
                    </Table.Td>
                    <Table.Td data-label="">
                      <div style={{ display: 'flex', gap: 4 }}>
                        {canUpdate && (
                          <Button
                            size="sm"
                            variant="subtle"
                            onClick={() => openEdit(p)}
                          >
                            <IconPencil size={16} />
                          </Button>
                        )}
                        {canDelete && (
                          <Button
                            size="sm"
                            variant="subtle"
                            style={{ color: '#ff4d3d' }}
                            onClick={() => setDeleteTarget(p)}
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
        title={t('finance.externalParty.new', 'Neue Partei')}
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
        {partyForm}
      </Modal>
      <Modal
        open={!!editTarget}
        onClose={() => setEditTarget(null)}
        title={t('finance.externalParty.edit', 'Partei bearbeiten')}
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
        {partyForm}
      </Modal>
      <ConfirmModal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title={t('finance.externalParty.deleteTitle', '«{{name}}» löschen?', {
          name: deleteTarget?.name ?? '',
        })}
        body={t(
          'finance.externalParty.deleteBody',
          'Rechnungen an diese Partei bleiben erhalten.',
        )}
        onConfirm={confirmDelete}
      />
    </div>
  )
}
