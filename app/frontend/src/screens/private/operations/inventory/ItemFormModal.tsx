import { useState } from 'react'
import { Button, Checkbox, Select, SimpleGrid, TextInput, Textarea } from '@mantine/core'
import type { InventoryItemCreate } from '@/api/inventory'
import { Modal, Field } from '@/components/ui'
import { MemberPicker } from '@/components/MemberPicker'
import { useT } from '@/locales/i18n'
import type {
  InventoryCategory,
  InventoryItem,
  InventoryLink,
  InventoryStatus,
  InventoryVisibility,
} from '@/types'
import { STATUSES, STATUS_CONFIG } from './constants'
import { LinkEditor } from './LinkEditor'

/**
 * Adds an item, or edits `item` when one is given. Give it a `key` that
 * changes with the item, so the fields start from it.
 */
export function ItemFormModal({
  open,
  item,
  onClose,
  onSubmit,
}: {
  open: boolean
  item: InventoryItem | null
  onClose: () => void
  onSubmit: (input: InventoryItemCreate) => Promise<unknown>
}) {
  const { t } = useT()
  const [fName, setFName] = useState(item?.name ?? '')
  const [fCat, setFCat] = useState<InventoryCategory>(item?.category ?? 'Tool')
  const [fDesc, setFDesc] = useState(item?.description ?? '')
  const [fOwner, setFOwner] = useState<number | undefined>(item?.ownerId ?? undefined)
  const [fResponsible, setFResponsible] = useState<number | undefined>(
    item?.responsibleId ?? undefined,
  )
  const [fVisibility, setFVisibility] = useState<InventoryVisibility>(item?.visibility ?? 'shared')
  const [fStatus, setFStatus] = useState<InventoryStatus>(item?.status ?? 'available')
  const [fCost, setFCost] = useState(item?.cost ?? '')
  const [fLinks, setFLinks] = useState<InventoryLink[]>(item?.links ?? [])
  const [fInstructionRequired, setFInstructionRequired] = useState(
    item?.instructionRequired ?? false,
  )
  const [saving, setSaving] = useState(false)

  const submit = async () => {
    if (!fName.trim()) return
    setSaving(true)
    try {
      await onSubmit({
        name: fName,
        category: fCat,
        description: fDesc || undefined,
        // An edit clears an owner that was taken away; a new item just has none.
        ownerId: fOwner ?? (item ? null : undefined),
        responsibleId: fResponsible ?? (item ? null : undefined),
        visibility: fVisibility,
        status: fStatus,
        cost: fCost || null,
        links: fLinks,
        instructionRequired: fInstructionRequired,
      })
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={open}
      wide
      onClose={onClose}
      onSubmit={(e) => {
        e?.preventDefault()
        submit()
      }}
      title={
        item
          ? t('inventory.editItem', 'Gegenstand bearbeiten')
          : t('inventory.addInventoryItem', 'Gegenstand hinzufügen')
      }
      subtitle={item?.name}
      footer={
        <>
          <Button variant="default" onClick={onClose}>
            {t('common.cancel', 'Abbrechen')}
          </Button>
          <Button variant="filled" type="submit" loading={saving}>
            {item
              ? t('common.saveChanges', 'Änderungen speichern')
              : t('inventory.addItem', 'Gegenstand hinzufügen')}
          </Button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <Field label={t('common.name', 'Name')}>
          <TextInput
            value={fName}
            onChange={(e) => setFName(e.target.value)}
            placeholder={t('common.namePlaceholder', 'Name')}
          />
        </Field>
        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing={12}>
          <Field label={t('inventory.category', 'Kategorie')}>
            <Select
              data={[
                { value: 'Tool', label: t('inventory.tool', 'Werkzeug') },
                { value: 'Item', label: t('inventory.itemLabel', 'Gegenstand') },
                { value: 'Material', label: t('inventory.material', 'Material') },
              ]}
              value={fCat}
              onChange={(v) => setFCat((v ?? 'Tool') as InventoryCategory)}
            />
          </Field>
          <Field label={t('common.status', 'Status')}>
            <Select
              data={STATUSES.map((s) => ({
                value: s,
                label: t(`inventory.status_${s}`, STATUS_CONFIG[s].label),
              }))}
              value={fStatus}
              onChange={(v) => setFStatus((v ?? 'active') as InventoryStatus)}
            />
          </Field>
        </SimpleGrid>
        <Field label={t('inventory.descriptionOptional', 'Beschreibung (optional)')}>
          <Textarea
            rows={2}
            value={fDesc}
            onChange={(e) => setFDesc(e.target.value)}
            placeholder={t('common.descriptionPlaceholder', 'Kurze Beschreibung …')}
          />
        </Field>
        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing={12}>
          <Field label={t('inventory.owner', 'Eigentümer:in')}>
            <MemberPicker
              noneLabel={t('inventory.noOwner', 'Keine Eigentümer:in')}
              value={fOwner}
              onChange={(v) => setFOwner(v ? Number(v) : undefined)}
            />
          </Field>
          <Field label={t('inventory.responsible', 'Verantwortlich')}>
            <MemberPicker
              noneLabel={t('inventory.noOneAssigned', 'Niemand zugewiesen')}
              value={fResponsible}
              onChange={(v) => setFResponsible(v ? Number(v) : undefined)}
            />
          </Field>
        </SimpleGrid>
        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing={12}>
          <Field label={t('inventory.visibility', 'Sichtbarkeit')}>
            <Select
              data={[
                { value: 'shared', label: t('inventory.shared', 'Gemeinsam') },
                { value: 'private', label: t('inventory.private', 'Privat') },
              ]}
              value={fVisibility}
              onChange={(v) => setFVisibility((v ?? 'shared') as InventoryVisibility)}
            />
          </Field>
          <Field label={t('inventory.costOptional', 'Kosten (CHF, optional)')}>
            <TextInput
              type="number"
              min={0}
              step="0.01"
              value={fCost}
              onChange={(e) => setFCost(e.target.value)}
              placeholder="0.00"
            />
          </Field>
        </SimpleGrid>
        <Field label={t('inventory.links', 'Links')}>
          <LinkEditor links={fLinks} onChange={setFLinks} />
        </Field>
        <Checkbox
          checked={fInstructionRequired}
          onChange={(e) => setFInstructionRequired(e.currentTarget.checked)}
          label={t('inventory.instruction.required', 'Einweisung vor Gebrauch nötig')}
        />
      </div>
    </Modal>
  )
}
