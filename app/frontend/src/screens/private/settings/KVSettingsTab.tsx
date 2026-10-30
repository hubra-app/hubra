import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Badge, Button, TextInput, Select } from '@mantine/core'
import {
  IconPlus,
  IconPencil,
  IconTrash,
  IconLock,
  IconAdjustmentsHorizontal,
} from '@tabler/icons-react'
import { useToast, useAuth } from '@/context/AppContext'
import { useT } from '@/locales/i18n'
import { KVTable, Modal, Field, ConfirmModal } from '@/components/ui'
import { listSettings, upsertSetting, deleteSetting } from '@/api/settings'
import type { SettingEntry } from '@/api/settings'
import { qk } from '@/data/keys'

const VALIDATION_TYPES: [string, string][] = [
  ['', 'Keine'],
  ['text', 'Text'],
  ['email', 'E-Mail'],
  ['url', 'URL'],
  ['domain', 'Domain'],
  ['host', 'Host'],
  ['port', 'Port'],
  ['number', 'Zahl'],
]

export function KVSettingsTab() {
  const queryClient = useQueryClient()
  const { notify } = useToast()
  const { t } = useT()
  const validationTypes = VALIDATION_TYPES.map(([value, label]) => ({
    value,
    label: t(`kv.validation.${value || 'none'}`, label),
  }))
  const { hasPermission } = useAuth()
  const canWrite = hasPermission('settings.settings.write')
  const canDelete = hasPermission('settings.settings.delete')
  const [editingKey, setEditingKey] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')
  const [saving, setSaving] = useState(false)
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState<
    'all' | 'required' | 'sensitive' | 'restricted'
  >('all')
  const [showAdd, setShowAdd] = useState(false)
  const [newKey, setNewKey] = useState('')
  const [newValue, setNewValue] = useState('')
  const [newNamespace, setNewNamespace] = useState('general')
  const [newDesc, setNewDesc] = useState('')
  const [newValidationType, setNewValidationType] = useState('')
  const [addSaving, setAddSaving] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<SettingEntry | null>(null)
  const [editingMeta, setEditingMeta] = useState<SettingEntry | null>(null)
  const [metaNamespace, setMetaNamespace] = useState('')
  const [metaLabel, setMetaLabel] = useState('')
  const [metaValidationType, setMetaValidationType] = useState('')
  const [metaDescription, setMetaDescription] = useState('')
  const [metaSensitive, setMetaSensitive] = useState(false)
  const [metaRequired, setMetaRequired] = useState(false)
  const [metaRestricted, setMetaRestricted] = useState(false)
  const [metaSaving, setMetaSaving] = useState(false)

  const { data, isLoading: loading } = useQuery({
    queryKey: qk.settings.kv,
    queryFn: () => listSettings(),
  })
  const entries = data ?? []

  const startEdit = (entry: SettingEntry) => {
    setEditingKey(entry.key)
    setEditValue(entry.value ?? '')
  }

  const cancelEdit = () => {
    setEditingKey(null)
    setEditValue('')
  }

  const saveEdit = async (key: string) => {
    const entry = entries.find((e) => e.key === key)
    if (entry?.required && !editValue.trim()) {
      notify('error', t('kv.required', 'Pflichtfeld'), t('kv.requiredMsg', '«{{key}}» ist ein Pflichtfeld und darf nicht leer sein.', { key }))
      return
    }
    setSaving(true)
    try {
      await upsertSetting(key, editValue)
      queryClient.invalidateQueries({ queryKey: qk.settings.kv })
      setEditingKey(null)
      notify('success', t('common.saved', 'Gespeichert'), t('kv.updatedMsg', '{{key}} wurde gespeichert.', { key }))
    } catch (err: unknown) {
      notify(
        'error',
        t('common.saveFailed', 'Speichern fehlgeschlagen'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    } finally {
      setSaving(false)
    }
  }

  const handleAdd = async () => {
    if (!newKey.trim()) return
    setAddSaving(true)
    try {
      await upsertSetting(newKey.trim(), newValue, {
        namespace: newNamespace,
        description: newDesc || null,
        validation_type: newValidationType || null,
      })
      queryClient.invalidateQueries({ queryKey: qk.settings.kv })
      setShowAdd(false)
      setNewKey('')
      setNewValue('')
      setNewNamespace('general')
      setNewDesc('')
      setNewValidationType('')
      notify('success', t('common.created', 'Erstellt'), t('kv.addedMsg', '{{key}} wurde hinzugefügt.', { key: newKey.trim() }))
    } catch (err: unknown) {
      notify(
        'error',
        t('common.createFailed', 'Erstellen fehlgeschlagen'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    } finally {
      setAddSaving(false)
    }
  }

  const handleDelete = async (entry: SettingEntry) => {
    try {
      await deleteSetting(entry.key)
      queryClient.invalidateQueries({ queryKey: qk.settings.kv })
      setDeleteTarget(null)
      notify('success', t('common.deleted', 'Gelöscht'), t('kv.removedMsg', '{{key}} wurde entfernt.', { key: entry.key }))
    } catch (err: unknown) {
      notify(
        'error',
        t('common.deleteFailed', 'Löschen fehlgeschlagen'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    }
  }

  const filtered = search.trim()
    ? entries.filter(
        (e) =>
          e.key.toLowerCase().includes(search.toLowerCase()) ||
          (e.value ?? '').toLowerCase().includes(search.toLowerCase()),
      )
    : entries

  const filteredEntries = filtered.filter((e) => {
    if (typeFilter === 'required') return e.required
    if (typeFilter === 'sensitive') return e.sensitive
    if (typeFilter === 'restricted') return e.restricted
    return true
  })

  return (
    <div>
      <div
        style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}
      >
        {(['all', 'required', 'sensitive', 'restricted'] as const).map((f) => (
          <button
            key={f}
            className={`chip${typeFilter === f ? ' on' : ''}`}
            onClick={() => setTypeFilter(f)}
          >
            {t(`kv.filter.${f}`, f)}
          </button>
        ))}
      </div>
      <KVTable<SettingEntry>
        entries={filteredEntries}
        loading={loading}
        getNamespace={(e) => e.namespace || 'other'}
        search={search}
        onSearchChange={setSearch}
        toolbar={
          <Button
            variant="filled"
            onClick={() => setShowAdd(true)}
            style={{ display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <IconPlus size={16} /> {t('settings.kv.addEntry', 'Eintrag hinzufügen')}
          </Button>
        }
        editingKey={editingKey}
        editValue={editValue}
        onEditValueChange={setEditValue}
        onEditStart={startEdit}
        onEditSave={(entry) => saveEdit(entry.key)}
        onEditCancel={cancelEdit}
        saving={saving}
        isValueClickable={(entry) => !entry.restricted}
        renderKeySuffix={(entry) => (
          <>
            {entry.sensitive && (
              <IconLock size={11} style={{ color: '#8c86a0', flexShrink: 0 }} />
            )}
            {entry.restricted && (
              <Badge
                variant="light"
                radius="xl"
                styles={{
                  root: {
                    fontSize: 'var(--mantine-font-size-xs)',
                    padding: '1px 5px',
                    background: '#fff3e0',
                    color: '#e65100',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 3,
                  },
                }}
              >
                <IconLock size={10} /> {t('kv.restricted', 'Gesperrt')}
              </Badge>
            )}
            {entry.required && (
              <Badge
                variant="light"
                radius="xl"
                styles={{
                  root: {
                    fontSize: 'var(--mantine-font-size-xs)',
                    padding: '1px 5px',
                    background: '#f0f4ff',
                    color: '#4a5dcc',
                  },
                }}
              >
                {t('kv.required', 'Pflichtfeld')}
              </Badge>
            )}
            {entry.validation_type && (
              <Badge
                variant="light"
                radius="xl"
                styles={{
                  root: {
                    fontSize: 'var(--mantine-font-size-xs)',
                    padding: '1px 5px',
                    background: '#f4f0ff',
                    color: '#7c4dcc',
                  },
                }}
              >
                {entry.validation_type}
              </Badge>
            )}
          </>
        )}
        renderKeyBelow={(entry) =>
          entry.description ? (
            <div
              style={{
                fontSize: 'var(--mantine-font-size-xs)',
                color: '#8c86a0',
                marginTop: 2,
              }}
            >
              {entry.description}
            </div>
          ) : null
        }
        renderValue={(entry) => (
          <span
            style={{
              fontFamily: 'monospace',
              fontSize: 'var(--mantine-font-size-sm)',
              color: entry.value === null ? '#bbb' : undefined,
            }}
          >
            {entry.sensitive ? (
              entry.value ? (
                '\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022'
              ) : (
                <em style={{ color: '#b7b0c9' }}>{t('kv.notSet', 'nicht gesetzt')}</em>
              )
            ) : (
              entry.value ?? <em style={{ color: '#b7b0c9' }}>{t('kv.notSet', 'nicht gesetzt')}</em>
            )}
          </span>
        )}
        getInputType={(entry) => (entry.sensitive ? 'password' : 'text')}
        renderActions={(entry) => (
          <>
            {editingKey !== entry.key && !entry.restricted && canWrite && (
              <Button
                variant="subtle"
                onClick={() => startEdit(entry)}
                style={{ padding: '4px 7px' }}
                title={t('kv.editValue', 'Wert bearbeiten')}
              >
                <IconPencil size={16} />
              </Button>
            )}
            {editingKey !== entry.key && canWrite && (
              <Button
                variant="subtle"
                onClick={() => {
                  setEditingMeta(entry)
                  setMetaNamespace(entry.namespace ?? '')
                  setMetaLabel(entry.label ?? '')
                  setMetaValidationType(entry.validation_type ?? '')
                  setMetaDescription(entry.description ?? '')
                  setMetaSensitive(entry.sensitive)
                  setMetaRequired(entry.required)
                  setMetaRestricted(entry.restricted)
                }}
                style={{ padding: '4px 7px' }}
                title={t('kv.editMeta', 'Eigenschaften bearbeiten')}
              >
                <IconAdjustmentsHorizontal size={16} />
              </Button>
            )}
            {!entry.required && editingKey !== entry.key && canDelete && (
              <Button
                variant="subtle"
                onClick={() => setDeleteTarget(entry)}
                style={{ padding: '4px 7px', color: '#c0392b' }}
                title={t('common.delete', 'Löschen')}
              >
                <IconTrash size={16} />
              </Button>
            )}
          </>
        )}
        emptyMessage={t('kv.empty', 'Keine Einstellungen gefunden.')}
      />

      <Modal
        open={showAdd}
        title={t('kv.addTitle', 'Einstellung hinzufügen')}
        onClose={() => setShowAdd(false)}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Field label={t('data.key', 'Schlüssel')} hint={t('kv.keyHint', 'z. B. club.website')}>
            <TextInput
              value={newKey}
              onChange={(e) => setNewKey(e.target.value)}
              placeholder="namespace.key"
            />
          </Field>
          <Field label={t('data.value', 'Wert')}>
            <TextInput
              value={newValue}
              onChange={(e) => setNewValue(e.target.value)}
            />
          </Field>
          <Field label={t('kv.namespace', 'Bereich')} hint={t('kv.namespaceHint', 'Gruppe, zu der diese Einstellung gehört')}>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <Select
                value={
                  [...new Set(entries.map((e) => e.namespace))].includes(
                    newNamespace,
                  )
                    ? newNamespace
                    : '__custom__'
                }
                onChange={(v) => {
                  if (v === '__custom__' || v === null) {
                    setNewNamespace('')
                  } else {
                    setNewNamespace(v)
                  }
                }}
                data={[
                  ...[...new Set(entries.map((e) => e.namespace))]
                    .sort()
                    .map((ns) => ({ value: ns, label: ns })),
                  { value: '__custom__', label: t('kv.addCustom', 'Eigenen hinzufügen …') },
                ]}
                style={{ flex: 1 }}
              />
              {![...new Set(entries.map((e) => e.namespace))].includes(
                newNamespace,
              ) && (
                <TextInput
                  value={newNamespace}
                  onChange={(e) => setNewNamespace(e.target.value)}
                  placeholder={t('kv.newNamespace', 'neuer Bereich')}
                  style={{ flex: 1, fontSize: 'var(--mantine-font-size-sm)' }}
                  autoFocus
                />
              )}
            </div>
          </Field>
          <Field label={t('common.description', 'Beschreibung')} hint={t('common.optional', 'Optional')}>
            <TextInput
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
            />
          </Field>
          <Field
            label={t('kv.validationType', 'Prüfung')}
            hint={t('kv.validationHint', 'Optional: wie der Wert geprüft wird')}
          >
            <Select
              data={validationTypes}
              value={newValidationType}
              onChange={(v) => setNewValidationType(v ?? '')}
            />
          </Field>
          <div
            style={{
              display: 'flex',
              gap: 8,
              justifyContent: 'flex-end',
              marginTop: 4,
            }}
          >
            <Button variant="subtle" onClick={() => setShowAdd(false)}>
              {t('common.cancel', 'Abbrechen')}
            </Button>
            <Button
              variant="filled"
              onClick={handleAdd}
              disabled={addSaving || !newKey.trim()}
            >
              {addSaving ? t('common.saving', 'Wird gespeichert …') : t('common.save', 'Speichern')}
            </Button>
          </div>
        </div>
      </Modal>

      <ConfirmModal
        open={deleteTarget !== null}
        title={t('kv.deleteTitle', 'Einstellung löschen')}
        body={
          deleteTarget
            ? t('kv.deleteBody', '«{{key}}» löschen? Das kann nicht rückgängig gemacht werden.', { key: deleteTarget.key })
            : ''
        }
        onConfirm={() => {
          if (deleteTarget) handleDelete(deleteTarget)
        }}
        onClose={() => setDeleteTarget(null)}
      />

      <Modal
        open={editingMeta !== null}
        title={`${t('kv.editMeta', 'Eigenschaften bearbeiten')}: ${editingMeta?.key ?? ''}`}
        onClose={() => setEditingMeta(null)}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Field label={t('kv.label', 'Bezeichnung')} hint={t('kv.labelHint', 'Anzeigename dieser Einstellung')}>
            <TextInput
              value={metaLabel}
              onChange={(e) => setMetaLabel(e.target.value)}
              placeholder={t('kv.labelPlaceholder', 'z. B. Vereinsname')}
            />
          </Field>
          <Field label={t('kv.namespace', 'Bereich')}>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <Select
                value={
                  [...new Set(entries.map((e) => e.namespace))].includes(
                    metaNamespace,
                  )
                    ? metaNamespace
                    : '__custom__'
                }
                onChange={(v) => {
                  if (v === '__custom__' || v === null) {
                    setMetaNamespace('')
                  } else {
                    setMetaNamespace(v)
                  }
                }}
                data={[
                  ...[...new Set(entries.map((e) => e.namespace))]
                    .sort()
                    .map((ns) => ({ value: ns, label: ns })),
                  { value: '__custom__', label: t('kv.addCustom', 'Eigenen hinzufügen …') },
                ]}
                style={{ flex: 1 }}
              />
              {![...new Set(entries.map((e) => e.namespace))].includes(
                metaNamespace,
              ) && (
                <TextInput
                  value={metaNamespace}
                  onChange={(e) => setMetaNamespace(e.target.value)}
                  placeholder={t('kv.newNamespace', 'neuer Bereich')}
                  style={{ flex: 1, fontSize: 'var(--mantine-font-size-sm)' }}
                  autoFocus
                />
              )}
            </div>
          </Field>
          <Field label={t('kv.validationType', 'Prüfung')}>
            <Select
              data={validationTypes}
              value={metaValidationType}
              onChange={(v) => setMetaValidationType(v ?? '')}
            />
          </Field>
          <Field label={t('common.description', 'Beschreibung')} hint={t('kv.descHint', 'Hilfetext in den Einstellungen')}>
            <TextInput
              value={metaDescription}
              onChange={(e) => setMetaDescription(e.target.value)}
            />
          </Field>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <label
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                fontSize: 'var(--mantine-font-size-sm)',
                cursor: 'pointer',
              }}
            >
              <input
                type="checkbox"
                checked={metaSensitive}
                onChange={(e) => setMetaSensitive(e.target.checked)}
                style={{ width: 16, height: 16, accentColor: 'var(--mantine-color-acc-6)' }}
              />
              <span style={{ fontWeight: 600 }}>{t('kv.sensitive', 'Vertraulich')}</span>
              <span
                style={{
                  color: '#5e5873',
                  fontSize: 'var(--mantine-font-size-xs)',
                }}
              >
                {t('kv.sensitiveHint', 'Wert wird in API-Antworten verborgen')}
              </span>
            </label>
            <label
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                fontSize: 'var(--mantine-font-size-sm)',
                cursor: 'pointer',
              }}
            >
              <input
                type="checkbox"
                checked={metaRequired}
                onChange={(e) => setMetaRequired(e.target.checked)}
                style={{ width: 16, height: 16, accentColor: 'var(--mantine-color-acc-6)' }}
              />
              <span style={{ fontWeight: 600 }}>{t('kv.required', 'Pflichtfeld')}</span>
              <span
                style={{
                  color: '#5e5873',
                  fontSize: 'var(--mantine-font-size-xs)',
                }}
              >
                {t('kv.requiredHint', 'Kann nicht gelöscht werden')}
              </span>
            </label>
            <label
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                fontSize: 'var(--mantine-font-size-sm)',
                cursor: 'pointer',
              }}
            >
              <input
                type="checkbox"
                checked={metaRestricted}
                onChange={(e) => setMetaRestricted(e.target.checked)}
                style={{ width: 16, height: 16, accentColor: 'var(--mantine-color-acc-6)' }}
              />
              <span style={{ fontWeight: 600 }}>{t('kv.restricted', 'Gesperrt')}</span>
              <span
                style={{
                  color: '#5e5873',
                  fontSize: 'var(--mantine-font-size-xs)',
                }}
              >
                {t('kv.restrictedHint', 'Kann nicht geändert werden')}
              </span>
            </label>
          </div>
          <div
            style={{
              display: 'flex',
              gap: 8,
              justifyContent: 'flex-end',
              marginTop: 4,
            }}
          >
            <Button variant="subtle" onClick={() => setEditingMeta(null)}>
              {t('common.cancel', 'Abbrechen')}
            </Button>
            <Button
              variant="filled"
              onClick={async () => {
                if (!editingMeta) return
                setMetaSaving(true)
                try {
                  await upsertSetting(
                    editingMeta.key,
                    editingMeta.value ?? '',
                    {
                      namespace: metaNamespace || 'general',
                      label: metaLabel || null,
                      validation_type: metaValidationType || null,
                      description: metaDescription || null,
                      sensitive: metaSensitive,
                      required: metaRequired,
                      restricted: metaRestricted,
                    },
                  )
                  queryClient.invalidateQueries({ queryKey: qk.settings.kv })
                  setEditingMeta(null)
                  notify(
                    'success',
                    t('kv.metaSaved', 'Eigenschaften gespeichert'),
                    t('kv.updatedMsg', '{{key}} wurde gespeichert.', { key: editingMeta.key }),
                  )
                } catch (err: unknown) {
                  notify(
                    'error',
                    t('common.saveFailed', 'Speichern fehlgeschlagen'),
                    err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
                  )
                } finally {
                  setMetaSaving(false)
                }
              }}
              disabled={metaSaving}
            >
              {metaSaving ? t('common.saving', 'Wird gespeichert …') : t('common.save', 'Speichern')}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
