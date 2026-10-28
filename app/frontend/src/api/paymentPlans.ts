import { apiFetch } from '@hubra/api-client'

export type PlanInterval = 'yearly' | 'half_yearly' | 'quarterly' | 'monthly'

export interface PaymentPlan {
  id: number
  tier_id: number
  name: string
  interval: PlanInterval
  surcharge_pct: number
  visible: boolean
  amount?: number
}

export interface PlanInput {
  name?: string
  interval?: PlanInterval
  surcharge_pct?: number
  visible?: boolean
}

export interface PlanOptions {
  tier: {
    id: number
    name: string
    billing_cycle: string | null
    amount: number
  } | null
  current_plan_id: number | null
  plans: PaymentPlan[]
}

export const listPlans = (tierId: string | number) =>
  apiFetch<PaymentPlan[]>(`/tiers/${tierId}/plans`)

export const createPlan = (tierId: string | number, input: PlanInput) =>
  apiFetch<PaymentPlan>(`/tiers/${tierId}/plans`, {
    method: 'POST',
    body: JSON.stringify(input),
  })

export const updatePlan = (planId: number, input: PlanInput) =>
  apiFetch<PaymentPlan>(`/tiers/plans/${planId}`, {
    method: 'PATCH',
    body: JSON.stringify(input),
  })

export const deletePlan = (planId: number) =>
  apiFetch<void>(`/tiers/plans/${planId}`, { method: 'DELETE' })

export const getMyPlanOptions = () => apiFetch<PlanOptions>('/tiers/my-plan')

export const chooseMyPlan = (planId: number | null) =>
  apiFetch<PlanOptions>('/tiers/my-plan', {
    method: 'PUT',
    body: JSON.stringify({ plan_id: planId }),
  })
