import { useState, useMemo } from 'react'
import { Badge, Button } from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { IconPlus, IconTrash, IconLock, IconPencil, IconPower } from '@tabler/icons-react'
import { useToast, useAuth } from '@/context/AppContext'
import { useT } from '@/locales/i18n'
import { ConfirmModal, KVTable } from '@/components/ui'
import { formatRelative } from '@/format'
import {
  listKeys,
  listBindings,
  createBinding,
  updateBinding,
  deleteBinding,
  toggleBinding,
  getRegistry,
  getValidators,
} from '@/api/bindings'
import type { Binding } from '@/api/bindings'
import { qk } from '@/data/keys'
import { BindingFormModal, type BindingInput } from './BindingFormModal'

type BindingRow = Binding & { key: string }

export function BindingsTab() {
  const { notify } = useToast()
  const { t } = useT()
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const canCreate = hasPermission('bindings.bindings.write')
  const canUpdate = hasPermission('bindings.bindings.write')
  const canDelete = hasPermission('bindings.bindings.delete')
  const { data: combinedData, isLoading: loading } = useQuery({
    queryKey: qk.bindings.all,
    queryFn: () =>
      Promise.all([listBindings(), listKeys(), getRegistry(), getValidators()]),
  })
  const bindingsData = combinedData?.[0]
  const bindings = useMemo(() => bindingsData ?? [], [bindingsData])
  const keys = combinedData?.[1] ?? []
  const registry = combinedData?.[2] ?? []
  const validators = combinedData?.[3] ?? []
  const [search, setSearch] = useState('')
  // 'new' opens the form for a new binding, a binding opens it for that one.
  const [formTarget, setFormTarget] = useState<Binding | 'new' | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Binding | null>(null)

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

  const handleAdd = async (input: BindingInput) => {
    try {
      const b = await createBinding({
        type: input.type,
        source_id: input.source_id,
        source_attribute: input.source_attribute,
        key_id: input.key_id,
        validator: input.validator,
      })
      queryClient.invalidateQueries({ queryKey: qk.bindings.all })
      setFormTarget(null)
      notify('success', t('common.created', 'Erstellt'), t('bindings.createdMsg', 'Verknüpfung #{{id}} erstellt.', { id: b.id }))
    } catch (err: unknown) {
      notify(
        'error',
        t('common.createFailed', 'Erstellen fehlgeschlagen'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    }
  }

  const handleDelete = async (b: Binding) => {
    try {
      await deleteBinding(b.id)
      queryClient.invalidateQueries({ queryKey: qk.bindings.all })
      setDeleteTarget(null)
      notify('success', t('common.deleted', 'Gelöscht'), t('bindings.removedMsg', 'Verknüpfung #{{id}} entfernt.', { id: b.id }))
    } catch (err: unknown) {
      notify(
        'error',
        t('common.deleteFailed', 'Löschen fehlgeschlagen'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    }
  }

  const handleToggle = async (b: Binding) => {
    try {
      const updated = await toggleBinding(b.id, !b.enabled)
      queryClient.invalidateQueries({ queryKey: qk.bindings.all })
      notify(
        'success',
        updated.enabled ? t('common.enabled', 'Aktiviert') : t('common.disabled', 'Deaktiviert'),
        updated.enabled
          ? t('bindings.enabledMsg', 'Verknüpfung #{{id}} aktiviert.', { id: b.id })
          : t('bindings.disabledMsg', 'Verknüpfung #{{id}} deaktiviert.', { id: b.id }),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.updateFailed', 'Aktualisieren fehlgeschlagen'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    }
  }

  const handleEdit = async (target: Binding, input: BindingInput) => {
    try {
      // Send only what changed, besides the validator.
      const data: Parameters<typeof updateBinding>[1] = { validator: input.validator }
      if (input.type !== target.type) data.type = input.type
      if (input.source_id !== target.source_id) data.source_id = input.source_id
      if (input.source_attribute !== target.source_attribute) data.source_attribute = input.source_attribute
      if (input.key_id !== target.key_id) data.key_id = input.key_id
      if (input.is_protected !== target.is_protected) data.is_protected = input.is_protected
      const updated = await updateBinding(target.id, data)
      queryClient.invalidateQueries({ queryKey: qk.bindings.all })
      setFormTarget(null)
      notify('success', t('common.saved', 'Gespeichert'), t('bindings.updatedMsg', 'Verknüpfung #{{id}} gespeichert.', { id: updated.id }))
    } catch (err: unknown) {
      notify(
        'error',
        t('common.saveFailed', 'Speichern fehlgeschlagen'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
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
        searchPlaceholder={t('bindings.filterBindings', 'Nach Schlüssel, Quelle oder Attribut filtern …')}
        emptyMessage={t('bindings.noBindings', 'Noch keine Verknüpfungen.')}
        loadingMessage={t('common.loading', 'Wird geladen …')}
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
              color: '#8c86a0',
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
              color: '#8c86a0',
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
            header: t('data.value', 'Wert'),
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
                      color: '#2e2940',
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
            header: t('bindings.validator', 'Prüfung'),
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
                  <IconLock size={10} /> protected
                </Badge>
              ) : null,
          },
          {
            key: 'status',
            header: t('common.status', 'Status'),
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
            header: t('common.enabled', 'Aktiviert'),
            width: 80,
            render: (entry) => (
              <Button
                variant="subtle"
                onClick={() => handleToggle(entry)}
                disabled={entry.is_protected}
                style={{
                  padding: '3px 8px',
                  fontSize: 'var(--mantine-font-size-xs)',
                  color: entry.enabled ? '#27ae60' : '#8c86a0',
                  cursor: entry.is_protected ? 'not-allowed' : 'pointer',
                }}
                title={
                  entry.is_protected
                    ? t('bindings.protectedToggle', 'Geschützt: kann nicht umgeschaltet werden')
                    : entry.enabled
                      ? t('bindings.clickDisable', 'Zum Deaktivieren klicken')
                      : t('bindings.clickEnable', 'Zum Aktivieren klicken')
                }
              >
                <IconPower size={16} style={{ verticalAlign: 'middle' }} />
                {entry.enabled ? 'on' : 'off'}
              </Button>
            ),
          },
          {
            key: 'updated',
            header: t('bindings.lastUpdated', 'Zuletzt geändert'),
            width: 110,
            render: (entry) =>
              entry.updated_at ? (
                <span
                  style={{
                    color: '#8c86a0',
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
                onClick={() => setFormTarget(entry)}
                style={{ padding: '4px 7px' }}
                title={t('bindings.editBinding', 'Quelle, Ziel und Prüfung bearbeiten')}
              >
                <IconPencil size={16} />
              </Button>
            ) : null
          ) : canUpdate || canDelete ? (
            <>
              {canUpdate && (
                <Button
                  variant="subtle"
                  onClick={() => setFormTarget(entry)}
                  style={{ padding: '4px 7px' }}
                  title={t('bindings.editBinding', 'Quelle, Ziel und Prüfung bearbeiten')}
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
              onClick={() => setFormTarget('new')}
              style={{ display: 'flex', alignItems: 'center', gap: 6 }}
            >
              <IconPlus size={16} /> {t('bindings.add', 'Verknüpfung hinzufügen')}
            </Button>
          )
        }
      />

      <BindingFormModal
        key={formTarget === 'new' ? 'new' : (formTarget?.id ?? 'closed')}
        open={formTarget !== null}
        binding={formTarget === 'new' ? null : formTarget}
        registry={registry}
        keys={keys}
        validators={validators}
        onClose={() => setFormTarget(null)}
        onSubmit={(input) =>
          formTarget === 'new' || formTarget === null ? handleAdd(input) : handleEdit(formTarget, input)
        }
      />

      <ConfirmModal
        open={deleteTarget !== null}
        title={t('bindings.deleteBinding', 'Verknüpfung löschen')}
        body={
          deleteTarget
            ? t('bindings.deleteBody', 'Verknüpfung #{{id}} ({{source}} → {{key}}) löschen?', { id: deleteTarget.id, source: `${deleteTarget.type}.${deleteTarget.source_attribute}`, key: deleteTarget.key_name })
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
