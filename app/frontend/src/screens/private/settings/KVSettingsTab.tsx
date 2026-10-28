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
import { KVTable, Modal, Field, ConfirmModal } from '@/components/ui'
import { listSettings, upsertSetting, deleteSetting } from '@/api/settings'
import type { SettingEntry } from '@/api/settings'

const VALIDATION_TYPES = [
  { value: '', label: 'None' },
  { value: 'text', label: 'Text' },
  { value: 'email', label: 'Email' },
  { value: 'url', label: 'URL' },
  { value: 'domain', label: 'Domain' },
  { value: 'host', label: 'Host' },
  { value: 'port', label: 'Port' },
  { value: 'number', label: 'Number' },
]

export function KVSettingsTab() {
  const queryClient = useQueryClient()
  const { notify } = useToast()
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
    queryKey: ['kv-settings'],
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
      notify('error', 'Required', `"${key}" is required and cannot be empty.`)
      return
    }
    setSaving(true)
    try {
      await upsertSetting(key, editValue)
      queryClient.invalidateQueries({ queryKey: ['kv-settings'] })
      setEditingKey(null)
      notify('success', 'Saved', `${key} updated.`)
    } catch (err: unknown) {
      notify(
        'error',
        'Save failed',
        err instanceof Error ? err.message : 'Unknown error',
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
      queryClient.invalidateQueries({ queryKey: ['kv-settings'] })
      setShowAdd(false)
      setNewKey('')
      setNewValue('')
      setNewNamespace('general')
      setNewDesc('')
      setNewValidationType('')
      notify('success', 'Created', `${newKey.trim()} added.`)
    } catch (err: unknown) {
      notify(
        'error',
        'Create failed',
        err instanceof Error ? err.message : 'Unknown error',
      )
    } finally {
      setAddSaving(false)
    }
  }

  const handleDelete = async (entry: SettingEntry) => {
    try {
      await deleteSetting(entry.key)
      queryClient.invalidateQueries({ queryKey: ['kv-settings'] })
      setDeleteTarget(null)
      notify('success', 'Deleted', `${entry.key} removed.`)
    } catch (err: unknown) {
      notify(
        'error',
        'Delete failed',
        err instanceof Error ? err.message : 'Unknown error',
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
            {f === 'all' ? 'All' : f.charAt(0).toUpperCase() + f.slice(1)}
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
            <IconPlus size={16} /> Add entry
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
              <IconLock size={11} style={{ color: '#99a2ac', flexShrink: 0 }} />
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
                <IconLock size={10} /> restricted
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
                required
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
                color: '#99a2ac',
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
                <em style={{ color: '#bbb' }}>not set</em>
              )
            ) : (
              entry.value ?? <em style={{ color: '#bbb' }}>not set</em>
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
                title="Edit value"
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
                title="Edit metadata"
              >
                <IconAdjustmentsHorizontal size={16} />
              </Button>
            )}
            {!entry.required && editingKey !== entry.key && canDelete && (
              <Button
                variant="subtle"
                onClick={() => setDeleteTarget(entry)}
                style={{ padding: '4px 7px', color: '#c0392b' }}
                title="Delete"
              >
                <IconTrash size={16} />
              </Button>
            )}
          </>
        )}
        emptyMessage="No settings found."
      />

      <Modal
        open={showAdd}
        title="Add KV entry"
        onClose={() => setShowAdd(false)}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Field label="Key" hint="e.g. club.website">
            <TextInput
              value={newKey}
              onChange={(e) => setNewKey(e.target.value)}
              placeholder="namespace.key"
            />
          </Field>
          <Field label="Value">
            <TextInput
              value={newValue}
              onChange={(e) => setNewValue(e.target.value)}
            />
          </Field>
          <Field label="Namespace" hint="Group this setting belongs to">
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
                  { value: '__custom__', label: 'Add custom…' },
                ]}
                style={{ flex: 1 }}
              />
              {![...new Set(entries.map((e) => e.namespace))].includes(
                newNamespace,
              ) && (
                <TextInput
                  value={newNamespace}
                  onChange={(e) => setNewNamespace(e.target.value)}
                  placeholder="new namespace"
                  style={{ flex: 1, fontSize: 'var(--mantine-font-size-sm)' }}
                  autoFocus
                />
              )}
            </div>
          </Field>
          <Field label="Description" hint="Optional">
            <TextInput
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
            />
          </Field>
          <Field
            label="Validation type"
            hint="Optional \u2014 how the value is validated"
          >
            <Select
              data={VALIDATION_TYPES}
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
              Cancel
            </Button>
            <Button
              variant="filled"
              onClick={handleAdd}
              disabled={addSaving || !newKey.trim()}
            >
              {addSaving ? 'Saving\u2026' : 'Save'}
            </Button>
          </div>
        </div>
      </Modal>

      <ConfirmModal
        open={deleteTarget !== null}
        title="Delete setting"
        body={
          deleteTarget
            ? `Delete "${deleteTarget.key}"? This cannot be undone.`
            : ''
        }
        onConfirm={() => {
          if (deleteTarget) handleDelete(deleteTarget)
        }}
        onClose={() => setDeleteTarget(null)}
      />

      <Modal
        open={editingMeta !== null}
        title={`Edit metadata: ${editingMeta?.key ?? ''}`}
        onClose={() => setEditingMeta(null)}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Field label="Label" hint="Display name for this setting">
            <TextInput
              value={metaLabel}
              onChange={(e) => setMetaLabel(e.target.value)}
              placeholder="e.g. Club Name"
            />
          </Field>
          <Field label="Namespace">
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
                  { value: '__custom__', label: 'Add custom…' },
                ]}
                style={{ flex: 1 }}
              />
              {![...new Set(entries.map((e) => e.namespace))].includes(
                metaNamespace,
              ) && (
                <TextInput
                  value={metaNamespace}
                  onChange={(e) => setMetaNamespace(e.target.value)}
                  placeholder="new namespace"
                  style={{ flex: 1, fontSize: 'var(--mantine-font-size-sm)' }}
                  autoFocus
                />
              )}
            </div>
          </Field>
          <Field label="Validation type">
            <Select
              data={VALIDATION_TYPES}
              value={metaValidationType}
              onChange={(v) => setMetaValidationType(v ?? '')}
            />
          </Field>
          <Field label="Description" hint="Help text shown in settings UI">
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
                style={{ width: 16, height: 16, accentColor: '#fece2b' }}
              />
              <span style={{ fontWeight: 600 }}>Sensitive</span>
              <span
                style={{
                  color: '#6b7480',
                  fontSize: 'var(--mantine-font-size-xs)',
                }}
              >
                Masks value in API responses
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
                style={{ width: 16, height: 16, accentColor: '#fece2b' }}
              />
              <span style={{ fontWeight: 600 }}>Required</span>
              <span
                style={{
                  color: '#6b7480',
                  fontSize: 'var(--mantine-font-size-xs)',
                }}
              >
                Prevents deletion
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
                style={{ width: 16, height: 16, accentColor: '#fece2b' }}
              />
              <span style={{ fontWeight: 600 }}>Restricted</span>
              <span
                style={{
                  color: '#6b7480',
                  fontSize: 'var(--mantine-font-size-xs)',
                }}
              >
                Prevents modification
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
              Cancel
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
                  queryClient.invalidateQueries({ queryKey: ['kv-settings'] })
                  setEditingMeta(null)
                  notify(
                    'success',
                    'Metadata saved',
                    `${editingMeta.key} updated.`,
                  )
                } catch (err: unknown) {
                  notify(
                    'error',
                    'Save failed',
                    err instanceof Error ? err.message : 'Unknown error',
                  )
                } finally {
                  setMetaSaving(false)
                }
              }}
              disabled={metaSaving}
            >
              {metaSaving ? 'Saving\u2026' : 'Save'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
