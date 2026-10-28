import { useState, useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useT } from '@/locales/i18n'
import { TextInput, Button } from '@mantine/core'
import { Modal, Field, Toggle, ConfirmModal } from '@/components/ui'
import { useToast } from '@/context/AppContext'
import type { ManagedMailAddressInfo } from '@/api/mail'
import {
  toggleMemberMail,
  updateMailMember,
  deleteMemberMail,
  toggleGroupMail,
  deleteGroupMail,
  changeGroupMailPrefix,
  listGroupAliases,
  createGroupAlias,
  deleteGroupAlias,
  toggleGroupAlias,
  toggleFunctionMail,
  deleteFunctionMail,
  changeFunctionMailPrefix,
  listFunctionAliases,
  createFunctionAlias,
  deleteFunctionAlias,
  toggleFunctionAlias,
  toggleSystemAddress,
  deleteSystemAddress,
  resetSystemAddressPassword,
  updateSystemForwarding,
  resolveLocalPart,
  getFromWhitelist,
  updateFromWhitelist,
} from '@/api/mail'

type Category = 'member' | 'group' | 'function' | 'system'

export function MailSettingsModal({
  entry,
  category,
  open,
  onClose,
  onSaved,
  canManage,
}: {
  entry: ManagedMailAddressInfo | null
  category: Category
  open: boolean
  onClose: () => void
  onSaved: () => void
  canManage: boolean
}) {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()

  const [forwarding, setForwarding] = useState(
    entry?.forwardingEnabled ?? false,
  )
  const [enabled, setEnabled] = useState(entry?.isEnabled ?? true)
  const [retention, setRetention] = useState(
    entry?.retention != null ? Math.round(entry.retention / 86400000) : null,
  )
  const [quotaMb, setQuotaMb] = useState(
    entry?.quotaBytes ? Math.round(entry.quotaBytes / 1048576) : 1024,
  )
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [busy, setBusy] = useState(false)

  const [prefix, setPrefix] = useState(entry?.mailPrefix ?? '')
  const [prefixPreview, setPrefixPreview] = useState<string | null>(null)
  const prefixChanged = prefix !== (entry?.mailPrefix ?? '')

  const [newAliasPrefix, setNewAliasPrefix] = useState('')
  const [aliasBusy, setAliasBusy] = useState(false)
  const [customPassword, setCustomPassword] = useState('')

  const [forwardTargets, setForwardTargets] = useState<string[]>(
    entry?.fixedForwardTargets ?? [],
  )
  const forwardTargetsChanged =
    JSON.stringify(forwardTargets) !==
    JSON.stringify(entry?.fixedForwardTargets ?? [])

  const [wlEntries, setWlEntries] = useState<string[]>(
    entry?.fromWhitelist ?? [],
  )
  const [wlEffective, setWlEffective] = useState<string[]>([])
  const wlChanged =
    JSON.stringify(wlEntries) !== JSON.stringify(entry?.fromWhitelist ?? [])

  const showFromWhitelist = entry?.addressType === 'mailbox'

  const { data: wlData } = useQuery({
    queryKey: ['from-whitelist', entry?.id],
    queryFn: () => getFromWhitelist(entry!.id!),
    enabled: open && showFromWhitelist && entry?.id != null,
  })

  const [prevWlData, setPrevWlData] = useState(wlData)
  if (wlData !== prevWlData) {
    setPrevWlData(wlData)
    if (wlData) {
      setWlEntries(wlData.curated)
      setWlEffective(wlData.effective)
    }
  }

  const linkedId =
    category === 'group'
      ? entry?.ownerId
      : category === 'function'
        ? entry?.ownerId
        : null

  const { data: aliases = [] } = useQuery<ManagedMailAddressInfo[]>({
    queryKey: ['mail-aliases', category, linkedId],
    queryFn: () => {
      if (category === 'group' && entry?.ownerId != null) {
        return listGroupAliases(entry.ownerId)
      }
      if (category === 'function' && entry?.ownerId != null) {
        return listFunctionAliases(entry.ownerId)
      }
      return []
    },
    enabled:
      open &&
      (category === 'group' || category === 'function') &&
      linkedId != null,
  })

  const invalidateAliases = () =>
    queryClient.invalidateQueries({
      queryKey: ['mail-aliases', category, linkedId],
    })

  useEffect(() => {
    if (!canManage || !prefixChanged || !prefix.trim()) return
    const timer = setTimeout(() => {
      resolveLocalPart(prefix.trim())
        .then((local) => {
          const domain = entry?.domain || ''
          setPrefixPreview(domain ? `${local}@${domain}` : local)
        })
        .catch(() => setPrefixPreview(null))
    }, 300)
    return () => clearTimeout(timer)
  }, [canManage, prefixChanged, prefix, entry?.domain])

  if (!entry) return null

  const handleSave = async () => {
    setBusy(true)
    try {
      if (category === 'member') {
        if (entry.ownerId != null) {
          await updateMailMember(String(entry.ownerId), {
            forwardingEnabled: forwarding,
            retentionDays: retention,
            quotaMb,
          })
          if (enabled !== entry.isEnabled) {
            await toggleMemberMail(entry.ownerId, enabled)
          }
        }
      } else if (category === 'group') {
        if (entry.ownerId != null) {
          if (enabled !== entry.isEnabled) {
            await toggleGroupMail(entry.ownerId, enabled)
          }
          if (prefixChanged && prefix.trim()) {
            await changeGroupMailPrefix(entry.ownerId, prefix.trim())
          }
        }
      } else if (category === 'function') {
        if (entry.ownerId != null) {
          if (enabled !== entry.isEnabled) {
            await toggleFunctionMail(entry.ownerId, enabled)
          }
          if (prefixChanged && prefix.trim()) {
            await changeFunctionMailPrefix(entry.ownerId, prefix.trim())
          }
        }
      } else if (category === 'system') {
        if (entry.id) {
          if (enabled !== entry.isEnabled) {
            await toggleSystemAddress(entry.id, enabled)
          }
          if (forwardTargetsChanged) {
            const cleaned = forwardTargets.map((s) => s.trim()).filter(Boolean)
            await updateSystemForwarding(entry.id, cleaned)
          }
        }
      }
      if (showFromWhitelist && entry.id && wlChanged) {
        const cleaned = wlEntries.map((s) => s.trim()).filter(Boolean)
        await updateFromWhitelist(entry.id, cleaned)
      }
      notify(
        'success',
        t('common.saved', 'Gespeichert'),
        t('mail.admin.settingsSaved', 'Mail-Einstellungen gespeichert.'),
      )
      onSaved()
      onClose()
    } catch {
      notify(
        'error',
        t('common.updateFailed', 'Speichern fehlgeschlagen'),
        t(
          'mail.admin.couldNotSave',
          'Mail-Einstellungen konnten nicht gespeichert werden.',
        ),
      )
    } finally {
      setBusy(false)
    }
  }

  const handleDelete = async () => {
    setBusy(true)
    try {
      if (category === 'member' && entry.ownerId != null) {
        await deleteMemberMail(entry.ownerId)
      } else if (category === 'group' && entry.ownerId != null) {
        await deleteGroupMail(entry.ownerId)
      } else if (category === 'function' && entry.ownerId != null) {
        await deleteFunctionMail(entry.ownerId)
      } else if (category === 'system' && entry.id) {
        await deleteSystemAddress(entry.id)
      }
      notify(
        'info',
        t('mail.admin.deleted', 'Mail-Adresse entfernt'),
        t('mail.admin.deletedMsg', '{{address}} wurde entfernt.', {
          address: entry.address,
        }),
      )
      onSaved()
      onClose()
    } catch {
      notify(
        'error',
        t('common.deleteFailed', 'Löschen fehlgeschlagen'),
        t('mail.admin.couldNotDelete', 'Mail-Adresse konnte nicht gelöscht werden.'),
      )
    } finally {
      setBusy(false)
      setDeleteOpen(false)
    }
  }

  const handleResetPassword = async () => {
    if (category !== 'system' || !entry.id) return
    setBusy(true)
    try {
      const pwd = await resetSystemAddressPassword(
        entry.id,
        customPassword.trim() || undefined,
      )
      notify(
        'success',
        t('mail.system.password.set', 'Passwort festlegen'),
        t('mail.system.password.generated', 'Neues Passwort: {{pwd}}', { pwd }),
      )
      setCustomPassword('')
    } catch {
      notify(
        'error',
        t('common.error', 'Fehler'),
        t(
          'mail.system.password.resetFailed',
          'Passwort konnte nicht zurückgesetzt werden.',
        ),
      )
    } finally {
      setBusy(false)
    }
  }

  const handleAddAlias = async () => {
    const p = newAliasPrefix.trim()
    if (!p) return
    setAliasBusy(true)
    try {
      if (category === 'group' && entry.ownerId != null) {
        await createGroupAlias(entry.ownerId, p)
      } else if (category === 'function' && entry.ownerId != null) {
        await createFunctionAlias(entry.ownerId, p)
      }
      setNewAliasPrefix('')
      invalidateAliases()
      notify(
        'success',
        t('common.saved', 'Gespeichert'),
        t('mail.admin.aliasCreated', 'Alias erstellt.'),
      )
    } catch {
      notify(
        'error',
        t('common.error', 'Fehler'),
        t('mail.admin.aliasCreateFailed', 'Alias konnte nicht erstellt werden.'),
      )
    } finally {
      setAliasBusy(false)
    }
  }

  const handleDeleteAlias = async (aliasId: number) => {
    setAliasBusy(true)
    try {
      if (category === 'group' && entry.ownerId != null) {
        await deleteGroupAlias(entry.ownerId, aliasId)
      } else if (category === 'function' && entry.ownerId != null) {
        await deleteFunctionAlias(entry.ownerId, aliasId)
      }
      invalidateAliases()
    } catch {
      notify(
        'error',
        t('common.deleteFailed', 'Löschen fehlgeschlagen'),
        t('mail.admin.aliasDeleteFailed', 'Alias konnte nicht gelöscht werden.'),
      )
    } finally {
      setAliasBusy(false)
    }
  }

  const handleToggleAlias = async (aliasId: number, aliasEnabled: boolean) => {
    setAliasBusy(true)
    try {
      if (category === 'group' && entry.ownerId != null) {
        await toggleGroupAlias(entry.ownerId, aliasId, aliasEnabled)
      } else if (category === 'function' && entry.ownerId != null) {
        await toggleFunctionAlias(entry.ownerId, aliasId, aliasEnabled)
      }
      invalidateAliases()
    } catch {
      notify(
        'error',
        t('common.error', 'Fehler'),
        t('mail.admin.aliasToggleFailed', 'Alias konnte nicht geändert werden.'),
      )
    } finally {
      setAliasBusy(false)
    }
  }

  const showQuota = entry.addressType === 'mailbox'
  const showRetention = category === 'member'
  const showPassword = category === 'system' && showQuota
  const canDelete = !entry.isProtected
  const showPrefix =
    canManage && (category === 'group' || category === 'function')
  const showAliases =
    canManage && (category === 'group' || category === 'function')
  const isLinkedAlias =
    entry.ownerType === 'mail_address' || entry.addressType === 'alias'
  const showForwardTargets =
    canManage && category === 'system' && !isLinkedAlias
  const showFixedTargets = isLinkedAlias

  return (
    <>
      <Modal
        open={open}
        onClose={onClose}
        title={t('mail.admin.settings', 'Mail-Einstellungen')}
        subtitle={entry.address}
        footer={
          <div
            style={{
              display: 'flex',
              gap: 8,
              justifyContent: 'space-between',
              width: '100%',
            }}
          >
            {canManage && canDelete ? (
              <Button
                size="sm"
                variant="light"
                color="red"
                onClick={() => setDeleteOpen(true)}
                disabled={busy}
              >
                {t('common.delete', 'Löschen')}
              </Button>
            ) : (
              <span />
            )}
            <div style={{ display: 'flex', gap: 8 }}>
              <Button variant="default" onClick={onClose} disabled={busy}>
                {t('common.cancel', 'Abbrechen')}
              </Button>
              {canManage && (
                <Button variant="filled" onClick={handleSave} disabled={busy}>
                  {busy ? '...' : t('common.save', 'Speichern')}
                </Button>
              )}
            </div>
          </div>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          {canManage && (
            <Field label={t('mail.enabled', 'Eingeschaltet')}>
              <Toggle checked={enabled} onChange={setEnabled} />
            </Field>
          )}

          {category !== 'system' && (
            <Field label={t('mail.forwarding', 'Weiterleitung')}>
              <Toggle
                checked={forwarding}
                onChange={setForwarding}
                disabled={!canManage}
              />
            </Field>
          )}

          {showQuota && canManage && (
            <Field label={t('mail.admin.quotaMb', 'Speicherplatz (MB)')}>
              <TextInput
                type="number"
                min={10}
                max={10240}
                value={quotaMb}
                onChange={(e) => setQuotaMb(Number(e.target.value))}
              />
            </Field>
          )}

          {showRetention && canManage && (
            <Field
              label={t(
                'mail.admin.retentionDays',
                'Aufbewahrung (Tage, leer = unbegrenzt)',
              )}
            >
              <TextInput
                type="number"
                min={0}
                value={retention ?? ''}
                onChange={(e) =>
                  setRetention(e.target.value ? Number(e.target.value) : null)
                }
                placeholder={t('mail.admin.retentionOff', 'Unbegrenzt')}
              />
            </Field>
          )}

          {showPrefix && (
            <Field label={t('mail.admin.mailPrefix', 'Mail-Präfix')}>
              <TextInput
                value={prefix}
                onChange={(e) => setPrefix(e.target.value)}
                placeholder="info"
              />
              {prefixChanged && prefix.trim() && prefixPreview && (
                <div
                  style={{
                    fontSize: 'var(--mantine-font-size-xs)',
                    color: '#2596be',
                    marginTop: 4,
                  }}
                >
                  {t('mail.admin.mailPrefixPreview', 'Vorschau')}:{' '}
                  {prefixPreview}
                </div>
              )}
            </Field>
          )}

          {showForwardTargets && (
            <Field
              label={t('mail.admin.forwardingTargets', 'Weiterleitungsziele')}
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {forwardTargets.map((target, i) => (
                  <div key={target + i} style={{ display: 'flex', gap: 6 }}>
                    <TextInput
                      value={target}
                      onChange={(e) => {
                        const next = [...forwardTargets]
                        next[i] = e.target.value
                        setForwardTargets(next)
                      }}
                      placeholder="user@example.com"
                    />
                    <Button
                      size="sm"
                      variant="light"
                      color="red"
                      onClick={() =>
                        setForwardTargets(
                          forwardTargets.filter((_, idx) => idx !== i),
                        )
                      }
                      disabled={busy}
                    >
                      ×
                    </Button>
                  </div>
                ))}
                <Button
                  size="sm"
                  variant="default"
                  onClick={() => setForwardTargets([...forwardTargets, ''])}
                  disabled={busy}
                >
                  + {t('mail.admin.addTarget', 'Ziel hinzufügen')}
                </Button>
              </div>
            </Field>
          )}

          {showFixedTargets && (
            <Field
              label={t('mail.admin.forwardingTargets', 'Weiterleitungsziele')}
              hint={t(
                'mail.admin.fixedTargets',
                'Fest an die übergeordnete Adresse gebunden, nicht änderbar',
              )}
            >
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 4,
                  opacity: 0.7,
                }}
              >
                {(entry.fixedForwardTargets ?? []).map((target) => (
                  <div
                    key={target}
                    style={{
                      fontSize: 'var(--mantine-font-size-sm)',
                      color: '#5e5873',
                      fontFamily: 'monospace',
                    }}
                  >
                    {target}
                  </div>
                ))}
                {(!entry.fixedForwardTargets ||
                  entry.fixedForwardTargets.length === 0) && (
                  <span
                    style={{
                      fontSize: 'var(--mantine-font-size-sm)',
                      color: '#8c86a0',
                      fontStyle: 'italic',
                    }}
                  >
                    {t(
                      'mail.admin.autoResolved',
                      'Automatisch von der übergeordneten Adresse übernommen',
                    )}
                  </span>
                )}
              </div>
            </Field>
          )}

          {showFromWhitelist && (
            <Field label={t('mail.admin.fromWhitelist', 'Erlaubte Absender (Senden als)')}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {wlEntries.map((addr, i) => (
                  <div key={addr + '-' + i} style={{ display: 'flex', gap: 6 }}>
                    <TextInput
                      value={addr}
                      onChange={(e) => {
                        const next = [...wlEntries]
                        next[i] = e.target.value
                        setWlEntries(next)
                      }}
                      placeholder="sender@example.org"
                      disabled={busy}
                    />
                    <Button
                      size="sm"
                      variant="light"
                      color="red"
                      onClick={() =>
                        setWlEntries(wlEntries.filter((_, idx) => idx !== i))
                      }
                      disabled={busy}
                    >
                      ×
                    </Button>
                  </div>
                ))}
                <Button
                  size="sm"
                  variant="default"
                  onClick={() => setWlEntries([...wlEntries, ''])}
                  disabled={busy}
                >
                  + {t('mail.admin.addWhitelist', 'Adresse hinzufügen')}
                </Button>
              </div>
              {wlEffective.length > 0 && (
                <div
                  style={{
                    fontSize: 'var(--mantine-font-size-xs)',
                    color: '#8c86a0',
                    marginTop: 6,
                  }}
                >
                  {t('mail.admin.effectiveWhitelist', 'Wirksam')}:{' '}
                  {wlEffective.join(', ')}
                </div>
              )}
            </Field>
          )}

          {showAliases && (
            <div>
              <div
                style={{
                  fontSize: 'var(--mantine-font-size-sm)',
                  fontWeight: 600,
                  color: '#2e2940',
                  marginBottom: 8,
                }}
              >
                {t('mail.admin.aliases', 'Weitere Aliasse')}
              </div>
              {aliases.length === 0 ? (
                <div
                  style={{
                    fontSize: 'var(--mantine-font-size-xs)',
                    color: '#8c86a0',
                  }}
                >
                  {t('mail.admin.noAliases', 'Keine weiteren Aliasse.')}
                </div>
              ) : (
                <div
                  style={{ display: 'flex', flexDirection: 'column', gap: 6 }}
                >
                  {aliases.map((alias) => (
                    <div
                      key={alias.id}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        padding: '6px 10px',
                        background: '#f4f2f9',
                        borderRadius: 6,
                      }}
                    >
                      <span
                        style={{
                          fontSize: 'var(--mantine-font-size-sm)',
                          flex: 1,
                        }}
                      >
                        {alias.address}
                      </span>
                      <Toggle
                        checked={alias.isEnabled}
                        onChange={(v) => handleToggleAlias(alias.id, v)}
                        disabled={aliasBusy}
                      />
                      <Button
                        size="sm"
                        variant="light"
                        color="red"
                        onClick={() => handleDeleteAlias(alias.id)}
                        disabled={aliasBusy}
                      >
                        ×
                      </Button>
                    </div>
                  ))}
                </div>
              )}
              <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                <TextInput
                  value={newAliasPrefix}
                  onChange={(e) => setNewAliasPrefix(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddAlias()}
                  placeholder={t(
                    'mail.admin.aliasPrefix',
                    'Präfix für neuen Alias',
                  )}
                  style={{ flex: 1 }}
                />
                <Button
                  size="sm"
                  variant="default"
                  onClick={handleAddAlias}
                  disabled={aliasBusy || !newAliasPrefix.trim()}
                >
                  + {t('mail.admin.addAlias', 'Alias')}
                </Button>
              </div>
            </div>
          )}

          {showPassword && canManage && (
            <Field
              label={t('mail.system.password.set', 'Passwort festlegen')}
            >
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <TextInput
                  value={customPassword}
                  onChange={(e) => setCustomPassword(e.target.value)}
                  placeholder="Custom password (optional)"
                  type="password"
                  disabled={busy}
                  style={{ flex: 1 }}
                />
                <Button
                  size="sm"
                  variant="default"
                  onClick={handleResetPassword}
                  disabled={busy}
                >
                  {customPassword.trim()
                    ? t('mail.system.password.set', 'Setzen')
                    : t('mail.system.password.reset', 'Passwort zurücksetzen')}
                </Button>
              </div>
            </Field>
          )}

          {entry.syncError && (
            <div
              style={{
                padding: 10,
                background: '#fff3e0',
                borderRadius: 6,
                fontSize: 'var(--mantine-font-size-xs)',
                color: '#e65100',
              }}
            >
              <strong>{t('mail.admin.syncError', 'Fehler')}:</strong>{' '}
              {entry.syncError}
            </div>
          )}
        </div>
      </Modal>

      <ConfirmModal
        open={deleteOpen}
        title={t('mail.admin.deleteTitle', 'Mail-Adresse entfernen')}
        body={t(
          'mail.admin.deleteBody',
          'Die Mail-Adresse {{address}} wird entfernt.',
          { address: entry.address },
        )}
        onConfirm={handleDelete}
        onClose={() => setDeleteOpen(false)}
      />
    </>
  )
}
