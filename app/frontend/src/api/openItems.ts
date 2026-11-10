import { apiFetch } from '@hubra/api-client'

/** Something a member owes that is not on an invoice yet. */
export interface OpenItem {
  id: number
  member_id: number
  member_name: string | null
  amount: number
  text: string
  /** YYYY-MM-DD: the day it happened. */
  day: string
  /** The module that handed it over ("kasse", "booking"; "finance" by hand). */
  source: string
  source_ref: string | null
  category_id: number | null
  invoice_id: number | null
}

export interface OpenItems {
  items: OpenItem[]
  /** Finance setting collect_items. */
  cycle: 'off' | 'monthly' | 'quarterly'
  min_amount: number
}

export function listOpenItems(signal?: AbortSignal): Promise<OpenItems> {
  return apiFetch('/app/finance/open-items', { signal })
}

export function addOpenItem(input: { member_id: number; amount: number; text: string; day?: string }): Promise<OpenItem> {
  return apiFetch('/app/finance/open-items', { method: 'POST', body: JSON.stringify(input) })
}

export function deleteOpenItem(id: number): Promise<void> {
  return apiFetch(`/app/finance/open-items/${id}`, { method: 'DELETE' })
}

/** Bill now: one invoice per member with a positive total. */
export function billOpenItems(): Promise<{ invoices: number[] }> {
  return apiFetch('/app/finance/open-items/bill', { method: 'POST', body: '{}' })
}
