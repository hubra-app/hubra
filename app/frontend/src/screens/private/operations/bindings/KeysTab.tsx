import { useState, useMemo } from 'react'
import { Badge, Button, TextInput } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { IconPlus, IconTrash, IconLock, IconPencil } from '@tabler/icons-react'
import { useToast, useAuth } from '@/context/AppContext'
import { useT } from '@/locales/i18n'
import { Modal, Field, ConfirmModal, KVTable } from '@/components/ui'
import { formatRelative } from '@/format'
import { listKeys, createKey, updateKey, deleteKey } from '@/api/bindings'
import type { InternalKey } from '@/api/bindings'
import { qk } from '@/data/keys'

export function KeysTab() {
  const { notify } = useToast()
  const { t } = useT()
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const canCreate = hasPermission('keys.keys.write')
  const canUpdate = hasPermission('keys.keys.write')
  const canDelete = hasPermission('keys.keys.delete')
  const { data: keys = [], isLoading: loading } = useQuery({
    queryKey: qk.keys,
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
      queryClient.invalidateQueries({ queryKey: qk.keys })
      setShowAdd(false)
      setNewKey('')
      setNewLabel('')
      setNewAllowMultiple(false)
      setNewIsProtected(false)
      notify('success', t('common.created', 'Erstellt'), t('kv.addedMsg', '{{key}} wurde hinzugefügt.', { key: ik.key }))
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

  const handleDelete = async (ik: InternalKey) => {
    try {
      await deleteKey(ik.id)
      queryClient.invalidateQueries({ queryKey: qk.keys })
      setDeleteTarget(null)
      notify('success', t('common.deleted', 'Gelöscht'), t('kv.removedMsg', '{{key}} wurde entfernt.', { key: ik.key }))
    } catch (err: unknown) {
      notify(
        'error',
        t('common.deleteFailed', 'Löschen fehlgeschlagen'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
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
      queryClient.invalidateQueries({ queryKey: qk.keys })
      setEditTarget(null)
      notify('success', t('common.saved', 'Gespeichert'), t('kv.updatedMsg', '{{key}} wurde gespeichert.', { key: updated.key }))
    } catch (err: unknown) {
      notify(
        'error',
        t('common.saveFailed', 'Speichern fehlgeschlagen'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
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
        searchPlaceholder={t('bindings.filterKeys', 'Nach Schlüssel oder Bezeichnung filtern …')}
        emptyMessage={t('bindings.noKeys', 'Noch keine internen Schlüssel.')}
        loadingMessage={t('common.loading', 'Wird geladen …')}
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
            <span style={{ fontFamily: 'monospace', color: 'var(--hb-text-2)' }}>
              {entry.masked_value}
            </span>
          ) : (
            <em style={{ color: '#bbb' }}>{t('bindings.empty', 'leer')}</em>
          )
        }
        extraColumns={[
          {
            key: 'label',
            header: t('bindings.label', 'Bezeichnung'),
            width: 180,
            render: (entry) =>
              entry.label ? (
                <span style={{ color: 'var(--hb-text-2)' }}>{entry.label}</span>
              ) : (
                <em style={{ color: '#bbb' }}>{'\u2014'}</em>
              ),
          },
          {
            key: 'type',
            header: t('common.type', 'Typ'),
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
            header: t('bindings.flags', 'Eigenschaften'),
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
                  <IconLock size={10} /> {t('bindings.protected', 'Geschützt')}
                </Badge>
              ) : null,
          },
          {
            key: 'updated',
            header: t('bindings.lastUpdated', 'Zuletzt geändert'),
            width: 110,
            render: (entry) =>
              entry.updated_at ? (
                <span
                  style={{
                    color: 'var(--hb-text-3)',
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
                title={t('bindings.editLabelFlags', 'Bezeichnung und Eigenschaften bearbeiten')}
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
                  title={t('bindings.editLabelTypeFlags', 'Bezeichnung, Typ und Eigenschaften bearbeiten')}
                >
                  <IconPencil size={16} />
                </Button>
              )}
              {canDelete && (
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
          ) : null
        }
        toolbar={
          canCreate && (
            <Button
              variant="filled"
              onClick={() => setShowAdd(true)}
              style={{ display: 'flex', alignItems: 'center', gap: 6 }}
            >
              <IconPlus size={16} /> {t('bindings.addKey', 'Internen Schlüssel hinzufügen')}
            </Button>
          )
        }
      />

      <Modal
        open={showAdd}
        title={t('bindings.addKey', 'Internen Schlüssel hinzufügen')}
        onClose={() => setShowAdd(false)}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Field label={t('data.key', 'Schlüssel')} hint={t('bindings.keyHint', 'z. B. internal.mail.sender.invoice')}>
            <TextInput
              value={newKey}
              onChange={(e) => setNewKey(e.target.value)}
              placeholder="namespace.key"
            />
          </Field>
          <Field label={t('bindings.label', 'Bezeichnung')} hint={t('bindings.labelHint', 'Optionaler Anzeigename')}>
            <TextInput
              value={NewLabel}
              onChange={(e) => setNewLabel(e.target.value)}
              placeholder={t('bindings.labelPlaceholder', 'z. B. Absender für Rechnungen')}
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
              style={{ width: 16, height: 16, accentColor: 'var(--mantine-color-acc-6)' }}
            />
            <span style={{ fontWeight: 600 }}>{t('bindings.arrayKey', 'Listen-Schlüssel')}</span>
            <span
              style={{
                color: 'var(--hb-text-2)',
                fontSize: 'var(--mantine-font-size-xs)',
              }}
            >
              {t('bindings.arrayKeyHint', 'Mehrere Verknüpfungen können Werte beisteuern')}
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
              style={{ width: 16, height: 16, accentColor: 'var(--mantine-color-acc-6)' }}
            />
            <span style={{ fontWeight: 600 }}>{t('bindings.protected', 'Geschützt')}</span>
            <span
              style={{
                color: 'var(--hb-text-2)',
                fontSize: 'var(--mantine-font-size-xs)',
              }}
            >
              {t('bindings.protectedHint', 'Verhindert Löschen und Typänderungen')}
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

      <Modal
        open={editTarget !== null}
        title={t('bindings.editKeyTitle', 'Bearbeiten: {{key}}', { key: editTarget?.key ?? '' })}
        onClose={() => setEditTarget(null)}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Field label={t('bindings.label', 'Bezeichnung')}>
            <TextInput
              value={editLabel}
              onChange={(e) => setEditLabel(e.target.value)}
              placeholder={t('common.displayName', 'Anzeigename')}
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
              style={{ width: 16, height: 16, accentColor: 'var(--mantine-color-acc-6)' }}
            />
            <span style={{ fontWeight: 600 }}>{t('bindings.arrayKey', 'Listen-Schlüssel')}</span>
            <span
              style={{
                color: 'var(--hb-text-2)',
                fontSize: 'var(--mantine-font-size-xs)',
              }}
            >
              {editIsProtected
                ? t('bindings.unprotectHint', 'Schutz aufheben, um den Typ zu ändern')
                : t('bindings.arrayKeyHint', 'Mehrere Verknüpfungen können Werte beisteuern')}
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
              style={{ width: 16, height: 16, accentColor: 'var(--mantine-color-acc-6)' }}
            />
            <span style={{ fontWeight: 600 }}>{t('bindings.protected', 'Geschützt')}</span>
            <span
              style={{
                color: 'var(--hb-text-2)',
                fontSize: 'var(--mantine-font-size-xs)',
              }}
            >
              {t('bindings.protectedHint', 'Verhindert Löschen und Typänderungen')}
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
              {t('common.cancel', 'Abbrechen')}
            </Button>
            <Button variant="filled" onClick={handleEdit} disabled={editSaving}>
              {editSaving ? t('common.saving', 'Wird gespeichert …') : t('common.save', 'Speichern')}
            </Button>
          </div>
        </div>
      </Modal>

      <ConfirmModal
        open={deleteTarget !== null}
        title={t('bindings.deleteKey', 'Schlüssel löschen')}
        body={
          deleteTarget
            ? t('bindings.deleteKeyBody', '«{{key}}» löschen? Alle Verknüpfungen müssen vorher entfernt werden.', { key: deleteTarget.key })
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
