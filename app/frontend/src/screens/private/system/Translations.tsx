import { useState, useEffect, useMemo, useRef } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useT } from '@/locales/i18n'
import {
  IconPlus,
  IconCopy,
  IconTrash,
  IconCheck,
  IconPencil,
  IconGlobe,
  IconChevronDown,
  IconDownload,
  IconUpload,
  IconAlertCircle,
  IconArrowBackUp,
  IconLink,
  IconUnlink,
} from '@tabler/icons-react'
import { TextInput, Select, Button } from '@mantine/core'
import { useToast, useAuth } from '@/context/AppContext'
import {
  PageHead,
  KVTable,
  Modal,
  Field,
  ConfirmModal,
  LoadingSpinner,
} from '@/components/ui'
import {
  fetchTranslationsList,
  fetchLanguages,
  patchTranslations,
  deleteTranslation,
  duplicateLocale,
  copyDefaults as copyDefaultsApi,
  exportTranslations,
  importTranslations,
  type TranslationEntry,
} from '@/api/i18n'
import { qk } from '@/data/keys'

type FilterMode = 'all' | 'flagged' | 'missing'

const LANGUAGE_LABELS: Record<string, string> = {
  'de-CH': 'Deutsch (CH)',
  'en-GB': 'English',
}

const dropdownItemStyle: React.CSSProperties = {
  display: 'block',
  width: '100%',
  padding: '8px 14px',
  border: 'none',
  background: 'transparent',
  cursor: 'pointer',
  fontSize: 'var(--mantine-font-size-sm)',
  color: '#1a1625',
  textAlign: 'left',
}

function localeLabel(code: string): string {
  return LANGUAGE_LABELS[code] ?? code
}

function formatRelative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const sec = Math.floor(diff / 1000)
  if (sec < 60) return 'just now'
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min}m ago`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr}h ago`
  const day = Math.floor(hr / 24)
  if (day < 30) return `${day}d ago`
  const mo = Math.floor(day / 30)
  if (mo < 12) return `${mo}mo ago`
  const yr = Math.floor(mo / 12)
  return `${yr}y ago`
}

