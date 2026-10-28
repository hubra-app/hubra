import { apiFetch } from '@hubra/api-client'

export type BudgetKind = 'income' | 'expense'

export interface BudgetLine {
  id: number
  categoryId: number
  categoryName: string | null
  categoryColor: string | null
  kind: BudgetKind
  planned: string
  actual: string
  note: string | null
}

export interface Budget {
  id: number
  year: number
  name: string
  notes: string | null
  approved: boolean
  totals: Record<BudgetKind, { planned: string; actual: string }>
  plannedResult: string
  actualResult: string
  lines?: BudgetLine[]
  unplanned?: {
    categoryId: number
    categoryName: string | null
    kind: BudgetKind
    actual: string
  }[]
}

export interface BudgetLineInput {
  category_id: number
  kind: BudgetKind
  planned: number
  note?: string | null
}

export const listBudgets = () => apiFetch<Budget[]>('/budgets/')
export const getBudget = (id: number) => apiFetch<Budget>(`/budgets/${id}`)

export const createBudget = (input: { name: string; year: number }) =>
  apiFetch<Budget>('/budgets/', { method: 'POST', body: JSON.stringify(input) })

export const updateBudget = (
  id: number,
  input: { name?: string; year?: number; notes?: string; approved?: boolean },
) =>
  apiFetch<Budget>(`/budgets/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(input),
  })

export const deleteBudget = (id: number) => apiFetch<void>(`/budgets/${id}`, { method: 'DELETE' })

export const saveBudgetLines = (id: number, lines: BudgetLineInput[]) =>
  apiFetch<Budget>(`/budgets/${id}/lines`, {
    method: 'PUT',
    body: JSON.stringify({ lines }),
  })

export const copyBudget = (id: number, year?: number) =>
  apiFetch<Budget>(`/budgets/${id}/copy`, {
    method: 'POST',
    body: JSON.stringify({ year }),
  })
