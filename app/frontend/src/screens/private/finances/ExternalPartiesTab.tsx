import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Group, SimpleGrid, TextInput } from '@mantine/core'
import { useT } from '@/locales/i18n'
import { IconPlus, IconTrash, IconPencil } from '@tabler/icons-react'
import { useToast, useAuth } from '@/context/AppContext'
import { Modal, Field, ConfirmModal, SimpleList, useSubmitOnce } from '@/components/ui'
import type { ExternalParty } from '@/types'
import {
  listExternalParties,
  createExternalParty,
  updateExternalParty,
  deleteExternalParty,
} from '@/api/finance'
import { qk } from '@/data/keys'

export function ExternalPartiesTab() {
  const { t } = useT()
  const { notify } = useToast()
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const canCreate = hasPermission('finance.external_parties.create')
  const canUpdate = hasPermission('finance.external_parties.update')
  const canDelete = hasPermission('finance.external_parties.delete')
  const { data: parties = [], isLoading: loading } = useQuery({
    queryKey: qk.externalParties,
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
      queryClient.invalidateQueries({ queryKey: qk.externalParties })
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
  const [submitAdd, adding] = useSubmitOnce(saveAdd)

  const saveEdit = async () => {
    if (!editTarget) return
    try {
      await updateExternalParty(editTarget.id, buildPayload())
      queryClient.invalidateQueries({ queryKey: qk.externalParties })
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
      queryClient.invalidateQueries({ queryKey: qk.externalParties })
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
      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing={12}>
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
            type="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            placeholder="billing@example.com"
          />
        </Field>
      </SimpleGrid>
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
        <Group justify="flex-end" mb={16} className="page-actions">
          <Button variant="filled" onClick={openAdd}>
            <IconPlus size={16} />
            {t('finance.externalParty.new', 'Neue Partei')}
          </Button>
        </Group>
      )}
      <SimpleList
        items={parties}
        loading={loading}
        emptyMessage={t('finance.externalParty.none', 'Noch keine externen Parteien.')}
        getKey={(p) => p.id}
        row={(p) => ({
          title: p.name,
          subtitle: [p.email, p.addressCity].filter(Boolean).join(' · ') || undefined,
          actions:
            canUpdate || canDelete ? (
              <>
                {canUpdate && (
                  <Button
                    size="sm"
                    variant="subtle"
                    onClick={() => openEdit(p)}
                    aria-label={t('common.edit', 'Bearbeiten')}
                    title={t('common.edit', 'Bearbeiten')}
                  >
                    <IconPencil size={16} />
                  </Button>
                )}
                {canDelete && (
                  <Button
                    size="sm"
                    variant="subtle"
                    style={{ color: 'var(--mantine-color-red-text)' }}
                    onClick={() => setDeleteTarget(p)}
                    aria-label={t('common.delete', 'Löschen')}
                    title={t('common.delete', 'Löschen')}
                  >
                    <IconTrash size={16} />
                  </Button>
                )}
              </>
            ) : undefined,
        })}
      />

      <Modal
        onSubmit={(e) => {
          e?.preventDefault()
          submitAdd()
        }}
        wide
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title={t('finance.externalParty.new', 'Neue Partei')}
        footer={
          <>
            <Button variant="default" onClick={() => setAddOpen(false)}>
              {t('common.cancel', 'Abbrechen')}
            </Button>
            <Button variant="filled" type="submit" loading={adding}>
              {t('common.create', 'Erstellen')}
            </Button>
          </>
        }
      >
        {partyForm}
      </Modal>
      <Modal
        onSubmit={(e) => {
          e?.preventDefault()
          saveEdit()
        }}
        wide
        open={!!editTarget}
        onClose={() => setEditTarget(null)}
        title={t('finance.externalParty.edit', 'Partei bearbeiten')}
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
