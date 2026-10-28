import { useState, useMemo } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Badge, Button, TextInput, Select } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  IconPlus,
  IconTrash,
  IconLock,
  IconPencil,
  IconPower,
} from '@tabler/icons-react'
import { useToast, useAuth } from '@/context/AppContext'
import {
  Modal,
  Field,
  ConfirmModal,
  KVTable,
  PageHead,
  Tabs,
} from '@/components/ui'
import { formatRelative } from '@/format'
import {
  listKeys,
  createKey,
  updateKey,
  deleteKey,
  listBindings,
  createBinding,
  updateBinding,
  deleteBinding,
  toggleBinding,
  getRegistry,
  getValidators,
  getSources,
  previewBindingValue,
} from '@/api/bindings'
import type {
  InternalKey,
  Binding,
  BindingSource,
  BindingPreview,
} from '@/api/bindings'

type Tab = 'keys' | 'bindings'

export function BindingsScreen() {
  const location = useLocation()
  const navigate = useNavigate()
  const tab: Tab = location.pathname.includes('/list') ? 'bindings' : 'keys'
  return (
    <div>
      <PageHead eyebrow="Operations" title="Bindings" actions={null} />
      <Tabs
        tabs={[
          { id: 'keys', label: 'Internal Keys' },
          { id: 'bindings', label: 'Bindings' },
        ]}
        activeTab={tab}
        onTabChange={(id) =>
          navigate(
            `/app/operations/bindings${id === 'bindings' ? '/list' : ''}`,
          )
        }
      />
      {tab === 'keys' && <KeysTab />}
      {tab === 'bindings' && <BindingsTab />}
    </div>
  )
}