export function TranslationsScreen() {
  const { t } = useT()
  const { notify } = useToast()
  const { hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const canWrite = hasPermission('i18n.i18n.write')
  const [activeLocale, setActiveLocale] = useState('')
  const [search, setSearch] = useState('')
  const [editingKey, setEditingKey] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')
  const [saving, setSaving] = useState(false)
  const [showAddModal, setShowAddModal] = useState(false)
  const [showDupModal, setShowDupModal] = useState(false)
  const [localeMenuOpen, setLocaleMenuOpen] = useState(false)
  const localeMenuRef = useRef<HTMLDivElement>(null)
  const [filterMode, setFilterMode] = useState<FilterMode>('all')
  const [showExportMenu, setShowExportMenu] = useState(false)
  const [showImportMenu, setShowImportMenu] = useState(false)
  const exportMenuRef = useRef<HTMLDivElement>(null)
  const importMenuRef = useRef<HTMLDivElement>(null)
  const importInputRef = useRef<HTMLInputElement>(null)
  const [aliasTarget, setAliasTarget] = useState<TranslationEntry | null>(null)
  const [aliasValue, setAliasValue] = useState('')
  const [deleteTarget, setDeleteTarget] = useState<{
    key: string
    aliasCount: number
  } | null>(null)

  const languagesQuery = useQuery({
    queryKey: qk.languages,
    queryFn: () => fetchLanguages(),
  })
  const languages = useMemo(() => {
    if (languagesQuery.data && languagesQuery.data.length > 0)
      return languagesQuery.data
    if (languagesQuery.isError) return ['de-CH', 'en-GB']
    return []
  }, [languagesQuery.data, languagesQuery.isError])

  const translationsQuery = useQuery({
    queryKey: qk.translations(activeLocale),
    queryFn: () => fetchTranslationsList(activeLocale),
    enabled: !!activeLocale,
  })
  const entries = useMemo(
    () => translationsQuery.data ?? [],
    [translationsQuery.data],
  )
  const loading = translationsQuery.isLoading || translationsQuery.isFetching

  useEffect(() => {
    if (!activeLocale && languages.length > 0) {
      queueMicrotask(() => setActiveLocale(languages[0]))
    }
  }, [languages, activeLocale])

  useEffect(() => {
    if (activeLocale) {
      queueMicrotask(() => {
        setEditingKey(null)
        setEditValue('')
      })
    }
  }, [activeLocale])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (
        localeMenuRef.current &&
        !localeMenuRef.current.contains(e.target as Node)
      ) {
        setLocaleMenuOpen(false)
      }
      if (
        exportMenuRef.current &&
        !exportMenuRef.current.contains(e.target as Node)
      ) {
        setShowExportMenu(false)
      }
      if (
        importMenuRef.current &&
        !importMenuRef.current.contains(e.target as Node)
      ) {
        setShowImportMenu(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const flaggedCount = useMemo(
    () => entries.filter((e) => e.needs_attention).length,
    [entries],
  )
  const missingCount = useMemo(
    () => entries.filter((e) => e.is_missing).length,
    [entries],
  )

  const filtered = useMemo(() => {
    let result = entries
    if (filterMode === 'flagged') {
      result = result.filter((e) => e.needs_attention)
    } else if (filterMode === 'missing') {
      result = result.filter((e) => e.is_missing)
    }
    if (search.trim()) {
      const q = search.toLowerCase()
      result = result.filter(
        (e) =>
          e.key.toLowerCase().includes(q) ||
          e.value.toLowerCase().includes(q) ||
          (e.default_value ?? '').toLowerCase().includes(q),
      )
    }
    return result
  }, [entries, search, filterMode])

  const startEdit = (entry: TranslationEntry) => {
    setEditingKey(entry.key)
    setEditValue(entry.value)
  }

  const cancelEdit = () => {
    setEditingKey(null)
    setEditValue('')
  }

  const saveEdit = async (key: string) => {
    setSaving(true)
    try {
      await patchTranslations(activeLocale, [{ key, value: editValue }])
      queryClient.invalidateQueries({
        queryKey: qk.translations(activeLocale),
      })
      setEditingKey(null)
      setEditValue('')
      notify('success', t('translations.saved'), key)
    } catch {
      notify('error', t('translations.saveFailed'))
    }
    setSaving(false)
  }

  const handleDeleteClick = (entry: TranslationEntry) => {
    const aliasCount = entries.filter((e) => e.alias_for === entry.key).length
    setDeleteTarget({ key: entry.key, aliasCount })
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    try {
      const result = await deleteTranslation(activeLocale, deleteTarget.key)
      const keysToRemove = new Set([deleteTarget.key])
      if (result.count > 1) {
        entries.forEach((e) => {
          if (e.alias_for === deleteTarget.key) keysToRemove.add(e.key)
        })
      }
      queryClient.invalidateQueries({
        queryKey: qk.translations(activeLocale),
      })
      notify(
        'success',
        t('translations.deleted'),
        result.count > 1
          ? `${deleteTarget.key} + ${result.count - 1} alias(es)`
          : deleteTarget.key,
      )
    } catch {
      notify('error', t('translations.deleteFailed'))
    }
    setDeleteTarget(null)
  }

  const handleSetAlias = async () => {
    if (!aliasTarget || !aliasValue.trim()) return
    try {
      await patchTranslations(activeLocale, [
        { key: aliasTarget.key, value: '', alias_for: aliasValue.trim() },
      ])
      queryClient.invalidateQueries({
        queryKey: qk.translations(activeLocale),
      })
      notify('success', t('translations.alias.linked'), aliasTarget.key)
    } catch {
      notify('error', t('translations.alias.failed'))
    }
    setAliasTarget(null)
    setAliasValue('')
  }

  const handleRemoveAlias = async (entry: TranslationEntry) => {
    try {
      await patchTranslations(activeLocale, [
        { key: entry.key, value: '', alias_for: null },
      ])
      queryClient.invalidateQueries({
        queryKey: qk.translations(activeLocale),
      })
      notify('success', t('translations.alias.removed'), entry.key)
    } catch {
      notify('error', t('translations.alias.failed'))
    }
  }

  const handleAdd = async (key: string, value: string) => {
    try {
      await patchTranslations(activeLocale, [{ key, value }])
      setShowAddModal(false)
      queryClient.invalidateQueries({
        queryKey: qk.translations(activeLocale),
      })
      notify('success', t('translations.added'), key)
    } catch {
      notify('error', t('translations.addFailed'))
    }
  }

  const handleDuplicate = async (
    targetLocale: string,
    source: string,
    copyValues: boolean,
  ) => {
    try {
      const result = await duplicateLocale(targetLocale, source, copyValues)
      setShowDupModal(false)
      notify('success', t('translations.duplicated'), String(result.inserted))
      if (targetLocale === activeLocale) {
        queryClient.invalidateQueries({
          queryKey: qk.translations(activeLocale),
        })
      }
      queryClient.invalidateQueries({ queryKey: qk.languages })
    } catch {
      notify('error', t('translations.duplicateFailed'))
    }
  }

  const handleExport = async (format: 'json' | 'csv') => {
    setShowExportMenu(false)
    try {
      await exportTranslations(activeLocale, format)
      notify('success', t('translations.exported'), `${activeLocale}.${format}`)
    } catch {
      notify('error', t('translations.exportFailed'))
    }
  }

  const handleCopyDefaults = async () => {
    try {
      const result = await copyDefaultsApi(activeLocale)
      queryClient.invalidateQueries({
        queryKey: qk.translations(activeLocale),
      })
      notify(
        'success',
        t('translations.copyDefaults.done', 'Standardwerte übernommen'),
        `${result.filled} ${t('translations.entries')}`,
      )
    } catch {
      notify('error', t('translations.copyDefaults.failed', 'Übernehmen fehlgeschlagen'))
    }
  }

  const handleImportFile = async (file: File, format: 'json' | 'csv') => {
    setShowImportMenu(false)
    try {
      const result = await importTranslations(activeLocale, file, format)
      queryClient.invalidateQueries({
        queryKey: qk.translations(activeLocale),
      })
      notify(
        'success',
        t('translations.imported'),
        `${result.imported} ${t('translations.entries')}`,
      )
    } catch {
      notify('error', t('translations.importFailed'))
    }
  }

  const onImportFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const ext = file.name.split('.').pop()?.toLowerCase()
    const format: 'json' | 'csv' = ext === 'csv' ? 'csv' : 'json'
    handleImportFile(file, format).finally(() => {
      if (importInputRef.current) importInputRef.current.value = ''
    })
  }

  return (
    <div>
      <PageHead
        title={t('translations.title')}
        desc={t('translations.description')}
        actions={
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {/* Export */}
            <div ref={exportMenuRef} style={{ position: 'relative' }}>
              <Button
                variant="default"
                onClick={() => setShowExportMenu(!showExportMenu)}
              >
                <IconDownload size={16} />
                {t('common.export')}
              </Button>
              {showExportMenu && (
                <div
                  style={{
                    position: 'absolute',
                    top: '100%',
                    right: 0,
                    marginTop: 4,
                    background: '#fff',
                    border: '1px solid #e6e3ef',
                    borderRadius: 8,
                    boxShadow: '0 4px 12px rgba(0,0,0,.08)',
                    zIndex: 100,
                    minWidth: 140,
                    overflow: 'hidden',
                  }}
                >
                  <button
                    style={dropdownItemStyle}
                    onClick={() => handleExport('json')}
                  >
                    {t('translations.format.json')}
                  </button>
                  <button
                    style={dropdownItemStyle}
                    onClick={() => handleExport('csv')}
                  >
                    {t('translations.format.csv')}
                  </button>
                </div>
              )}
            </div>

            {/* Import */}
            <div ref={importMenuRef} style={{ position: 'relative' }}>
              <Button
                variant="default"
                onClick={() => setShowImportMenu(!showImportMenu)}
              >
                <IconUpload size={16} />
                {t('common.import')}
              </Button>
              {showImportMenu && (
                <div
                  style={{
                    position: 'absolute',
                    top: '100%',
                    right: 0,
                    marginTop: 4,
                    background: '#fff',
                    border: '1px solid #e6e3ef',
                    borderRadius: 8,
                    boxShadow: '0 4px 12px rgba(0,0,0,.08)',
                    zIndex: 100,
                    minWidth: 140,
                    overflow: 'hidden',
                  }}
                >
                  <button
                    style={dropdownItemStyle}
                    onClick={() => {
                      setShowImportMenu(false)
                      importInputRef.current?.click()
                    }}
                  >
                    {t('translations.format.json')}
                  </button>
                  <button
                    style={dropdownItemStyle}
                    onClick={() => {
                      setShowImportMenu(false)
                      importInputRef.current?.click()
                    }}
                  >
                    {t('translations.format.csv')}
                  </button>
                </div>
              )}
            </div>

            {/* Hidden file input */}
            <input
              ref={importInputRef}
              type="file"
              accept=".json,.csv"
              style={{ display: 'none' }}
              onChange={onImportFileChange}
            />

            {canWrite && (
              <Button variant="default" onClick={() => setShowDupModal(true)}>
                <IconCopy size={16} />
                {t('translations.addLanguageLabel')}
              </Button>
            )}
            {canWrite && (
              <Button
                variant="default"
                onClick={handleCopyDefaults}
                title={t(
                  'translations.copyDefaults.hint',
                  'Leere Werte mit den Standardwerten füllen',
                )}
              >
                <IconArrowBackUp size={16} />
                {t('translations.copyDefaultsLabel', 'Standardwerte übernehmen')}
              </Button>
            )}
            {canWrite && (
              <Button variant="filled" onClick={() => setShowAddModal(true)}>
                <IconPlus size={16} />
                {t('translations.addKeyLabel')}
              </Button>
            )}
          </div>
        }
      />

      {/* Locale selector */}
      {languagesQuery.isLoading ? (
        <LoadingSpinner
          compact
          message={t(
            'translations.loadingLanguages',
            'Sprachen werden geladen …',
          )}
        />
      ) : (
        <div
          ref={localeMenuRef}
          style={{ position: 'relative', marginBottom: 16 }}
        >
          <Button
            variant="default"
            style={{ minWidth: 180, justifyContent: 'space-between' }}
            onClick={() => setLocaleMenuOpen(!localeMenuOpen)}
          >
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <IconGlobe size={16} />
              {localeLabel(activeLocale)}
            </span>
            <IconChevronDown size={16} />
          </Button>
          {localeMenuOpen && (
            <div
              style={{
                position: 'absolute',
                top: '100%',
                left: 0,
                marginTop: 4,
                background: '#fff',
                border: '1px solid #e6e3ef',
                borderRadius: 8,
                boxShadow: '0 4px 12px rgba(0,0,0,.08)',
                zIndex: 100,
                minWidth: 180,
                overflow: 'hidden',
              }}
            >
              {languages.map((lang) => (
                <button
                  key={lang}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    width: '100%',
                    padding: '8px 14px',
                    border: 'none',
                    background: 'transparent',
                    cursor: 'pointer',
                    fontSize: 'var(--mantine-font-size-sm)',
                    color: '#1a1625',
                  }}
                  onClick={() => {
                    setActiveLocale(lang)
                    setLocaleMenuOpen(false)
                  }}
                >
                  {localeLabel(lang)}
                  {lang === activeLocale && <IconCheck size={14} />}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {activeLocale && loading && entries.length === 0 ? (
        <LoadingSpinner
          compact
          message={t('translations.loading', 'Übersetzungen werden geladen …')}
        />
      ) : (
        <KVTable<TranslationEntry>
          entries={filtered}
          loading={loading}
          getNamespace={(e) => e.key.split('.')[0] || 'other'}
          search={search}
          onSearchChange={setSearch}
          searchPlaceholder={t('translations.searchPlaceholder')}
          extraFilters={
            <>
              <button
                className={`chip${filterMode === 'all' ? ' on' : ''}`}
                onClick={() => setFilterMode('all')}
              >
                {t('translations.flagged.showAll')}
              </button>
              <button
                className={`chip${filterMode === 'flagged' ? ' on' : ''}`}
                onClick={() => setFilterMode('flagged')}
              >
                <IconAlertCircle size={16} />
                {t('translations.flagged.showFlagged')}
                {flaggedCount > 0 && (
                  <span
                    style={{
                      background: '#ff6b5e',
                      color: '#fff',
                      borderRadius: 10,
                      padding: '0 6px',
                      fontSize: 'var(--mantine-font-size-xs)',
                      fontWeight: 600,
                    }}
                  >
                    {flaggedCount}
                  </span>
                )}
              </button>
              <button
                className={`chip${filterMode === 'missing' ? ' on' : ''}`}
                onClick={() => setFilterMode('missing')}
              >
                {t('translations.flagged.missing')}
                {missingCount > 0 && (
                  <span
                    style={{
                      background: '#f0a020',
                      color: '#fff',
                      borderRadius: 10,
                      padding: '0 6px',
                      fontSize: 'var(--mantine-font-size-xs)',
                      fontWeight: 600,
                    }}
                  >
                    {missingCount}
                  </span>
                )}
              </button>
              <span
                style={{
                  fontSize: 'var(--mantine-font-size-xs)',
                  color: '#5e5873',
                  whiteSpace: 'nowrap',
                  marginLeft: 4,
                }}
              >
                {filtered.length} / {entries.length} {t('translations.keys')}
              </span>
            </>
          }
          editingKey={editingKey}
          editValue={editValue}
          onEditValueChange={setEditValue}
          onEditStart={startEdit}
          onEditSave={(entry) => saveEdit(entry.key)}
          onEditCancel={cancelEdit}
          saving={saving}
          renderKeyPrefix={(entry) =>
            entry.alias_for ? (
              <IconLink size={11} style={{ color: '#6131c4' }} />
            ) : null
          }
          renderKeyBelow={(entry) => (
            <span
              style={{
                fontSize: 'var(--mantine-font-size-xs)',
                color: entry.is_stale ? '#bbb' : '#8c86a0',
                fontStyle: entry.is_stale ? 'italic' : 'normal',
                whiteSpace: 'nowrap',
              }}
              title={
                entry.last_used_at
                  ? new Date(entry.last_used_at).toLocaleString()
                  : undefined
              }
            >
              {entry.last_used_at
                ? formatRelative(entry.last_used_at)
                : '\u2014'}
            </span>
          )}
          renderKeySuffix={(entry) => (
            <>
              {entry.alias_for && (
                <span
                  style={{
                    marginLeft: 6,
                    fontSize: 'var(--mantine-font-size-xs)',
                    fontWeight: 500,
                    color: '#6131c4',
                    background: '#fef9ef',
                    borderRadius: 4,
                    padding: '1px 4px',
                  }}
                  title={
                    t('translations.alias.target') + ': ' + entry.alias_for
                  }
                >
                  {'\u2192'} {entry.alias_for}
                </span>
              )}
              {entry.is_missing && (
                <span
                  style={{
                    marginLeft: 6,
                    fontSize: 'var(--mantine-font-size-xs)',
                    fontWeight: 600,
                    color: '#f0a020',
                    background: '#fef5e7',
                    borderRadius: 4,
                    padding: '1px 4px',
                  }}
                >
                  {t('translations.flagged.missing')}
                </span>
              )}
              {!entry.is_missing &&
                entry.needs_attention &&
                !entry.alias_for && (
                  <span
                    style={{
                      marginLeft: 6,
                      fontSize: 'var(--mantine-font-size-xs)',
                      fontWeight: 600,
                      color: '#ff6b5e',
                      background: '#fef0ef',
                      borderRadius: 4,
                      padding: '1px 4px',
                    }}
                  >
                    {t('translations.flagged.empty')}
                  </span>
                )}
            </>
          )}
          renderValue={(entry) =>
            entry.alias_for ? (
              <span
                style={{
                  fontSize: 'var(--mantine-font-size-sm)',
                  color: '#8c86a0',
                  fontStyle: 'italic',
                }}
              >
                {t('translations.alias.resolved')}: {entry.alias_for}
              </span>
            ) : (
              <span
                style={{
                  fontSize: 'var(--mantine-font-size-sm)',
                  color: entry.value ? '#2e2940' : '#bbb',
                }}
              >
                {entry.value || (
                  <em style={{ color: '#bbb' }}>{t('translations.empty')}</em>
                )}
              </span>
            )
          }
          isValueClickable={(entry) => !entry.alias_for}
          extraColumns={[
            {
              key: 'default',
              header: t('translations.default', 'Standard'),
              width: 200,
              render: (entry) => (
                <span
                  style={{
                    fontSize: 'var(--mantine-font-size-xs)',
                    color: '#8c86a0',
                    display: 'block',
                    maxWidth: 200,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {entry.default_value || (
                    <span style={{ color: '#ccc' }}>{'\u2014'}</span>
                  )}
                </span>
              ),
            },
          ]}
          renderActions={(entry) => (
            <>
              {!entry.alias_for && canWrite && (
                <Button
                  size="sm"
                  variant="subtle"
                  onClick={() => startEdit(entry)}
                  title={t('translations.editValue')}
                >
                  <IconPencil size={16} />
                </Button>
              )}
              {canWrite && (
                <Button
                  size="sm"
                  variant="subtle"
                  style={{ color: '#6131c4' }}
                  onClick={() => {
                    if (entry.alias_for) {
                      handleRemoveAlias(entry)
                    } else {
                      setAliasTarget(entry)
                      setAliasValue('')
                    }
                  }}
                  title={
                    entry.alias_for
                      ? t('translations.alias.unlink')
                      : t('translations.alias.link')
                  }
                >
                  {entry.alias_for ? (
                    <IconUnlink size={16} />
                  ) : (
                    <IconLink size={16} />
                  )}
                </Button>
              )}
              {canWrite && (
                <Button
                  size="sm"
                  variant="subtle"
                  style={{ color: '#ff4d3d' }}
                  onClick={() => handleDeleteClick(entry)}
                  title={t('translations.delete')}
                >
                  <IconTrash size={16} />
                </Button>
              )}
            </>
          )}
          emptyMessage={t('translations.noResults')}
          loadingMessage={t('translations.loading')}
        />
      )}

      <AddKeyModal
        key={showAddModal ? 'add-open' : 'add-closed'}
        open={showAddModal}
        onClose={() => setShowAddModal(false)}
        onAdd={handleAdd}
      />
      <DuplicateLocaleModal
        key={showDupModal ? 'dup-open' : 'dup-closed'}
        open={showDupModal}
        onClose={() => setShowDupModal(false)}
        onDuplicate={handleDuplicate}
        existingLocales={languages}
      />

      <Modal
        open={!!aliasTarget}
        onClose={() => {
          setAliasTarget(null)
          setAliasValue('')
        }}
        title={t('translations.alias.link')}
        subtitle={aliasTarget?.key}
        footer={
          <>
            <Button
              variant="default"
              onClick={() => {
                setAliasTarget(null)
                setAliasValue('')
              }}
            >
              {t('common.cancel')}
            </Button>
            <Button
              variant="filled"
              onClick={handleSetAlias}
              disabled={!aliasValue.trim()}
            >
              {t('translations.alias.link')}
            </Button>
          </>
        }
      >
        <Field
          label={t('translations.alias.target')}
          hint={t('translations.alias.targetHint')}
        >
          <TextInput
            value={aliasValue}
            onChange={(e) => setAliasValue(e.target.value)}
            placeholder="e.g. common.save"
            autoFocus
            onKeyDown={(e) => {
              if (e.key === 'Enter' && aliasValue.trim()) handleSetAlias()
            }}
          />
        </Field>
      </Modal>

      <ConfirmModal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title={t('translations.delete')}
        body={
          deleteTarget?.aliasCount
            ? t(
                'translations.deleteCascade.warning',
                '{{count}} Verknüpfungen werden ebenfalls gelöscht.',
                { count: deleteTarget.aliasCount },
              )
            : t('translations.deleteConfirm', 'Diese Übersetzung löschen?')
        }
        onConfirm={confirmDelete}
      />
    </div>
  )
}

function AddKeyModal({
  open,
  onClose,
  onAdd,
}: {
  open: boolean
  onClose: () => void
  onAdd: (key: string, value: string) => void
}) {
  const { t } = useT()
  const [key, setKey] = useState('')
  const [value, setValue] = useState('')

  const handleSubmit = () => {
    if (!key.trim()) return
    onAdd(key.trim(), value)
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t('translations.addKeyLabel')}
      subtitle={t('translations.addKey.desc')}
      footer={
        <>
          <Button variant="subtle" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button
            variant="filled"
            onClick={handleSubmit}
            disabled={!key.trim()}
          >
            {t('common.add')}
          </Button>
        </>
      }
    >
      <Field label={t('translations.key')}>
        <TextInput
          placeholder="section.descriptive.name"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
          style={{
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: 'var(--mantine-font-size-sm)',
          }}
        />
      </Field>
      <Field label={t('translations.value')}>
        <TextInput
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
        />
      </Field>
    </Modal>
  )
}

function DuplicateLocaleModal({
  open,
  onClose,
  onDuplicate,
  existingLocales,
}: {
  open: boolean
  onClose: () => void
  onDuplicate: (
    targetLocale: string,
    source: string,
    copyValues: boolean,
  ) => void
  existingLocales: string[]
}) {
  const { t } = useT()
  const [targetLocale, setTargetLocale] = useState('')
  const [source, setSource] = useState(existingLocales[0] ?? '')
  const [copyValues, setCopyValues] = useState(false)

  const targetExists = existingLocales.includes(targetLocale.trim())
  const canSubmit = targetLocale.trim().length > 0 && source && !targetExists

  const handleSubmit = () => {
    if (!canSubmit) return
    onDuplicate(targetLocale.trim(), source, copyValues)
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t('translations.addLanguageLabel')}
      subtitle={t('translations.addLanguage.desc')}
      footer={
        <>
          <Button variant="subtle" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button variant="filled" onClick={handleSubmit} disabled={!canSubmit}>
            {t('translations.createLanguage')}
          </Button>
        </>
      }
    >
      <Field label={t('translations.targetLocale')}>
        <TextInput
          placeholder="fr-CH"
          value={targetLocale}
          onChange={(e) => setTargetLocale(e.target.value)}
          style={{
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: 'var(--mantine-font-size-sm)',
          }}
        />
        {targetExists && (
          <div
            style={{
              fontSize: 'var(--mantine-font-size-xs)',
              color: '#ff4d3d',
              marginTop: 4,
            }}
          >
            {t('translations.localeExists')}
          </div>
        )}
      </Field>
      <Field label={t('translations.sourceLocale')}>
        <Select
          data={existingLocales.map((lang) => ({
            value: lang,
            label: `${localeLabel(lang)} (${lang})`,
          }))}
          value={source}
          onChange={(v) => v && setSource(v)}
          style={{ fontSize: 'var(--mantine-font-size-sm)' }}
        />
      </Field>
      <label
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          cursor: 'pointer',
          fontSize: 'var(--mantine-font-size-sm)',
          color: '#1a1625',
        }}
      >
        <input
          type="checkbox"
          checked={copyValues}
          onChange={(e) => setCopyValues(e.target.checked)}
        />
        {t('translations.copyValuesLabel')}
      </label>
      <p
        style={{
          fontSize: 'var(--mantine-font-size-xs)',
          color: '#5e5873',
          margin: '8px 0 0',
        }}
      >
        {copyValues
          ? t('translations.copyValues.on')
          : t('translations.copyValues.off')}
      </p>
    </Modal>
  )
}
