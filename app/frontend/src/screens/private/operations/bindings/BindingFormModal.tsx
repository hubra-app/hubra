import { useMemo, useState } from 'react'
import { Button, Select } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import {
  getSources,
  previewBindingValue,
  type Binding,
  type BindingPreview,
  type BindingSource,
  type InternalKey,
  type RegistryEntry,
} from '@/api/bindings'
import { Modal, Field } from '@/components/ui'
import { qk } from '@/data/keys'
import { useT } from '@/locales/i18n'

export interface BindingInput {
  type: string
  source_id: string
  source_attribute: string
  key_id: number
  validator: string
  is_protected: boolean
}

const box = {
  background: 'var(--hb-surface-2)',
  border: '1px solid var(--hb-border)',
  borderRadius: 8,
} as const
const muted = {
  color: 'var(--hb-text-3)',
  fontSize: 'var(--mantine-font-size-sm)',
  padding: '8px 0',
} as const

/**
 * Creates a binding, or edits `binding` when one is given. Give it a `key`
 * that changes with the binding, so the fields start from it.
 */
export function BindingFormModal({
  open,
  binding,
  registry,
  keys,
  validators,
  onClose,
  onSubmit,
}: {
  open: boolean
  binding: Binding | null
  registry: RegistryEntry[]
  keys: InternalKey[]
  validators: string[]
  onClose: () => void
  onSubmit: (input: BindingInput) => Promise<unknown>
}) {
  const { t } = useT()
  const [type, setType] = useState(binding?.type ?? 'member')
  const [sourceId, setSourceId] = useState(binding?.source_id ?? '')
  const [attribute, setAttribute] = useState(binding?.source_attribute ?? '')
  const [keyId, setKeyId] = useState(binding ? String(binding.key_id) : '')
  const [validator, setValidator] = useState(binding?.validator ?? 'none')
  const [isProtected, setIsProtected] = useState(binding?.is_protected ?? false)
  const [saving, setSaving] = useState(false)

  const { data: sources = [], isLoading: sourcesLoading } = useQuery({
    queryKey: qk.bindings.sources(type),
    queryFn: () => getSources(type),
    enabled: open,
  })
  const { data: preview } = useQuery<BindingPreview>({
    queryKey: qk.bindings.preview(type, sourceId, attribute),
    queryFn: () => previewBindingValue(type, sourceId, attribute),
    enabled: open && !!sourceId && !!attribute,
  })
  const source: BindingSource | null = sources.find((s) => s.id === sourceId) ?? null

  const attributes = useMemo(() => {
    const attrs = registry.find((r) => r.type === type)?.attributes ?? []
    const aliases = (source?.aliases ?? []).map((a) => ({
      name: `additional_alias:${a.id}`,
      label: t('bindings.additionalAlias', 'Weitere Adresse: {{address}}', { address: a.address }),
    }))
    return [...attrs, ...aliases]
  }, [registry, type, source, t])

  const complete = !!type && !!sourceId && !!attribute && !!keyId
  const submit = async () => {
    if (!complete) return
    setSaving(true)
    try {
      await onSubmit({
        type,
        source_id: sourceId,
        source_attribute: attribute,
        key_id: parseInt(keyId, 10),
        validator,
        is_protected: isProtected,
      })
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={open}
      title={
        binding
          ? t('bindings.editTitle', 'Verknüpfung #{{id}} bearbeiten', { id: binding.id })
          : t('bindings.add', 'Verknüpfung hinzufügen')
      }
      onClose={onClose}
      onSubmit={(e) => {
        e?.preventDefault()
        submit()
      }}
      footer={
        <>
          <Button variant="subtle" onClick={onClose}>
            {t('common.cancel', 'Abbrechen')}
          </Button>
          <Button variant="filled" type="submit" loading={saving} disabled={!complete}>
            {t('common.save', 'Speichern')}
          </Button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <Field label={t('bindings.sourceType', 'Quelltyp')}>
          <Select
            data={registry.map((r) => ({ value: r.type, label: r.type }))}
            value={type}
            onChange={(v) => {
              setType(v ?? '')
              setAttribute('')
              setSourceId('')
            }}
          />
        </Field>
        <Field
          label={t('bindings.source', 'Quelle')}
          hint={t('bindings.sourceHint', 'Wähle einen Quelldatensatz')}
        >
          {sourcesLoading ? (
            <div style={muted}>{t('bindings.loadingSources', 'Quellen werden geladen …')}</div>
          ) : sources.length === 0 ? (
            <div style={muted}>
              {t('bindings.noSources', 'Keine Einträge vom Typ {{type}}.', { type })}
            </div>
          ) : (
            <Select
              data={[
                { value: '', label: t('bindings.selectSource', 'Eintrag wählen …') },
                ...sources.map((s) => ({ value: s.id, label: s.label })),
              ]}
              value={sourceId}
              onChange={(v) => setSourceId(v ?? '')}
              searchable
            />
          )}
        </Field>
        {source && (
          <div
            style={{
              ...box,
              padding: '12px 14px',
              display: 'grid',
              gridTemplateColumns: 'auto 1fr',
              gap: '4px 16px',
              fontSize: 'var(--mantine-font-size-xs)',
            }}
          >
            {Object.entries(source.preview)
              .filter(([k]) => !/password|secret|token|credential/i.test(k))
              .map(([k, v]) => (
                <div key={k} style={{ display: 'contents' }}>
                  <span style={{ color: 'var(--hb-text-2)', fontWeight: 500 }}>{k}</span>
                  <span style={{ color: 'var(--hb-text)' }}>
                    {v === null || v === undefined ? '—' : String(v)}
                  </span>
                </div>
              ))}
          </div>
        )}
        <Field label={t('bindings.attribute', 'Attribut')}>
          <Select
            data={[
              { value: '', label: t('bindings.selectAttribute', 'Attribut wählen …') },
              ...attributes.map((a) => ({ value: a.name, label: `${a.label} (${a.name})` })),
            ]}
            value={attribute}
            onChange={(v) => setAttribute(v ?? '')}
            searchable
          />
        </Field>
        {sourceId && attribute && (
          <div style={{ ...box, padding: '10px 14px', fontSize: 'var(--mantine-font-size-sm)' }}>
            <span style={{ color: 'var(--hb-text-2)', fontWeight: 500 }}>
              {t('bindings.currentValue', 'Aktueller Wert:')}{' '}
            </span>
            {preview?.masked ? (
              <span style={{ color: '#bbb', fontStyle: 'italic' }}>
                {'••••• '}
                {t('bindings.hidden', '(verborgen)')}
              </span>
            ) : preview?.value ? (
              <span style={{ color: 'var(--hb-text)' }}>{preview.value}</span>
            ) : (
              <em style={{ color: '#bbb' }}>
                {'— '}
                {t('bindings.empty', '(leer)')}
              </em>
            )}
          </div>
        )}
        <Field label={t('bindings.targetKey', 'Zielschlüssel')}>
          <Select
            data={[
              { value: '', label: t('bindings.selectKey', 'Schlüssel wählen …') },
              ...keys.map((k) => ({
                value: String(k.id),
                label: `${k.key}${k.label ? ` — ${k.label}` : ''}`,
              })),
            ]}
            value={keyId}
            onChange={(v) => setKeyId(v ?? '')}
            searchable
          />
        </Field>
        <Field label={t('bindings.validator', 'Prüfung')}>
          <Select
            data={validators.map((v) => ({ value: v, label: v }))}
            value={validator}
            onChange={(v) => setValidator(v ?? '')}
          />
        </Field>
        {binding && (
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
              checked={isProtected}
              onChange={(e) => setIsProtected(e.target.checked)}
              style={{ width: 16, height: 16, accentColor: 'var(--mantine-color-acc-6)' }}
            />
            <span style={{ fontWeight: 600 }}>{t('bindings.protected', 'Geschützt')}</span>
            <span style={{ color: 'var(--hb-text-2)', fontSize: 'var(--mantine-font-size-xs)' }}>
              {t('bindings.protectedHint', 'Kann nicht gelöscht oder ausgeschaltet werden')}
            </span>
          </label>
        )}
      </div>
    </Modal>
  )
}
