import { categoryColors } from '@hubra/ui'
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
  Tool: categoryColors.blue,
  Item: categoryColors.green,
  Material: categoryColors.orange,
}

export const STATUS_CONFIG: Record<
  InventoryStatus,
  { label: string; color: string; icon: React.ReactNode }
> = {
  available: {
    label: 'Verfügbar',
    color: 'var(--mantine-color-green-text)',
    icon: <IconCircleCheck size={12} />,
  },
  in_use: {
    label: 'In Gebrauch',
    color: 'var(--mantine-color-acc-text)',
    icon: <IconClock size={12} />,
  },
  maintenance: {
    label: 'Wartung',
    color: 'var(--mantine-color-orange-text)',
    icon: <IconAlertCircle size={12} />,
  },
  broken: {
    label: 'Defekt',
    color: 'var(--mantine-color-red-text)',
    icon: <IconAlertCircle size={12} />,
  },
  archived: {
    label: 'Archiviert',
    color: 'var(--hb-text-3)',
    icon: <IconArchive size={12} />,
  },
  checked_out: {
    label: 'Ausgeliehen',
    color: 'var(--mantine-color-acc-text)',
    icon: <IconClock size={12} />,
  },
  pending: {
    label: 'Ausstehend',
    color: 'var(--mantine-color-orange-text)',
    icon: <IconAlertCircle size={12} />,
  },
  lost: {
    label: 'Verloren',
    color: 'var(--mantine-color-red-text)',
    icon: <IconAlertCircle size={12} />,
  },
  retired: {
    label: 'Ausgemustert',
    color: 'var(--hb-text-3)',
    icon: <IconArchive size={12} />,
  },
}