function KeysTab() {
  const { notify } = useToast()
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const canCreate = hasPermission('keys.keys.write')
  const canUpdate = hasPermission('keys.keys.write')
  const canDelete = hasPermission('keys.keys.delete')
  const { data: keys = [], isLoading: loading } = useQuery({
    queryKey: ['keys'],
    queryFn: () => listKeys(),
  })
  const [search, setSearch] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [newKey, setNewKey] = useState('')
  const [NewLabel, setNewLabel] = useState('')
  const [newAllowMultiple, setNewAllowMultiple] = useState(false)
  const [newIsProtected, setNewIsProtected] = useState(false)
  const [addSaving, setAddSaving] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<InternalKey | null>(null)
  const [editTarget, setEditTarget] = useState<InternalKey | null>(null)
  const [editLabel, setEditLabel] = useState('')
  const [editAllowMultiple, setEditAllowMultiple] = useState(false)
  const [editIsProtected, setEditIsProtected] = useState(false)
  const [editSaving, setEditSaving] = useState(false)

  const filtered = useMemo(() => {
    if (!search.trim()) return keys
    const q = search.toLowerCase()
    return keys.filter(
      (k) =>
        k.key.toLowerCase().includes(q) ||
        (k.label?.toLowerCase().includes(q) ?? false),
    )
  }, [keys, search])

  const handleAdd = async () => {
    if (!newKey.trim()) return
    setAddSaving(true)
    try {
      const ik = await createKey({
        key: newKey.trim(),
        label: NewLabel.trim() || null,
        allow_multiple: newAllowMultiple,
        is_protected: newIsProtected,
      })
      queryClient.invalidateQueries({ queryKey: ['keys'] })
      setShowAdd(false)
      setNewKey('')
      setNewLabel('')
      setNewAllowMultiple(false)
      setNewIsProtected(false)
      notify('success', 'Created', `${ik.key} added.`)
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

  const handleDelete = async (ik: InternalKey) => {
    try {
      await deleteKey(ik.id)
      queryClient.invalidateQueries({ queryKey: ['keys'] })
      setDeleteTarget(null)
      notify('success', 'Deleted', `${ik.key} removed.`)
    } catch (err: unknown) {
      notify(
        'error',
        'Delete failed',
        err instanceof Error ? err.message : 'Unknown error',
      )
    }
  }

  const handleEdit = async () => {
    if (!editTarget) return
    setEditSaving(true)
    try {
      const updated = await updateKey(editTarget.id, {
        label: editLabel.trim() || null,
        allow_multiple: editAllowMultiple,
        is_protected: editIsProtected,
      })
      queryClient.invalidateQueries({ queryKey: ['keys'] })
      setEditTarget(null)
      notify('success', 'Saved', `${updated.key} updated.`)
    } catch (err: unknown) {
      notify(
        'error',
        'Save failed',
        err instanceof Error ? err.message : 'Unknown error',
      )
    } finally {
      setEditSaving(false)
    }
  }

  return (
    <div>
      <KVTable<InternalKey>
        entries={filtered}
        loading={loading}
        getNamespace={(e) => e.key.split('.').slice(0, 2).join('.') || 'other'}
        search={search}
        onSearchChange={setSearch}
        searchPlaceholder={'Filter by key or label\u2026'}
        emptyMessage="No internal keys yet."
        loadingMessage={'Loading\u2026'}
        editingKey={null}
        editValue=""
        onEditValueChange={() => {}}
        onEditStart={() => {}}
        onEditSave={async () => {}}
        onEditCancel={() => {}}
        isValueClickable={() => false}
        renderKeySuffix={(entry) =>
          entry.is_protected ? (
            <IconLock size={11} style={{ color: '#e65100', flexShrink: 0 }} />
          ) : null
        }
        renderValue={(entry) =>
          entry.has_value ? (
            <span style={{ fontFamily: 'monospace', color: '#6b7480' }}>
              {entry.masked_value}
            </span>
          ) : (
            <em style={{ color: '#bbb' }}>empty</em>
          )
        }
        extraColumns={[
          {
            key: 'label',
            header: 'Label',
            width: 180,
            render: (entry) =>
              entry.label ? (
                <span style={{ color: '#6b7480' }}>{entry.label}</span>
              ) : (
                <em style={{ color: '#bbb' }}>{'\u2014'}</em>
              ),
          },
          {
            key: 'type',
            header: 'Type',
            width: 80,
            render: (entry) => (
              <Badge
                variant="light"
                radius="xl"
                styles={{
                  root: {
                    fontSize: 'var(--mantine-font-size-xs)',
                    padding: '1px 6px',
                    background: entry.allow_multiple ? '#e8f5e9' : '#e3f2fd',
                    color: entry.allow_multiple ? '#2e7d32' : '#1565c0',
                  },
                }}
              >
                {entry.allow_multiple ? 'array' : 'scalar'}
              </Badge>
            ),
          },
          {
            key: 'flags',
            header: 'Flags',
            width: 100,
            render: (entry) =>
              entry.is_protected ? (
                <Badge
                  variant="light"
                  radius="xl"
                  styles={{
                    root: {
                      fontSize: 'var(--mantine-font-size-xs)',
                      padding: '1px 6px',
                      background: '#fff3e0',
                      color: '#e65100',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 3,
                    },
                  }}
                >
                  <IconLock size={10} /> protected
                </Badge>
              ) : null,
          },
          {
            key: 'updated',
            header: 'Last updated',
            width: 110,
            render: (entry) =>
              entry.updated_at ? (
                <span
                  style={{
                    color: '#99a2ac',
                    fontSize: 'var(--mantine-font-size-xs)',
                  }}
                >
                  {formatRelative(entry.updated_at)}
                </span>
              ) : (
                <em style={{ color: '#bbb' }}>{'\u2014'}</em>
              ),
          },
        ]}
        renderActions={(entry) =>
          entry.is_protected ? (
            canUpdate ? (
              <Button
                variant="subtle"
                onClick={() => {
                  setEditTarget(entry)
                  setEditLabel(entry.label ?? '')
                  setEditAllowMultiple(entry.allow_multiple)
                  setEditIsProtected(entry.is_protected)
                }}
                style={{ padding: '4px 7px' }}
                title="Edit label and flags"
              >
                <IconPencil size={16} />
              </Button>
            ) : null
          ) : canCreate || canUpdate || canDelete ? (
            <>
              {canUpdate && (
                <Button
                  variant="subtle"
                  onClick={() => {
                    setEditTarget(entry)
                    setEditLabel(entry.label ?? '')
                    setEditAllowMultiple(entry.allow_multiple)
                    setEditIsProtected(entry.is_protected)
                  }}
                  style={{ padding: '4px 7px' }}
                  title="Edit label, type and flags"
                >
                  <IconPencil size={16} />
                </Button>
              )}
              {canDelete && (
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
          ) : null
        }
        toolbar={
          canCreate && (
            <Button
              variant="filled"
              onClick={() => setShowAdd(true)}
              style={{ display: 'flex', alignItems: 'center', gap: 6 }}
            >
              <IconPlus size={16} /> Add key
            </Button>
          )
        }
      />

      <Modal
        open={showAdd}
        title="Add internal key"
        onClose={() => setShowAdd(false)}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Field label="Key" hint="e.g. internal.mail.sender.invoice">
            <TextInput
              value={newKey}
              onChange={(e) => setNewKey(e.target.value)}
              placeholder="namespace.key"
            />
          </Field>
          <Field label="Label" hint="Optional display name">
            <TextInput
              value={NewLabel}
              onChange={(e) => setNewLabel(e.target.value)}
              placeholder="e.g. Invoice sender email"
            />
          </Field>
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
              checked={newAllowMultiple}
              onChange={(e) => setNewAllowMultiple(e.target.checked)}
              style={{ width: 16, height: 16, accentColor: '#fece2b' }}
            />
            <span style={{ fontWeight: 600 }}>Array key</span>
            <span
              style={{
                color: '#6b7480',
                fontSize: 'var(--mantine-font-size-xs)',
              }}
            >
              Allows multiple bindings to contribute values
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
              checked={newIsProtected}
              onChange={(e) => setNewIsProtected(e.target.checked)}
              style={{ width: 16, height: 16, accentColor: '#fece2b' }}
            />
            <span style={{ fontWeight: 600 }}>Protected</span>
            <span
              style={{
                color: '#6b7480',
                fontSize: 'var(--mantine-font-size-xs)',
              }}
            >
              Prevents deletion and type changes
            </span>
          </label>
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
              {addSaving ? 'Saving...' : 'Save'}
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        open={editTarget !== null}
        title={`Edit: ${editTarget?.key ?? ''}`}
        onClose={() => setEditTarget(null)}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Field label="Label">
            <TextInput
              value={editLabel}
              onChange={(e) => setEditLabel(e.target.value)}
              placeholder="Display name"
            />
          </Field>
          <label
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              fontSize: 'var(--mantine-font-size-sm)',
              cursor: editIsProtected ? 'not-allowed' : 'pointer',
              opacity: editIsProtected ? 0.6 : 1,
            }}
          >
            <input
              type="checkbox"
              checked={editAllowMultiple}
              onChange={(e) => setEditAllowMultiple(e.target.checked)}
              disabled={editIsProtected}
              style={{ width: 16, height: 16, accentColor: '#fece2b' }}
            />
            <span style={{ fontWeight: 600 }}>Array key</span>
            <span
              style={{
                color: '#6b7480',
                fontSize: 'var(--mantine-font-size-xs)',
              }}
            >
              {editIsProtected
                ? 'Unprotect to change type'
                : 'Allows multiple bindings to contribute values'}
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
              checked={editIsProtected}
              onChange={(e) => setEditIsProtected(e.target.checked)}
              style={{ width: 16, height: 16, accentColor: '#fece2b' }}
            />
            <span style={{ fontWeight: 600 }}>Protected</span>
            <span
              style={{
                color: '#6b7480',
                fontSize: 'var(--mantine-font-size-xs)',
              }}
            >
              Prevents deletion and type changes
            </span>
          </label>
          <div
            style={{
              display: 'flex',
              gap: 8,
              justifyContent: 'flex-end',
              marginTop: 4,
            }}
          >
            <Button variant="subtle" onClick={() => setEditTarget(null)}>
              Cancel
            </Button>
            <Button variant="filled" onClick={handleEdit} disabled={editSaving}>
              {editSaving ? 'Saving...' : 'Save'}
            </Button>
          </div>
        </div>
      </Modal>

      <ConfirmModal
        open={deleteTarget !== null}
        title="Delete key"
        body={
          deleteTarget
            ? `Delete "${deleteTarget.key}"? All bindings must be removed first.`
            : ''
        }
        onConfirm={() => {
          if (deleteTarget) handleDelete(deleteTarget)
        }}
        onClose={() => setDeleteTarget(null)}
      />
    </div>
  )
}

type BindingRow = Binding & { key: string }

function BindingsTab() {
  const { notify } = useToast()
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const canCreate = hasPermission('bindings.bindings.write')
  const canUpdate = hasPermission('bindings.bindings.write')
  const canDelete = hasPermission('bindings.bindings.delete')
  const { data: combinedData, isLoading: loading } = useQuery({
    queryKey: ['bindings'],
    queryFn: () =>
      Promise.all([listBindings(), listKeys(), getRegistry(), getValidators()]),
  })
  const bindingsData = combinedData?.[0]
  const bindings = useMemo(() => bindingsData ?? [], [bindingsData])
  const keys = combinedData?.[1] ?? []
  const registry = combinedData?.[2] ?? []
  const validators = combinedData?.[3] ?? []
  const [search, setSearch] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [addSaving, setAddSaving] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<Binding | null>(null)
  const [editTarget, setEditTarget] = useState<Binding | null>(null)
  const [editSaving, setEditSaving] = useState(false)

  const [newType, setNewType] = useState('member')
  const [newSourceId, setNewSourceId] = useState('')
  const [newAttribute, setNewAttribute] = useState('')
  const [newKeyId, setNewKeyId] = useState('')
  const [newValidator, setNewValidator] = useState('none')

  const { data: sources = [], isLoading: sourcesLoading } = useQuery({
    queryKey: ['binding-sources', newType],
    queryFn: () => getSources(newType),
    enabled: showAdd,
  })
  const [selectedSource, setSelectedSource] = useState<BindingSource | null>(
    null,
  )

  const { data: newPreview } = useQuery<BindingPreview>({
    queryKey: ['binding-preview', newType, newSourceId, newAttribute],
    queryFn: () => previewBindingValue(newType, newSourceId, newAttribute),
    enabled: !!newSourceId && !!newAttribute,
  })

  // Edit modal state
  const [editType, setEditType] = useState('member')
  const [editSourceId, setEditSourceId] = useState('')
  const [editAttribute, setEditAttribute] = useState('')
  const [editKeyId, setEditKeyId] = useState('')
  const [editValidator, setEditValidator] = useState('none')
  const [editProtected, setEditProtected] = useState(false)

  const { data: editSources = [], isLoading: editSourcesLoading } = useQuery({
    queryKey: ['binding-sources', editType],
    queryFn: () => getSources(editType),
    enabled: editTarget !== null,
  })
  const [editSelectedSource, setEditSelectedSource] =
    useState<BindingSource | null>(null)

  const { data: editPreview } = useQuery<BindingPreview>({
    queryKey: ['binding-preview', editType, editSourceId, editAttribute],
    queryFn: () => previewBindingValue(editType, editSourceId, editAttribute),
    enabled: !!editSourceId && !!editAttribute,
  })

  const currentRegistry = registry.find((r) => r.type === newType)
  const editRegistry = registry.find((r) => r.type === editType)

  const allAttributes = useMemo(() => {
    const attrs = currentRegistry?.attributes ?? []
    const aliasOpts = (selectedSource?.aliases ?? []).map((a) => ({
      name: `additional_alias:${a.id}`,
      label: `Additional alias: ${a.address}`,
    }))
    return [...attrs, ...aliasOpts]
  }, [currentRegistry, selectedSource])

  const autoEditSource = useMemo(
    () =>
      editSourceId && editSources.length > 0
        ? editSources.find((s) => s.id === editSourceId) ?? null
        : null,
    [editSources, editSourceId],
  )
  const effectiveEditSource = editSelectedSource ?? autoEditSource

  const editAllAttributes = useMemo(() => {
    const attrs = editRegistry?.attributes ?? []
    const aliasOpts = (effectiveEditSource?.aliases ?? []).map((a) => ({
      name: `additional_alias:${a.id}`,
      label: `Additional alias: ${a.address}`,
    }))
    return [...attrs, ...aliasOpts]
  }, [editRegistry, effectiveEditSource])

  const rows: BindingRow[] = useMemo(
    () =>
      bindings.map((b) => ({
        ...b,
        key: b.key_name ?? `#${b.id}`,
      })),
    [bindings],
  )

  const filtered = useMemo(() => {
    if (!search.trim()) return rows
    const q = search.toLowerCase()
    return rows.filter(
      (r) =>
        r.key.toLowerCase().includes(q) ||
        (r.source_label?.toLowerCase().includes(q) ?? false) ||
        r.source_attribute.toLowerCase().includes(q) ||
        r.type.toLowerCase().includes(q),
    )
  }, [rows, search])

  const handleAdd = async () => {
    if (!newType || !newSourceId || !newAttribute || !newKeyId) return
    setAddSaving(true)
    try {
      const b = await createBinding({
        type: newType,
        source_id: newSourceId,
        source_attribute: newAttribute,
        key_id: parseInt(newKeyId, 10),
        validator: newValidator,
      })
      queryClient.invalidateQueries({ queryKey: ['bindings'] })
      setShowAdd(false)
      setNewSourceId('')
      setNewAttribute('')
      setNewKeyId('')
      setNewValidator('none')
      setSelectedSource(null)
      notify('success', 'Created', `Binding #${b.id} created.`)
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

  const handleDelete = async (b: Binding) => {
    try {
      await deleteBinding(b.id)
      queryClient.invalidateQueries({ queryKey: ['bindings'] })
      setDeleteTarget(null)
      notify('success', 'Deleted', `Binding #${b.id} removed.`)
    } catch (err: unknown) {
      notify(
        'error',
        'Delete failed',
        err instanceof Error ? err.message : 'Unknown error',
      )
    }
  }

  const handleToggle = async (b: Binding) => {
    try {
      const updated = await toggleBinding(b.id, !b.enabled)
      queryClient.invalidateQueries({ queryKey: ['bindings'] })
      notify(
        'success',
        updated.enabled ? 'Enabled' : 'Disabled',
        `Binding #${b.id} ${updated.enabled ? 'enabled' : 'disabled'}.`,
      )
    } catch (err: unknown) {
      notify(
        'error',
        'Toggle failed',
        err instanceof Error ? err.message : 'Unknown error',
      )
    }
  }

  const openEdit = (entry: Binding) => {
    setEditTarget(entry)
    setEditType(entry.type)
    setEditSourceId(entry.source_id)
    setEditAttribute(entry.source_attribute)
    setEditKeyId(String(entry.key_id))
    setEditValidator(entry.validator)
    setEditProtected(entry.is_protected)
    setEditSelectedSource(null)
  }

  const handleEdit = async () => {
    if (!editTarget) return
    setEditSaving(true)
    try {
      const data: Record<string, unknown> = {
        validator: editValidator,
      }
      if (editType !== editTarget.type) data.type = editType
      if (editSourceId !== editTarget.source_id) data.source_id = editSourceId
      if (editAttribute !== editTarget.source_attribute)
        data.source_attribute = editAttribute
      if (editKeyId && parseInt(editKeyId, 10) !== editTarget.key_id)
        data.key_id = parseInt(editKeyId, 10)
      if (editProtected !== editTarget.is_protected)
        data.is_protected = editProtected

      const updated = await updateBinding(editTarget.id, data)
      queryClient.invalidateQueries({ queryKey: ['bindings'] })
      setEditTarget(null)
      notify('success', 'Saved', `Binding #${updated.id} updated.`)
    } catch (err: unknown) {
      notify(
        'error',
        'Save failed',
        err instanceof Error ? err.message : 'Unknown error',
      )
    } finally {
      setEditSaving(false)
    }
  }

  return (
    <div>
      <KVTable<BindingRow>
        entries={filtered}
        loading={loading}
        getNamespace={() => 'bindings'}
        search={search}
        onSearchChange={setSearch}
        searchPlaceholder={'Filter by key, source, or attribute\u2026'}
        emptyMessage="No bindings yet."
        loadingMessage={'Loading\u2026'}
        editingKey={null}
        editValue=""
        onEditValueChange={() => {}}
        onEditStart={() => {}}
        onEditSave={async () => {}}
        onEditCancel={() => {}}
        isValueClickable={() => false}
        renderKeyPrefix={(entry) => (
          <span
            style={{
              color: '#99a2ac',
              fontSize: 'var(--mantine-font-size-xs)',
              flexShrink: 0,
            }}
          >
            #{entry.id}
          </span>
        )}
        renderKeySuffix={(entry) =>
          entry.is_protected ? (
            <IconLock size={11} style={{ color: '#e65100', flexShrink: 0 }} />
          ) : null
        }
        renderKeyBelow={(entry) => (
          <span
            style={{
              fontSize: 'var(--mantine-font-size-xs)',
              color: '#99a2ac',
              textTransform: 'capitalize',
            }}
          >
            {entry.type} . {entry.source_attribute}
          </span>
        )}
        renderValue={(entry) => (
          <span style={{ fontWeight: 500 }}>
            {entry.source_label || entry.source_id}
          </span>
        )}
        extraColumns={[
          {
            key: 'value',
            header: 'Value',
            width: 180,
            render: (entry) =>
              entry.resolved_value ? (
                entry.resolved_sensitive ? (
                  <span style={{ color: '#bbb', fontStyle: 'italic' }}>
                    {'\u2022\u2022\u2022\u2022\u2022'}
                  </span>
                ) : (
                  <span
                    style={{
                      fontFamily: 'monospace',
                      color: '#3a4048',
                      fontSize: 'var(--mantine-font-size-xs)',
                    }}
                  >
                    {entry.resolved_value}
                  </span>
                )
              ) : (
                <em style={{ color: '#bbb' }}>{'\u2014'}</em>
              ),
          },
          {
            key: 'validator',
            header: 'Validator',
            width: 100,
            render: (entry) => (
              <Badge
                variant="light"
                radius="xl"
                styles={{
                  root: {
                    fontSize: 'var(--mantine-font-size-xs)',
                    padding: '1px 6px',
                    background: '#f4f0ff',
                    color: '#7c4dcc',
                  },
                }}
              >
                {entry.validator}
              </Badge>
            ),
          },
          {
            key: 'flags',
            header: 'Flags',
            width: 100,
            render: (entry) =>
              entry.is_protected ? (
                <Badge
                  variant="light"
                  radius="xl"
                  styles={{
                    root: {
                      fontSize: 'var(--mantine-font-size-xs)',
                      padding: '1px 6px',
                      background: '#fff3e0',
                      color: '#e65100',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 3,
                    },
                  }}
                >
                  <IconLock size={10} /> protected
                </Badge>
              ) : null,
          },
          {
            key: 'status',
            header: 'Status',
            width: 70,
            render: (entry) =>
              entry.validation_status === 'ok' ? (
                <span
                  style={{
                    color: '#27ae60',
                    fontSize: 'var(--mantine-font-size-xs)',
                  }}
                >
                  ok
                </span>
              ) : (
                <span
                  style={{
                    color: '#e74c3c',
                    fontSize: 'var(--mantine-font-size-xs)',
                  }}
                  title={entry.validation_error ?? undefined}
                >
                  failed
                </span>
              ),
          },
          {
            key: 'enabled',
            header: 'Enabled',
            width: 80,
            render: (entry) => (
              <Button
                variant="subtle"
                onClick={() => handleToggle(entry)}
                disabled={entry.is_protected}
                style={{
                  padding: '3px 8px',
                  fontSize: 'var(--mantine-font-size-xs)',
                  color: entry.enabled ? '#27ae60' : '#99a2ac',
                  cursor: entry.is_protected ? 'not-allowed' : 'pointer',
                }}
                title={
                  entry.is_protected
                    ? 'Protected \u2014 cannot toggle'
                    : entry.enabled
                      ? 'Click to disable'
                      : 'Click to enable'
                }
              >
                <IconPower size={16} style={{ verticalAlign: 'middle' }} />
                {entry.enabled ? 'on' : 'off'}
              </Button>
            ),
          },
          {
            key: 'updated',
            header: 'Last updated',
            width: 110,
            render: (entry) =>
              entry.updated_at ? (
                <span
                  style={{
                    color: '#99a2ac',
                    fontSize: 'var(--mantine-font-size-xs)',
                  }}
                >
                  {formatRelative(entry.updated_at)}
                </span>
              ) : (
                <em style={{ color: '#bbb' }}>{'\u2014'}</em>
              ),
          },
        ]}
        renderActions={(entry) =>
          entry.is_protected ? (
            canUpdate ? (
              <Button
                variant="subtle"
                onClick={() => openEdit(entry)}
                style={{ padding: '4px 7px' }}
                title="Edit source, destination, and validator"
              >
                <IconPencil size={16} />
              </Button>
            ) : null
          ) : canUpdate || canDelete ? (
            <>
              {canUpdate && (
                <Button
                  variant="subtle"
                  onClick={() => openEdit(entry)}
                  style={{ padding: '4px 7px' }}
                  title="Edit source, destination, and validator"
                >
                  <IconPencil size={16} />
                </Button>
              )}
              {canDelete && (
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
          ) : null
        }
        toolbar={
          canCreate && (
            <Button
              variant="filled"
              onClick={() => setShowAdd(true)}
              style={{ display: 'flex', alignItems: 'center', gap: 6 }}
            >
              <IconPlus size={16} /> Add binding
            </Button>
          )
        }
      />

      <Modal
        open={showAdd}
        title="Add binding"
        onClose={() => setShowAdd(false)}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Field label="Source type">
            <Select
              data={registry.map((r) => ({ value: r.type, label: r.type }))}
              value={newType}
              onChange={(v) => {
                setNewType(v ?? '')
                setNewAttribute('')
                setNewSourceId('')
                setSelectedSource(null)
              }}
            />
          </Field>
          <Field label="Source" hint="Select a source record">
            {sourcesLoading ? (
              <div
                style={{
                  color: '#99a2ac',
                  fontSize: 'var(--mantine-font-size-sm)',
                  padding: '8px 0',
                }}
              >
                Loading sources...
              </div>
            ) : sources.length === 0 ? (
              <div
                style={{
                  color: '#99a2ac',
                  fontSize: 'var(--mantine-font-size-sm)',
                  padding: '8px 0',
                }}
              >
                No {newType} records available.
              </div>
            ) : (
              <Select
                data={[
                  { value: '', label: `Select ${newType}...` },
                  ...sources.map((s) => ({ value: s.id, label: s.label })),
                ]}
                value={newSourceId}
                onChange={(v) => {
                  setNewSourceId(v ?? '')
                  const found = sources.find((s) => s.id === v)
                  setSelectedSource(found ?? null)
                }}
                searchable
              />
            )}
          </Field>
          {selectedSource && (
            <div
              style={{
                background: '#f4f8f5',
                border: '1px solid #d3ddd7',
                borderRadius: 8,
                padding: '12px 14px',
                display: 'grid',
                gridTemplateColumns: 'auto 1fr',
                gap: '4px 16px',
                fontSize: 'var(--mantine-font-size-xs)',
              }}
            >
              {Object.entries(selectedSource.preview)
                .filter(([k]) => !/password|secret|token|credential/i.test(k))
                .map(([k, v]) => (
                  <div key={k} style={{ display: 'contents' }}>
                    <span style={{ color: '#6b7480', fontWeight: 500 }}>
                      {k}
                    </span>
                    <span style={{ color: '#3a4048' }}>
                      {v === null || v === undefined ? '\u2014' : String(v)}
                    </span>
                  </div>
                ))}
            </div>
          )}
          <Field label="Attribute">
            <Select
              data={[
                { value: '', label: 'Select attribute...' },
                ...allAttributes.map((a) => ({
                  value: a.name,
                  label: `${a.label} (${a.name})`,
                })),
              ]}
              value={newAttribute}
              onChange={(v) => setNewAttribute(v ?? '')}
              searchable
            />
          </Field>
          {newSourceId && newAttribute && (
            <div
              style={{
                background: '#f4f8f5',
                border: '1px solid #d3ddd7',
                borderRadius: 8,
                padding: '10px 14px',
                fontSize: 'var(--mantine-font-size-sm)',
              }}
            >
              <span style={{ color: '#6b7480', fontWeight: 500 }}>
                Current value:{' '}
              </span>
              {newPreview?.masked ? (
                <span style={{ color: '#bbb', fontStyle: 'italic' }}>
                  {'\u2022\u2022\u2022\u2022\u2022 (hidden)'}
                </span>
              ) : newPreview?.value ? (
                <span style={{ color: '#3a4048' }}>{newPreview.value}</span>
              ) : (
                <em style={{ color: '#bbb' }}>{'\u2014 (empty)'}</em>
              )}
            </div>
          )}
          <Field label="Target key">
            <Select
              data={[
                { value: '', label: 'Select key...' },
                ...keys.map((k) => ({
                  value: String(k.id),
                  label: `${k.key}${k.label ? ` — ${k.label}` : ''}`,
                })),
              ]}
              value={newKeyId}
              onChange={(v) => setNewKeyId(v ?? '')}
              searchable
            />
          </Field>
          <Field label="Validator">
            <Select
              data={validators.map((v) => ({ value: v, label: v }))}
              value={newValidator}
              onChange={(v) => setNewValidator(v ?? '')}
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
              disabled={addSaving || !newSourceId || !newAttribute || !newKeyId}
            >
              {addSaving ? 'Saving...' : 'Save'}
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        open={editTarget !== null}
        title={`Edit binding #${editTarget?.id ?? ''}`}
        onClose={() => setEditTarget(null)}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Field label="Source type">
            <Select
              data={registry.map((r) => ({ value: r.type, label: r.type }))}
              value={editType}
              onChange={(v) => {
                setEditType(v ?? '')
                setEditAttribute('')
                setEditSourceId('')
                setEditSelectedSource(null)
              }}
            />
          </Field>
          <Field label="Source" hint="Select a source record">
            {editSourcesLoading ? (
              <div
                style={{
                  color: '#99a2ac',
                  fontSize: 'var(--mantine-font-size-sm)',
                  padding: '8px 0',
                }}
              >
                Loading sources...
              </div>
            ) : editSources.length === 0 ? (
              <div
                style={{
                  color: '#99a2ac',
                  fontSize: 'var(--mantine-font-size-sm)',
                  padding: '8px 0',
                }}
              >
                No {editType} records available.
              </div>
            ) : (
              <Select
                data={[
                  { value: '', label: `Select ${editType}...` },
                  ...editSources.map((s) => ({ value: s.id, label: s.label })),
                ]}
                value={editSourceId}
                onChange={(v) => {
                  setEditSourceId(v ?? '')
                  const found = editSources.find((s) => s.id === v)
                  setEditSelectedSource(found ?? null)
                }}
                searchable
              />
            )}
          </Field>
          {effectiveEditSource && (
            <div
              style={{
                background: '#f4f8f5',
                border: '1px solid #d3ddd7',
                borderRadius: 8,
                padding: '12px 14px',
                display: 'grid',
                gridTemplateColumns: 'auto 1fr',
                gap: '4px 16px',
                fontSize: 'var(--mantine-font-size-xs)',
              }}
            >
              {Object.entries(effectiveEditSource.preview)
                .filter(([k]) => !/password|secret|token|credential/i.test(k))
                .map(([k, v]) => (
                  <div key={k} style={{ display: 'contents' }}>
                    <span style={{ color: '#6b7480', fontWeight: 500 }}>
                      {k}
                    </span>
                    <span style={{ color: '#3a4048' }}>
                      {v === null || v === undefined ? '\u2014' : String(v)}
                    </span>
                  </div>
                ))}
            </div>
          )}
          <Field label="Attribute">
            <Select
              data={[
                { value: '', label: 'Select attribute...' },
                ...editAllAttributes.map((a) => ({
                  value: a.name,
                  label: `${a.label} (${a.name})`,
                })),
              ]}
              value={editAttribute}
              onChange={(v) => setEditAttribute(v ?? '')}
              searchable
            />
          </Field>
          {editSourceId && editAttribute && (
            <div
              style={{
                background: '#f4f8f5',
                border: '1px solid #d3ddd7',
                borderRadius: 8,
                padding: '10px 14px',
                fontSize: 'var(--mantine-font-size-sm)',
              }}
            >
              <span style={{ color: '#6b7480', fontWeight: 500 }}>
                Current value:{' '}
              </span>
              {editPreview?.masked ? (
                <span style={{ color: '#bbb', fontStyle: 'italic' }}>
                  {'\u2022\u2022\u2022\u2022\u2022 (hidden)'}
                </span>
              ) : editPreview?.value ? (
                <span style={{ color: '#3a4048' }}>{editPreview.value}</span>
              ) : (
                <em style={{ color: '#bbb' }}>{'\u2014 (empty)'}</em>
              )}
            </div>
          )}
          <Field label="Target key">
            <Select
              data={[
                { value: '', label: 'Select key...' },
                ...keys.map((k) => ({
                  value: String(k.id),
                  label: `${k.key}${k.label ? ` — ${k.label}` : ''}`,
                })),
              ]}
              value={editKeyId}
              onChange={(v) => setEditKeyId(v ?? '')}
              searchable
            />
          </Field>
          <Field label="Validator">
            <Select
              data={validators.map((v) => ({ value: v, label: v }))}
              value={editValidator}
              onChange={(v) => setEditValidator(v ?? '')}
            />
          </Field>
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
              checked={editProtected}
              onChange={(e) => setEditProtected(e.target.checked)}
              style={{ width: 16, height: 16, accentColor: '#fece2b' }}
            />
            <span style={{ fontWeight: 600 }}>Protected</span>
            <span
              style={{
                color: '#6b7480',
                fontSize: 'var(--mantine-font-size-xs)',
              }}
            >
              Prevents deletion and enable/disable toggle
            </span>
          </label>
          <div
            style={{
              display: 'flex',
              gap: 8,
              justifyContent: 'flex-end',
              marginTop: 4,
            }}
          >
            <Button variant="subtle" onClick={() => setEditTarget(null)}>
              Cancel
            </Button>
            <Button variant="filled" onClick={handleEdit} disabled={editSaving}>
              {editSaving ? 'Saving...' : 'Save'}
            </Button>
          </div>
        </div>
      </Modal>

      <ConfirmModal
        open={deleteTarget !== null}
        title="Delete binding"
        body={
          deleteTarget
            ? `Delete binding #${deleteTarget.id} (${deleteTarget.type}.${deleteTarget.source_attribute} -> ${deleteTarget.key_name})?`
            : ''
        }
        onConfirm={() => {
          if (deleteTarget) handleDelete(deleteTarget)
        }}
        onClose={() => setDeleteTarget(null)}
      />
    </div>
  )
}
