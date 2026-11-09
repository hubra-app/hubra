import { apiFetch } from '@hubra/api-client'

/** exempt: no fee · amount: own yearly fee · percent: reduction in per cent */
export type FeeAdjustmentKind = 'exempt' | 'amount' | 'percent'

export interface FeeAdjustment {
  id: number
  member_id: number
  kind: FeeAdjustmentKind
  amount_chf: number | null
  percent: number | null
  reason: string
  valid_until: string | null
  remind_days: number
  reminder_sent_at: string | null
  confirmed_at: string | null
  confirmation_note: string | null
  active: boolean
  ended: boolean
  awaiting_confirmation: boolean
  created_at: string | null
  updated_at: string | null
  member_name?: string
}

/** A member's fee for one of their billing periods, with and without their
 *  own arrangement. Amounts are null when their tier bills nothing. */
export interface MemberFee {
  adjustment: FeeAdjustment | null
  billing_cycle: string | null
  standard_amount: number | null
  amount: number | null
}

export interface FeeAdjustmentInput {
  kind: FeeAdjustmentKind
  amount_chf?: number | null
  percent?: number | null
  reason: string
  valid_until?: string | null
  remind_days?: number
}

export const listFeeAdjustments = () =>
  apiFetch<FeeAdjustment[]>('/app/tiers/fee-adjustments')

export const getMemberFee = (memberId: string | number) =>
  apiFetch<MemberFee>(`/app/tiers/members/${memberId}/fee`)

export const setMemberFee = (memberId: string | number, input: FeeAdjustmentInput) =>
  apiFetch<MemberFee>(`/app/tiers/members/${memberId}/fee`, {
    method: 'PUT',
    body: JSON.stringify(input),
  })

export const removeMemberFee = (memberId: string | number) =>
  apiFetch<MemberFee>(`/app/tiers/members/${memberId}/fee`, { method: 'DELETE' })

export const getMyFee = () => apiFetch<MemberFee>('/app/tiers/my-fee')

export const confirmMyFee = (note: string) =>
  apiFetch<MemberFee>('/app/tiers/my-fee/confirm', {
    method: 'POST',
    body: JSON.stringify({ note }),
  })
