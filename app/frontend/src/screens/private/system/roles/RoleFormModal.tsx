import { useState } from 'react'
import { Button, Checkbox, TextInput } from '@mantine/core'
import type { Role } from '@/api/settings'
import { Modal, Field } from '@/components/ui'
import { useT } from '@/locales/i18n'
import { roleDescription, roleLabel } from '@/roles'
import type { RoleInput } from './useRoles'

/**
 * Creates a role, or edits `role` when one is given. Give it a `key` that
 * changes with the role, so the fields start from that role.
 */
export function RoleFormModal({
  open,
  role,
  onClose,
  onSubmit,
}: {
  open: boolean
  role: Role | null
  onClose: () => void
  onSubmit: (input: RoleInput) => Promise<unknown>
}) {
  const { t } = useT()
  const [name, setName] = useState(role?.name ?? '')
  const [description, setDescription] = useState(role ? roleDescription(role) : '')
  const [isAdmin, setIsAdmin] = useState(role?.isAdmin ?? false)
  const [saving, setSaving] = useState(false)

  const submit = async () => {
    if (!name.trim()) return
    setSaving(true)
    try {
      await onSubmit({ name: name.trim(), description: description.trim() || null, isAdmin })
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      onSubmit={(e) => {
        e?.preventDefault()
        submit()
      }}
      title={role ? t('roles.edit', 'Rolle bearbeiten') : t('roles.new', 'Neue Rolle')}
      subtitle={
        role
          ? [roleLabel(role.name), role.isSystem ? t('roles.systemRole', 'Systemrolle') : null]
              .filter(Boolean)
              .join(' · ')
          : t(
              'roles.newSubtitle',
              'Startet ohne Berechtigungen. Lege sie danach in der Tabelle fest.',
            )
      }
      footer={
        <>
          <Button variant="default" onClick={onClose}>
            {t('common.cancel', 'Abbrechen')}
          </Button>
          <Button variant="filled" type="submit" loading={saving}>
            {role
              ? t('common.saveChanges', 'Änderungen speichern')
              : t('roles.create', 'Rolle erstellen')}
          </Button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {/* A system role keeps its name, so it shows only in the subtitle. */}
        {!role?.isSystem && (
          <Field label={t('roles.name', 'Name der Rolle')}>
            <TextInput
              placeholder={role ? undefined : t('roles.namePlaceholder', 'z. B. Moderation')}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </Field>
        )}
        <Field
          label={t('common.description', 'Beschreibung')}
          hint={t('roles.descHint', 'Optional, wird in der Verwaltung angezeigt')}
        >
          <TextInput
            placeholder={
              role
                ? undefined
                : t('roles.descPlaceholder', 'z. B. Darf Mitglieder und Finanzen verwalten')
            }
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </Field>
        {!role?.isSystem && (
          <Checkbox
            checked={isAdmin}
            onChange={(e) => setIsAdmin(e.currentTarget.checked)}
            label={t('roles.adminRole', 'Admin-Rolle')}
            description={t('roles.adminHint', 'Umgeht alle Berechtigungsprüfungen')}
          />
        )}
      </div>
    </Modal>
  )
}
