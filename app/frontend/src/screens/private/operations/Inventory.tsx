import { useState, useEffect, useMemo } from 'react'
import {
  Button,
  TextInput,
  Textarea,
  Select,
  Badge,
  ActionIcon,
  Paper,
  Text,
} from '@mantine/core'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useT } from '@/locales/i18n'
import ReactDOM from 'react-dom'
import {
  IconPlus,
  IconTool,
  IconBox,
  IconStack2,
  IconPencil,
  IconX,
  IconSearch,
  IconEye,
  IconEyeOff,
  IconCircleCheck,
  IconAlertCircle,
  IconClock,
  IconArchive,
  IconExternalLink,
  IconUserCheck,
  IconInfoCircle,
} from '@tabler/icons-react'
import { useToast, useAuth } from '@/context/AppContext'
import {
  PageHead,
  Modal,
  Field,
  Avatar,
  usePagination,
  ConfirmModal,
  ErrorBanner,
  DataTable,
  ActionButtons,
  Seg,
  CardGrid,
  CardItem,
  LoadingSpinner,
  EmptyState,
  Pagination,
} from '@/components/ui'
import type {
  InventoryItem,
  InventoryCategory,
  InventoryStatus,
  InventoryVisibility,
  InventoryLink,
} from '@/types'
import {
  listInventory,
  createInventoryItem,
  updateInventoryItem,
  deleteInventoryItem,
  addInstruction,
  removeInstruction,
  addSelfInstruction,
} from '@/api/inventory'
import { listMembers } from '@/api/members'
import { PluginSlot } from '@/plugins'

// -- Constants --------------------------------------------------------------

const CATEGORIES: InventoryCategory[] = ['Tool', 'Item', 'Material']
const STATUSES: InventoryStatus[] = [
  'available',
  'in_use',
  'maintenance',
  'broken',
  'archived',
]

const CATEGORY_ICONS: Record<InventoryCategory, React.ReactNode> = {
  Tool: <IconTool size={16} />,
  Item: <IconBox size={16} />,
  Material: <IconStack2 size={16} />,
}

const CATEGORY_COLORS: Record<InventoryCategory, string> = {
  Tool: '#2596be',
  Item: '#1f9d57',
  Material: '#c2870f',
}

const STATUS_CONFIG: Record<
  InventoryStatus,
  { label: string; color: string; icon: React.ReactNode }
> = {
  available: {
    label: 'Verfüegbar',
    color: '#1f9d57',
    icon: <IconCircleCheck size={12} />,
  },
  in_use: {
    label: 'In Bruch',
    color: '#2596be',
    icon: <IconClock size={12} />,
  },
  maintenance: {
    label: 'Wartig',
    color: '#c2870f',
    icon: <IconAlertCircle size={12} />,
  },
  broken: {
    label: 'Defekt',
    color: '#ff4d3d',
    icon: <IconAlertCircle size={12} />,
  },
  archived: {
    label: 'Archiviert',
    color: '#99a2ac',
    icon: <IconArchive size={12} />,
  },
  checked_out: {
    label: 'Ausgecheckt',
    color: '#2596be',
    icon: <IconClock size={12} />,
  },
  pending: {
    label: 'Ausstehend',
    color: '#c2870f',
    icon: <IconAlertCircle size={12} />,
  },
  lost: {
    label: 'Verloren',
    color: '#ff4d3d',
    icon: <IconAlertCircle size={12} />,
  },
  retired: {
    label: 'Ausgemustert',
    color: '#99a2ac',
    icon: <IconArchive size={12} />,
  },
}

// -- Item Detail Panel -----------------------------------------------------

interface DetailPanelProps {
  item: InventoryItem
  onClose: () => void
  onEdit: () => void
  currentUserId: number | null
  currentUserName: string
  onInstructionChange: (updated: InventoryItem) => void
}

