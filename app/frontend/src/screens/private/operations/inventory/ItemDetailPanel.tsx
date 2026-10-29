import { useState, useMemo } from 'react'
import { Button, TextInput, Badge, ActionIcon } from '@mantine/core'
import { useT } from '@/locales/i18n'
import ReactDOM from 'react-dom'
import {
  IconPlus,
  IconPencil,
  IconX,
  IconSearch,
  IconEye,
  IconEyeOff,
  IconCircleCheck,
  IconExternalLink,
  IconUserCheck,
  IconInfoCircle,
} from '@tabler/icons-react'
import { useToast } from '@/context/AppContext'
import { Avatar } from '@/components/ui'
import type { InventoryItem } from '@/types'
import { addInstruction, removeInstruction, addSelfInstruction } from '@/api/inventory'
import { useMemberSearch } from '@/data/members'
import { PluginSlot } from '@/plugins'
import { CATEGORY_COLORS, CATEGORY_ICONS, STATUS_CONFIG } from './constants'

interface DetailPanelProps {
  item: InventoryItem
  onClose: () => void
  onEdit: () => void
  currentUserId: number | null
  currentUserName: string
  onInstructionChange: (updated: InventoryItem) => void
}

export function ItemDetailPanel({
  item,
  onClose,
  onEdit,
  currentUserId,
  currentUserName,
  onInstructionChange,
}: DetailPanelProps) {
  const { t } = useT()
  const { notify } = useToast()
  const [addSearch, setAddSearch] = useState('')
  const { data: searchData } = useMemberSearch(addSearch, { enabled: addSearch.trim().length >= 2 })
  const addResults = useMemo(() => {
    if (addSearch.trim().length < 2 || !searchData) return []
    const instructed = new Set(item.instructedMemberIds.map(String))
    return searchData.members.filter((m) => !instructed.has(m.id)).slice(0, 6)
  }, [addSearch, searchData, item.instructedMemberIds])
  const [loading, setLoading] = useState(false)

  const isSelfInstructed =
    currentUserId !== null && item.instructedMemberIds.includes(currentUserId)

  // Bug fix: update both instructedMemberIds AND instructedMemberNames on every change
  const handleAddInstruction = async (memberId: number, memberName: string) => {
    setLoading(true)
    try {
      await addInstruction(item.id, memberId)
      onInstructionChange({
        ...item,
        instructedMemberIds: [...item.instructedMemberIds, memberId],
        instructedMemberNames: [...item.instructedMemberNames, memberName],
      })
      setAddSearch('')
      notify(
        'success',
        t('inventory.instruction.recorded', 'Einweisung erfasst'),
        t(
          'inventory.memberMarkedInstructed',
          '{{member}} ist als eingewiesen markiert.',
          { member: memberName },
        ),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error', 'Fehler'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    } finally {
      setLoading(false)
    }
  }

  const handleRemoveInstruction = async (memberId: number, idx: number) => {
    setLoading(true)
    try {
      await removeInstruction(item.id, memberId)
      onInstructionChange({
        ...item,
        instructedMemberIds: item.instructedMemberIds.filter(
          (_, i) => i !== idx,
        ),
        instructedMemberNames: item.instructedMemberNames.filter(
          (_, i) => i !== idx,
        ),
      })
      notify(
        'info',
        t('inventory.instruction.removed', 'Einweisung entfernt'),
        t('inventory.recordCleared', 'Eintrag entfernt.'),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('inventory.failed', 'Fehler'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekannter Fehler'),
      )
    } finally {
      setLoading(false)
    }
  }

  const handleSelfInstruct = async () => {
    setLoading(true)
    try {
      await addSelfInstruction(item.id)
      if (currentUserId !== null) {
        onInstructionChange({
          ...item,
          instructedMemberIds: [...item.instructedMemberIds, currentUserId],
          instructedMemberNames: [
            ...item.instructedMemberNames,
            currentUserName,
          ],
        })
      }
      notify(
        'success',
        t('inventory.recorded', 'Erfasst'),
        t(
          'inventory.selfInstructedMsg',
          'Du bist jetzt für diesen Gegenstand als eingewiesen markiert.',
        ),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('inventory.failed', 'Fehler'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekannter Fehler'),
      )
    } finally {
      setLoading(false)
    }
  }

  const sc = STATUS_CONFIG[item.status]
  const cc = CATEGORY_COLORS[item.category]

  return ReactDOM.createPortal(
    <>
      <div className="scrim" onClick={onClose} />
      <div className="notif-panel open" style={{ width: 440 }} role="dialog" aria-label={item.name}>
        {/* Header */}
        <div
          style={{
            padding: '20px 20px 14px',
            borderBottom: '1px solid #d6d2e3',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: 10,
                background: cc + '22',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
                color: cc,
              }}
            >
              {CATEGORY_ICONS[item.category]}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  fontSize: 'var(--mantine-font-size-md)',
                  fontWeight: 700,
                  color: '#1a1625',
                }}
              >
                {item.name}
              </div>
              <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
                <Badge
                  variant="light"
                  style={{
                    borderColor: cc + '55',
                    color: cc,
                    background: cc + '11',
                  }}
                >
                  {item.category}
                </Badge>
                <Badge
                  variant="light"
                  style={{
                    borderColor: sc.color + '55',
                    color: sc.color,
                    background: sc.color + '11',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4,
                  }}
                >
                  {sc.icon}
                  {t(`inventory.status_${item.status}`, sc.label)}
                </Badge>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 4 }}>
              <Button size="sm" variant="subtle" onClick={onEdit}>
                <IconPencil size={16} />
              </Button>
              <ActionIcon variant="subtle" onClick={onClose} aria-label={t('common.close')}>
                <IconX size={16} />
              </ActionIcon>
            </div>
          </div>
        </div>

        <div style={{ flex: 1, overflowY: 'auto' }}>
          {/* Details */}
          <div
            style={{ padding: '14px 20px', borderBottom: '1px solid #e6e3ef' }}
          >
            {item.description && (
              <p
                style={{
                  fontSize: 'var(--mantine-font-size-sm)',
                  color: '#2e2940',
                  lineHeight: 1.6,
                  margin: '0 0 12px',
                }}
              >
                {item.description}
              </p>
            )}
            <div
              className="grid-2"
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: 10,
              }}
            >
              {item.ownerName && (
                <div>
                  <div
                    style={{
                      fontSize: 'var(--mantine-font-size-xs)',
                      fontWeight: 600,
                      color: '#8c86a0',
                      textTransform: 'uppercase',
                      letterSpacing: '0.06em',
                      marginBottom: 2,
                    }}
                  >
                    Bsitzer
                  </div>
                  <div
                    style={{
                      fontSize: 'var(--mantine-font-size-sm)',
                      color: '#2e2940',
                    }}
                  >
                    {item.ownerName}
                  </div>
                </div>
              )}
              {item.responsibleName && (
                <div>
                  <div
                    style={{
                      fontSize: 'var(--mantine-font-size-xs)',
                      fontWeight: 600,
                      color: '#8c86a0',
                      textTransform: 'uppercase',
                      letterSpacing: '0.06em',
                      marginBottom: 2,
                    }}
                  >
                    Verantwortlich
                  </div>
                  <div
                    style={{
                      fontSize: 'var(--mantine-font-size-sm)',
                      color: '#2e2940',
                    }}
                  >
                    {item.responsibleName}
                  </div>
                </div>
              )}
              {item.cost && (
                <div>
                  <div
                    style={{
                      fontSize: 'var(--mantine-font-size-xs)',
                      fontWeight: 600,
                      color: '#8c86a0',
                      textTransform: 'uppercase',
                      letterSpacing: '0.06em',
                      marginBottom: 2,
                    }}
                  >
                    Cost
                  </div>
                  <div
                    className="num"
                    style={{
                      fontSize: 'var(--mantine-font-size-sm)',
                      color: '#2e2940',
                    }}
                  >
                    CHF {item.cost}
                  </div>
                </div>
              )}
              <div>
                <div
                  style={{
                    fontSize: 'var(--mantine-font-size-xs)',
                    fontWeight: 600,
                    color: '#8c86a0',
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    marginBottom: 2,
                  }}
                >
                  Visibility
                </div>
                <div
                  style={{
                    fontSize: 'var(--mantine-font-size-sm)',
                    color: '#2e2940',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4,
                  }}
                >
                  {item.visibility === 'private' ? (
                    <IconEyeOff size={16} />
                  ) : (
                    <IconEye size={16} />
                  )}
                  {item.visibility === 'private' ? t('inventory.private', 'Privat') : t('inventory.shared', 'Geteilt')}
                </div>
              </div>
            </div>
          </div>

          {/* Links */}
          {item.links.length > 0 && (
            <div
              style={{
                padding: '14px 20px',
                borderBottom: '1px solid #e6e3ef',
              }}
            >
              <div
                style={{
                  fontSize: 'var(--mantine-font-size-xs)',
                  fontWeight: 600,
                  color: '#5e5873',
                  marginBottom: 8,
                }}
              >
                LINKS
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {item.links.map((link, i) => (
                  <a
                    key={link.url + i}
                    href={link.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      fontSize: 'var(--mantine-font-size-sm)',
                      color: '#2596be',
                      textDecoration: 'none',
                    }}
                  >
                    <IconExternalLink size={16} style={{ flexShrink: 0 }} />
                    {link.label || link.url}
                  </a>
                ))}
              </div>
            </div>
          )}

          {/* Instruction tracking */}
          {item.instructionRequired ? (
            <div style={{ padding: '14px 20px' }}>
              <div
                style={{
                  fontSize: 'var(--mantine-font-size-xs)',
                  fontWeight: 600,
                  color: '#5e5873',
                  marginBottom: 10,
                }}
              >
                INSTRUKTION ERFORDERLICH
              </div>

              {!isSelfInstructed && currentUserId !== null && (
                <Button
                  variant="filled"
                  style={{
                    width: '100%',
                    marginBottom: 12,
                    justifyContent: 'center',
                    fontSize: 'var(--mantine-font-size-sm)',
                  }}
                  onClick={handleSelfInstruct}
                  disabled={loading}
                >
                  <IconUserCheck size={16} />
                  {t(
                    'inventory.markMyselfInstructed',
                    'Mich als eingewiesen markieren',
                  )}
                </Button>
              )}
              {isSelfInstructed && (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    fontSize: 'var(--mantine-font-size-sm)',
                    color: '#1f9d57',
                    marginBottom: 12,
                    padding: '8px 12px',
                    background: '#1f9d5711',
                    borderRadius: 8,
                  }}
                >
                  <IconCircleCheck size={16} />
                  {t(
                    'inventory.youAreInstructed',
                    'Du bist für diesen Gegenstand eingewiesen',
                  )}
                </div>
              )}

              <div
                style={{
                  fontSize: 'var(--mantine-font-size-xs)',
                  fontWeight: 600,
                  color: '#8c86a0',
                  marginBottom: 6,
                }}
              >
                {t('common.addMember', 'Mitglied hinzufügen')}
              </div>
              <div style={{ position: 'relative', marginBottom: 8 }}>
                <TextInput
                  style={{ paddingLeft: 32, height: 36 }}
                  placeholder={t(
                    'inventory.searchMembersPlaceholder',
                    'Mitglieder suchen …',
                  )}
                  value={addSearch}
                  onChange={(e) => setAddSearch(e.target.value)}
                />
                <IconSearch
                  size={16}
                  style={{
                    position: 'absolute',
                    left: 10,
                    top: '50%',
                    transform: 'translateY(-50%)',
                    color: '#8c86a0',
                  }}
                />
              </div>
              {addResults.length > 0 && (
                <div
                  style={{
                    border: '1px solid #d6d2e3',
                    borderRadius: 8,
                    overflow: 'hidden',
                    background: 'white',
                    marginBottom: 10,
                  }}
                >
                  {addResults.map((m) => (
                    <Button
                      key={m.id}
                      variant="subtle"
                      style={{
                        width: '100%',
                        justifyContent: 'flex-start',
                        padding: '8px 12px',
                        borderRadius: 0,
                        borderBottom: '1px solid #e6e3ef',
                        gap: 8,
                      }}
                      onClick={() => handleAddInstruction(Number(m.id), m.name)}
                    >
                      <Avatar name={m.name} color={m.avatarColor} size={24} />
                      <span
                        style={{
                          fontSize: 'var(--mantine-font-size-sm)',
                          flex: 1,
                          textAlign: 'left',
                        }}
                      >
                        {m.name}
                      </span>
                      <IconPlus size={16} style={{ color: '#1f9d57' }} />
                    </Button>
                  ))}
                </div>
              )}

              {item.instructedMemberIds.length === 0 ? (
                <div
                  style={{
                    padding: '16px 0',
                    textAlign: 'center',
                    color: '#8c86a0',
                    fontSize: 'var(--mantine-font-size-sm)',
                  }}
                >
                  {t(
                    'inventory.noMembersInstructed',
                    'Noch niemand eingewiesen.',
                  )}
                </div>
              ) : (
                <div
                  style={{ display: 'flex', flexDirection: 'column', gap: 2 }}
                >
                  {item.instructedMemberNames.map((name, i) => (
                    <div
                      key={item.instructedMemberIds[i]}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 10,
                        padding: '8px 0',
                        borderBottom: '1px solid #f1eff7',
                      }}
                    >
                      <IconCircleCheck
                        size={16}
                        style={{ color: '#1f9d57', flexShrink: 0 }}
                      />
                      <span
                        style={{
                          flex: 1,
                          fontSize: 'var(--mantine-font-size-sm)',
                          color: '#1a1625',
                        }}
                      >
                        {name}
                      </span>
                      <Button
                        size="sm"
                        variant="subtle"
                        style={{ color: '#8c86a0', padding: '2px 6px' }}
                        onClick={() =>
                          handleRemoveInstruction(
                            item.instructedMemberIds[i],
                            i,
                          )
                        }
                        disabled={loading}
                      >
                        <IconX size={16} />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div
              style={{
                padding: '16px 20px',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                fontSize: 'var(--mantine-font-size-sm)',
                color: '#8c86a0',
              }}
            >
              <IconInfoCircle size={16} />
              {t(
                'inventory.noInstructionRequired',
                'Für diesen Gegenstand ist keine Einweisung nötig.',
              )}
            </div>
          )}
          <PluginSlot name="inventory.item" props={{ itemId: Number(item.id) }} />
        </div>
      </div>
    </>,
    document.body,
  )
}
