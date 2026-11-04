/** Where the record an entry is about has its own page, if it has one. */
export function recordPath(type: string | null, id: number | null): string | null {
  if (!type || id == null) return null
  switch (type.toLowerCase()) {
    case 'member':
      return `/app/members/${id}`
    case 'group':
      return `/app/groups/${id}`
    case 'transaction':
      return `/app/finance/transactions/${id}`
    case 'invoice':
      return `/app/finance/invoices/${id}`
    case 'function':
      return `/app/members/functions/${id}`
    case 'tier':
      return `/app/members/tiers/${id}`
    case 'post':
      return `/app/operations/posts/${id}`
    case 'inventoryitem':
      return `/app/inventory/${id}`
    default:
      return null
  }
}
