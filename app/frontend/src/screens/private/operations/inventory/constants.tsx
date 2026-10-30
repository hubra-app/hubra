import {
  IconTool,
  IconBox,
  IconStack2,
  IconCircleCheck,
  IconAlertCircle,
  IconClock,
  IconArchive,
} from '@tabler/icons-react'
import type { InventoryCategory, InventoryStatus } from '@/types'

export const CATEGORIES: InventoryCategory[] = ['Tool', 'Item', 'Material']
export const STATUSES: InventoryStatus[] = [
  'available',
  'in_use',
  'maintenance',
  'broken',
  'archived',
]

export const CATEGORY_ICONS: Record<InventoryCategory, React.ReactNode> = {
  Tool: <IconTool size={16} />,
  Item: <IconBox size={16} />,
  Material: <IconStack2 size={16} />,
}

export const CATEGORY_COLORS: Record<InventoryCategory, string> = {
  Tool: '#2596be',
  Item: '#1f9d57',
  Material: '#c2870f',
}

export const STATUS_CONFIG: Record<
  InventoryStatus,
  { label: string; color: string; icon: React.ReactNode }
> = {
  available: {
    label: 'Verfügbar',
    color: '#1f9d57',
    icon: <IconCircleCheck size={12} />,
  },
  in_use: {
    label: 'In Gebrauch',
    color: '#2596be',
    icon: <IconClock size={12} />,
  },
  maintenance: {
    label: 'Wartung',
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
    color: 'var(--hb-text-3)',
    icon: <IconArchive size={12} />,
  },
  checked_out: {
    label: 'Ausgeliehen',
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
    color: 'var(--hb-text-3)',
    icon: <IconArchive size={12} />,
  },
}