function ItemDetailPanel({
  item,
  onClose,
  onEdit,
  currentUserId,
  currentUserName,
  onInstructionChange,
}: DetailPanelProps) {
  const { t } = useT()
  const { notify } = useToast()
  const { data: membersData } = useQuery({
    queryKey: ['members'],
    queryFn: () => listMembers({ pageSize: 500 }),
  })
  const members = useMemo(
    () =>
      (membersData?.members ?? []).map((m) => ({
        id: m.id,
        name: m.name,
        avatarColor: m.avatarColor,
      })),
    [membersData],
  )
  const [addSearch, setAddSearch] = useState('')
  const [addResults, setAddResults] = useState<
    { id: string; name: string; avatarColor: string }[]
  >([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const timer = setTimeout(() => {
      if (addSearch.length < 2) {
        setAddResults([])
        return
      }
      const lower = addSearch.toLowerCase()
      const instructedSet = new Set(item.instructedMemberIds.map(String))
      setAddResults(
        members
          .filter(
            (m) =>
              m.name.toLowerCase().includes(lower) && !instructedSet.has(m.id),
          )
          .slice(0, 6),
      )
    }, 200)
    return () => clearTimeout(timer)
  }, [addSearch, members, item.instructedMemberIds])

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
      setAddResults([])
      notify(
        'success',
        t('inventory.instruction.recorded', 'Instruktion erfasst'),
        t(
          'inventory.memberMarkedInstructed',
          '{{member}} isch als instruiert markiert.',
          { member: memberName },
        ),
      )
    } catch (err: unknown) {
      notify(
        'error',
        'Failed',
        err instanceof Error ? err.message : 'Unknown error',
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
        t('inventory.instruction.removed', 'Instruktion entfernt'),
        t('inventory.recordCleared', 'Datensatz gelöscht.'),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('inventory.failed', 'Fehler'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekannte Fehler'),
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
          'Du bisch jetzt als instruiert markiert für das Item.',
        ),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('inventory.failed', 'Fehler'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekannte Fehler'),
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
      <div className="notif-panel open" style={{ width: 440 }}>
        {/* Header */}
        <div
          style={{
            padding: '20px 20px 14px',
            borderBottom: '1px solid #d3ddd7',
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
                  color: '#181818',
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
                  {sc.label}
                </Badge>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 4 }}>
              <Button size="sm" variant="subtle" onClick={onEdit}>
                <IconPencil size={16} />
              </Button>
              <ActionIcon variant="subtle" onClick={onClose}>
                <IconX size={16} />
              </ActionIcon>
            </div>
          </div>
        </div>

        <div style={{ flex: 1, overflowY: 'auto' }}>
          {/* Details */}
          <div
            style={{ padding: '14px 20px', borderBottom: '1px solid #e3eae6' }}
          >
            {item.description && (
              <p
                style={{
                  fontSize: 'var(--mantine-font-size-sm)',
                  color: '#3a4048',
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
                      color: '#99a2ac',
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
                      color: '#3a4048',
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
                      color: '#99a2ac',
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
                      color: '#3a4048',
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
                      color: '#99a2ac',
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
                      color: '#3a4048',
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
                    color: '#99a2ac',
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
                    color: '#3a4048',
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
                  {item.visibility === 'private' ? 'Private' : 'Shared'}
                </div>
              </div>
            </div>
          </div>

          {/* Links */}
          {item.links.length > 0 && (
            <div
              style={{
                padding: '14px 20px',
                borderBottom: '1px solid #e3eae6',
              }}
            >
              <div
                style={{
                  fontSize: 'var(--mantine-font-size-xs)',
                  fontWeight: 600,
                  color: '#6b7480',
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
                  color: '#6b7480',
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
                    'Mich als instruiert markiere',
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
                    'Du bisch instruiert für das Item',
                  )}
                </div>
              )}

              <div
                style={{
                  fontSize: 'var(--mantine-font-size-xs)',
                  fontWeight: 600,
                  color: '#99a2ac',
                  marginBottom: 6,
                }}
              >
                {t('common.addMember', 'MITGLID HINZUE')}
              </div>
              <div style={{ position: 'relative', marginBottom: 8 }}>
                <TextInput
                  style={{ paddingLeft: 32, height: 36 }}
                  placeholder={t(
                    'inventory.searchMembersPlaceholder',
                    'Mitglieder sueche…',
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
                    color: '#99a2ac',
                  }}
                />
              </div>
              {addResults.length > 0 && (
                <div
                  style={{
                    border: '1px solid #d3ddd7',
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
                        borderBottom: '1px solid #e3eae6',
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
                    color: '#99a2ac',
                    fontSize: 'var(--mantine-font-size-sm)',
                  }}
                >
                  {t(
                    'inventory.noMembersInstructed',
                    'No cheni Mitglieder instruiert.',
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
                        borderBottom: '1px solid #f0f4f1',
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
                          color: '#181818',
                        }}
                      >
                        {name}
                      </span>
                      <Button
                        size="sm"
                        variant="subtle"
                        style={{ color: '#99a2ac', padding: '2px 6px' }}
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
                color: '#99a2ac',
              }}
            >
              <IconInfoCircle size={16} />
              {t(
                'inventory.noInstructionRequired',
                'Für das Item isch cheni Instruktion erforderlich.',
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

// -- Link Editor ------------------------------------------------------------

function LinkEditor({
  links,
  onChange,
}: {
  links: InventoryLink[]
  onChange: (l: InventoryLink[]) => void
}) {
  const add = () => onChange([...links, { label: '', url: '' }])
  const remove = (i: number) => onChange(links.filter((_, idx) => idx !== i))
  const update = (i: number, field: 'label' | 'url', val: string) =>
    onChange(links.map((l, idx) => (idx === i ? { ...l, [field]: val } : l)))

  return (
    <div>
      {links.map((l, i) => (
        <div
          key={l.url + i}
          className="grid-3"
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr auto',
            gap: 6,
            marginBottom: 6,
          }}
        >
          <TextInput
            placeholder="Label"
            value={l.label}
            onChange={(e) => update(i, 'label', e.target.value)}
            style={{ height: 34, fontSize: 'var(--mantine-font-size-xs)' }}
          />
          <TextInput
            placeholder="https://…"
            value={l.url}
            onChange={(e) => update(i, 'url', e.target.value)}
            style={{ height: 34, fontSize: 'var(--mantine-font-size-xs)' }}
          />
          <Button
            size="sm"
            variant="subtle"
            style={{ color: '#ff4d3d' }}
            onClick={() => remove(i)}
          >
            <IconX size={16} />
          </Button>
        </div>
      ))}
      <Button
        size="sm"
        variant="subtle"
        onClick={add}
        style={{ fontSize: 'var(--mantine-font-size-xs)', color: '#2596be' }}
      >
        <IconPlus size={16} />
        Add link
      </Button>
    </div>
  )
}

// -- Main Screen -----------------------------------------------------------

export function InventoryScreen() {
  const { t } = useT()
  const { notify } = useToast()
  const { currentUser, hasPermission } = useAuth()
  const queryClient = useQueryClient()
  const canCreate = hasPermission('items.items.create')
  const canUpdate = hasPermission('items.items.update')
  const canDelete = hasPermission('items.items.delete')
  const {
    data: items = [],
    isLoading: loading,
    error: fetchError,
    refetch,
  } = useQuery({
    queryKey: ['inventory'],
    queryFn: () => listInventory(),
  })
  const { data: membersData } = useQuery({
    queryKey: ['members'],
    queryFn: () => listMembers({ pageSize: 500 }),
  })
  const members = useMemo(
    () => (membersData?.members ?? []).map((m) => ({ id: m.id, name: m.name })),
    [membersData],
  )
  const [catFilter, setCatFilter] = useState<InventoryCategory | 'All'>('All')
  const [statusFilter, setStatusFilter] = useState<InventoryStatus | 'All'>(
    'All',
  )
  const [search, setSearch] = useState('')
  const [view, setView] = useState<'table' | 'cards'>('cards')

  const [addOpen, setAddOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<InventoryItem | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<InventoryItem | null>(null)
  const [detailItem, setDetailItem] = useState<InventoryItem | null>(null)

  // Form state
  const [fName, setFName] = useState('')
  const [fCat, setFCat] = useState<InventoryCategory>('Tool')
  const [fDesc, setFDesc] = useState('')
  const [fOwner, setFOwner] = useState<number | undefined>(undefined)
  const [fResponsible, setFResponsible] = useState<number | undefined>(
    undefined,
  )
  const [fVisibility, setFVisibility] = useState<InventoryVisibility>('shared')
  const [fStatus, setFStatus] = useState<InventoryStatus>('available')
  const [fCost, setFCost] = useState('')
  const [fLinks, setFLinks] = useState<InventoryLink[]>([])
  const [fInstructionRequired, setFInstructionRequired] = useState(false)

  const filtered = items.filter((item) => {
    if (catFilter !== 'All' && item.category !== catFilter) return false
    if (statusFilter !== 'All' && item.status !== statusFilter) return false
    if (search && !item.name.toLowerCase().includes(search.toLowerCase()))
      return false
    return true
  })

  const pg = usePagination(filtered, 12)

  const resetForm = (item?: InventoryItem) => {
    setFName(item?.name ?? '')
    setFCat(item?.category ?? 'Tool')
    setFDesc(item?.description ?? '')
    setFOwner(item?.ownerId ?? undefined)
    setFResponsible(item?.responsibleId ?? undefined)
    setFVisibility(item?.visibility ?? 'shared')
    setFStatus(item?.status ?? 'available')
    setFCost(item?.cost ?? '')
    setFLinks(item?.links ?? [])
    setFInstructionRequired(item?.instructionRequired ?? false)
  }

  const openAdd = () => {
    resetForm()
    setAddOpen(true)
  }
  const openEdit = (item: InventoryItem) => {
    setEditTarget(item)
    resetForm(item)
  }

  const saveAdd = async () => {
    if (!fName) return
    try {
      await createInventoryItem({
        name: fName,
        category: fCat,
        description: fDesc || undefined,
        ownerId: fOwner,
        responsibleId: fResponsible,
        visibility: fVisibility,
        status: fStatus,
        cost: fCost || null,
        links: fLinks,
        instructionRequired: fInstructionRequired,
      })
      queryClient.invalidateQueries({ queryKey: ['inventory'] })
      setAddOpen(false)
      notify(
        'success',
        t('inventory.item.added', 'Item hinzuegse', { name: fName }),
        t(
          'inventory.item.addedMsg',
          '{{name}} isch zum Inventar hinzuegse worde.',
          { name: fName },
        ),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.createFailed', 'Erstelle fehlgeschlage'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekannte Fehler'),
      )
    }
  }

  const saveEdit = async () => {
    if (!editTarget || !fName) return
    try {
      const item = await updateInventoryItem(editTarget.id, {
        name: fName,
        category: fCat,
        description: fDesc || undefined,
        ownerId: fOwner ?? null,
        responsibleId: fResponsible ?? null,
        visibility: fVisibility,
        status: fStatus,
        cost: fCost || null,
        links: fLinks,
        instructionRequired: fInstructionRequired,
      })
      queryClient.invalidateQueries({ queryKey: ['inventory'] })
      if (detailItem?.id === item.id) setDetailItem(item)
      setEditTarget(null)
      notify(
        'success',
        t('inventory.item.updated', 'Item aktualisiert'),
        t('inventory.item.updatedMsg', '{{name}} isch aktualisiert worde.', {
          name: fName,
        }),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.updateFailed', 'Update fehlgeschlage'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekannte Fehler'),
      )
    }
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    try {
      await deleteInventoryItem(deleteTarget.id)
      queryClient.invalidateQueries({ queryKey: ['inventory'] })
      if (detailItem?.id === deleteTarget.id) setDetailItem(null)
      notify(
        'info',
        t('inventory.item.removed', 'Item entfernt'),
        t('inventory.item.removedMsg', '{{name}} isch glöscht worde.', {
          name: deleteTarget.name,
        }),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.deleteFailed', 'Lösche fehlgeschlage'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekannte Fehler'),
      )
    } finally {
      setDeleteTarget(null)
    }
  }

  const handleInstructionChange = (updated: InventoryItem) => {
    queryClient.invalidateQueries({ queryKey: ['inventory'] })
    setDetailItem(updated)
  }

  const itemForm = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <Field label={t('common.name', 'Name')}>
        <TextInput
          value={fName}
          onChange={(e) => setFName(e.target.value)}
          placeholder={t('common.namePlaceholder', 'z.B. MIG Schweissgerät')}
        />
      </Field>
      <div
        className="grid-2"
        style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}
      >
        <Field label={t('inventory.category', 'Kategorie')}>
          <Select
            data={[
              { value: 'Tool', label: t('inventory.tool', 'Wärchzeug') },
              { value: 'Item', label: t('inventory.item', 'Item') },
              { value: 'Material', label: t('inventory.material', 'Material') },
            ]}
            value={fCat}
            onChange={(v) => setFCat((v ?? 'Tool') as InventoryCategory)}
          />
        </Field>
        <Field label={t('common.status', 'Status')}>
          <Select
            data={STATUSES.map((s) => ({
              value: s,
              label: t(`inventory.status_${s}`, STATUS_CONFIG[s].label),
            }))}
            value={fStatus}
            onChange={(v) => setFStatus((v ?? 'active') as InventoryStatus)}
          />
        </Field>
      </div>
      <Field
        label={t('inventory.descriptionOptional', 'Beschribig (optional)')}
      >
        <Textarea
          rows={2}
          value={fDesc}
          onChange={(e) => setFDesc(e.target.value)}
          placeholder={t('common.descriptionPlaceholder', 'Kurzi Beschribig…')}
        />
      </Field>
      <div
        className="grid-2"
        style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}
      >
        <Field label={t('inventory.owner', 'Bsitzer')}>
          <Select
            data={[
              { value: '', label: t('inventory.noOwner', 'Kei Bsitzer') },
              ...members.map((m) => ({
                value: String(m.id),
                label: m.name,
              })),
            ]}
            value={fOwner != null ? String(fOwner) : ''}
            onChange={(v) => setFOwner(v && v !== '' ? Number(v) : undefined)}
            searchable
          />
        </Field>
        <Field label={t('inventory.responsible', 'Verantwortlich')}>
          <Select
            data={[
              {
                value: '',
                label: t('inventory.noOneAssigned', 'Niemand zuegwise'),
              },
              ...members.map((m) => ({
                value: String(m.id),
                label: m.name,
              })),
            ]}
            value={fResponsible != null ? String(fResponsible) : ''}
            onChange={(v) =>
              setFResponsible(v && v !== '' ? Number(v) : undefined)
            }
            searchable
          />
        </Field>
      </div>
      <div
        className="grid-2"
        style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}
      >
        <Field label={t('inventory.visibility', 'Sichtbarkeit')}>
          <Select
            data={[
              { value: 'shared', label: t('inventory.shared', 'Gmeinsam') },
              { value: 'private', label: t('inventory.private', 'Privat') },
            ]}
            value={fVisibility}
            onChange={(v) =>
              setFVisibility((v ?? 'shared') as InventoryVisibility)
            }
          />
        </Field>
        <Field label={t('inventory.costOptional', 'Koste (CHF, optional)')}>
          <TextInput
            type="number"
            min={0}
            step="0.01"
            value={fCost}
            onChange={(e) => setFCost(e.target.value)}
            placeholder="0.00"
          />
        </Field>
      </div>
      <Field label={t('inventory.links', 'Links')}>
        <LinkEditor links={fLinks} onChange={setFLinks} />
      </Field>
      <label
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          fontSize: 'var(--mantine-font-size-sm)',
          color: '#3a4048',
          cursor: 'pointer',
        }}
      >
        <input
          type="checkbox"
          checked={fInstructionRequired}
          onChange={(e) => setFInstructionRequired(e.target.checked)}
        />
        {t(
          'inventory.instruction.required',
          'Instruktion vor Bruch erforderlich',
        )}
      </label>
    </div>
  )

  const currentUserId = currentUser ? Number(currentUser.id) : null
  const currentUserName = currentUser?.name ?? ''

  return (
    <div>
      <PageHead
        eyebrow={t('shell.sections.workspace', 'Werkplatz')}
        title={t('inventory.title', 'Inventar')}
        desc={t('inventory.desc', 'Wärchzeug, Items und Material verfolge.')}
        actions={
          canCreate && (
            <Button variant="filled" onClick={openAdd}>
              <IconPlus size={16} />
              {t('inventory.addItem', 'Item hinzue')}
            </Button>
          )
        }
      />

      {fetchError ? (
        <ErrorBanner
          message={
            fetchError instanceof Error
              ? fetchError.message
              : t(
                  'inventory.failedToLoadInventory',
                  'Inventar chonnt n\u00f6d glade w\u00e4rde',
                )
          }
          onRetry={() => refetch()}
        />
      ) : view === 'table' ? (
        <DataTable
          breakpoint="wide"
          columns={[
            {
              key: 'name',
              header: t('common.name', 'Name'),
              render: (item) => (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                  }}
                >
                  <span
                    className="dot"
                    style={{ background: CATEGORY_COLORS[item.category] }}
                  />
                  <span style={{ color: CATEGORY_COLORS[item.category] }}>
                    {CATEGORY_ICONS[item.category]}
                  </span>
                  <span style={{ fontWeight: 600, color: '#181818' }}>
                    {item.name}
                  </span>
                </div>
              ),
            },
            {
              key: 'category',
              header: t('inventory.category', 'Kategorie'),
              width: 120,
              render: (item) => (
                <Badge
                  variant="light"
                  style={{
                    fontSize: 'var(--mantine-font-size-xs)',
                    borderColor: CATEGORY_COLORS[item.category] + '44',
                    color: CATEGORY_COLORS[item.category],
                    background: CATEGORY_COLORS[item.category] + '11',
                  }}
                >
                  {item.category === 'Tool'
                    ? t('inventory.tool', 'W\u00e4rchzeug')
                    : item.category === 'Item'
                      ? t('inventory.item', 'Item')
                      : t('inventory.material', 'Material')}
                </Badge>
              ),
            },
            {
              key: 'status',
              header: t('common.status', 'Status'),
              width: 130,
              render: (item) => {
                const sc = STATUS_CONFIG[item.status]
                return (
                  <Badge
                    variant="light"
                    style={{
                      fontSize: 'var(--mantine-font-size-xs)',
                      borderColor: sc.color + '44',
                      color: sc.color,
                      background: sc.color + '11',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 3,
                    }}
                  >
                    {sc.icon}
                    {sc.label}
                  </Badge>
                )
              },
            },
            {
              key: 'owner',
              header: t('inventory.owner', 'Bsitzer'),
              render: (item) => (
                <span
                  style={{
                    color: item.ownerName ? '#3a4048' : '#c2c9d0',
                    fontSize: 'var(--mantine-font-size-sm)',
                  }}
                >
                  {item.ownerName ?? t('inventory.noOwner', 'Kei Bsitzer')}
                </span>
              ),
            },
            {
              key: 'actions',
              header: '',
              render: (item) => (
                <div onClick={(e) => e.stopPropagation()}>
                  <ActionButtons
                    onEdit={canUpdate ? () => openEdit(item) : undefined}
                    onDelete={
                      canDelete ? () => setDeleteTarget(item) : undefined
                    }
                  />
                </div>
              ),
            },
          ]}
          data={pg.paged}
          loading={loading}
          emptyMessage={t('inventory.noItemsFound', 'Kei Items gfunde')}
          onRowClick={(item) => setDetailItem(item)}
          searchValue={search}
          onSearchChange={setSearch}
          searchPlaceholder={t('inventory.searchItems', 'Items sueche\u2026')}
          filters={[
            {
              label: t('inventory.allCategories', 'Alli'),
              value: 'cat-all',
              active: catFilter === 'All',
              onClick: () => setCatFilter('All'),
            },
            ...CATEGORIES.map((c) => ({
              label: (
                <>
                  <span
                    className="dot"
                    style={{ background: CATEGORY_COLORS[c] }}
                  />
                  {c === 'Tool'
                    ? t('inventory.tool', 'W\u00e4rchzeug')
                    : c === 'Item'
                      ? t('inventory.item', 'Item')
                      : t('inventory.material', 'Material')}
                </>
              ),
              value: `cat-${c}`,
              active: catFilter === c,
              onClick: () => setCatFilter(c),
            })),
          ]}
          toolbar={
            <>
              <Select
                size="sm"
                data={[
                  {
                    value: 'All',
                    label: t('inventory.allStatuses', 'Alli Status'),
                  },
                  ...STATUSES.map((s) => ({
                    value: s,
                    label: t(`inventory.status_${s}`, STATUS_CONFIG[s].label),
                  })),
                ]}
                value={statusFilter}
                onChange={(v) =>
                  setStatusFilter((v ?? 'All') as InventoryStatus | 'All')
                }
                style={{ width: 140 }}
              />
              <Seg
                options={[
                  { value: 'table', label: '\u2261 ' + t('members.tableView') },
                  { value: 'cards', label: '\u229e ' + t('members.cardsView') },
                ]}
                value={view}
                onChange={(v) => setView(v as 'table' | 'cards')}
              />
            </>
          }
          page={pg.page}
          perPage={pg.perPage}
          total={pg.total}
          totalPages={pg.totalPages}
          onPageChange={pg.goPage}
          onPerPageChange={pg.setPerPage}
          getRowKey={(item) => item.id}
        />
      ) : (
        <Paper withBorder shadow="sm" radius="lg">
          <div
            style={{
              padding: '14px 16px',
              borderBottom: '1px solid var(--mantine-color-gray-3)',
              display: 'flex',
              gap: 10,
              flexWrap: 'wrap',
              alignItems: 'center',
            }}
          >
            <div style={{ position: 'relative', flex: '1 1 220px' }}>
              <IconSearch
                size={16}
                style={{
                  position: 'absolute',
                  left: 11,
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: 'var(--mantine-color-gray-5)',
                }}
              />
              <TextInput
                size="sm"
                style={{ paddingLeft: 34 }}
                placeholder={t('inventory.searchItems', 'Items sueche\u2026')}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              <button
                className={`chip${catFilter === 'All' ? ' on' : ''}`}
                onClick={() => setCatFilter('All')}
              >
                {t('inventory.allCategories', 'Alli')}
              </button>
              {CATEGORIES.map((c) => (
                <button
                  key={c}
                  className={`chip${catFilter === c ? ' on' : ''}`}
                  onClick={() => setCatFilter(c)}
                >
                  <span
                    className="dot"
                    style={{ background: CATEGORY_COLORS[c] }}
                  />
                  {c === 'Tool'
                    ? t('inventory.tool', 'W\u00e4rchzeug')
                    : c === 'Item'
                      ? t('inventory.item', 'Item')
                      : t('inventory.material', 'Material')}
                </button>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <Select
                size="sm"
                data={[
                  {
                    value: 'All',
                    label: t('inventory.allStatuses', 'Alli Status'),
                  },
                  ...STATUSES.map((s) => ({
                    value: s,
                    label: t(`inventory.status_${s}`, STATUS_CONFIG[s].label),
                  })),
                ]}
                value={statusFilter}
                onChange={(v) =>
                  setStatusFilter((v ?? 'All') as InventoryStatus | 'All')
                }
                style={{ width: 140 }}
              />
              <Seg
                options={[
                  { value: 'table', label: '\u2261 ' + t('members.tableView') },
                  { value: 'cards', label: '\u229e ' + t('members.cardsView') },
                ]}
                value={view}
                onChange={(v) => setView(v as 'table' | 'cards')}
              />
            </div>
          </div>
          {loading ? (
            <LoadingSpinner compact message="Loading\u2026" />
          ) : pg.paged.length === 0 ? (
            <EmptyState
              title={t('inventory.noItemsFound', 'Kei Items gfunde')}
            />
          ) : (
            <>
              <div style={{ padding: 16 }}>
                <CardGrid>
                  {pg.paged.map((item) => {
                    const sc = STATUS_CONFIG[item.status]
                    const cc = CATEGORY_COLORS[item.category]
                    return (
                      <CardItem
                        key={item.id}
                        colorBar={cc}
                        icon={
                          <div
                            style={{
                              width: 36,
                              height: 36,
                              borderRadius: 8,
                              background: cc + '22',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              color: cc,
                            }}
                          >
                            {CATEGORY_ICONS[item.category]}
                          </div>
                        }
                        title={item.name}
                        subtitle={
                          item.ownerName ??
                          t('inventory.noOwner', 'Kei Bsitzer')
                        }
                        onClick={() => setDetailItem(item)}
                        footer={
                          <div
                            style={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                            }}
                          >
                            <Badge
                              variant="light"
                              size="sm"
                              style={{
                                borderColor: sc.color + '44',
                                color: sc.color,
                                background: sc.color + '11',
                              }}
                            >
                              {sc.label}
                            </Badge>
                            <div onClick={(e) => e.stopPropagation()}>
                              <ActionButtons
                                onEdit={
                                  canUpdate ? () => openEdit(item) : undefined
                                }
                                onDelete={
                                  canDelete
                                    ? () => setDeleteTarget(item)
                                    : undefined
                                }
                              />
                            </div>
                          </div>
                        }
                      >
                        {item.description && (
                          <Text
                            size="sm"
                            c="dimmed"
                            style={{
                              marginBottom: 8,
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {item.description}
                          </Text>
                        )}
                      </CardItem>
                    )
                  })}
                </CardGrid>
              </div>
              <Pagination
                page={pg.page}
                perPage={pg.perPage}
                total={pg.total}
                totalPages={pg.totalPages}
                goPage={pg.goPage}
                setPerPage={pg.setPerPage}
              />
            </>
          )}
        </Paper>
      )}

      {detailItem && (
        <ItemDetailPanel
          item={detailItem}
          onClose={() => setDetailItem(null)}
          onEdit={() => {
            openEdit(detailItem)
            setDetailItem(null)
          }}
          currentUserId={currentUserId}
          currentUserName={currentUserName}
          onInstructionChange={handleInstructionChange}
        />
      )}

      <Modal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title={t('inventory.addInventoryItem', 'Inventar-Item hinzue')}
        footer={
          <>
            <Button variant="default" onClick={() => setAddOpen(false)}>
              {t('common.cancel', 'Abbreche')}
            </Button>
            <Button variant="filled" onClick={saveAdd}>
              {t('inventory.addItem', 'Item hinzue')}
            </Button>
          </>
        }
      >
        {itemForm}
      </Modal>
      <Modal
        open={!!editTarget}
        onClose={() => setEditTarget(null)}
        title={t('inventory.editItem', 'Item bearbeite')}
        subtitle={editTarget?.name}
        footer={
          <>
            <Button variant="default" onClick={() => setEditTarget(null)}>
              {t('common.cancel', 'Abbreche')}
            </Button>
            <Button variant="filled" onClick={saveEdit}>
              {t('common.saveChanges', 'Änderige speichere')}
            </Button>
          </>
        }
      >
        {itemForm}
      </Modal>
      <ConfirmModal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title={t('inventory.deleteItemTitle', '"{{name}}" lösche?', {
          name: deleteTarget?.name ?? '',
        })}
        body={t(
          'inventory.deleteItemBody',
          'Das Item und alli Instruktions-Datensätz wärded permanent entfernt.',
        )}
        onConfirm={confirmDelete}
      />
    </div>
  )
}
