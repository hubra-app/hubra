import { useCallback } from 'react'
import { useAuth } from '@/context/AppContext'
import type { InventoryItem } from '@/types'

export interface ItemAccess {
  canEdit: boolean
  canDelete: boolean
  canInstruct: boolean
  /** Change the owner, the responsible person and the visibility. */
  canHandOn: boolean
}

/**
 * What the current member may do with an item: the club-wide inventory
 * rights, or being its owner or responsible person. The API checks the same
 * rules (inventory/services.py ITEM_ACTIONS); this only hides the buttons.
 */
export function useItemAccess(): (item: InventoryItem) => ItemAccess {
  const { currentUser, hasPermission } = useAuth()
  const me = currentUser ? Number(currentUser.id) : null
  const update = hasPermission('inventory.items.update')
  const del = hasPermission('inventory.items.delete')
  const instruct = hasPermission('inventory.items.manage_instructions')
  return useCallback(
    (item: InventoryItem) => {
      const isOwner = me !== null && item.ownerId === me
      const isResponsible = me !== null && item.responsibleId === me
      return {
        canEdit: update || isOwner || isResponsible,
        canDelete: del || isOwner,
        canInstruct: instruct || isOwner || isResponsible,
        canHandOn: update || isOwner,
      }
    },
    [me, update, del, instruct],
  )
}
