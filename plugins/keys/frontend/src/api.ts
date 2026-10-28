import { apiFetch } from '@hubra/plugin-sdk'

export type KeyKind = 'key' | 'card' | 'fob'
export type KeyStatus = 'available' | 'issued' | 'lost' | 'retired'

export interface KeyHandover {
  id: number
  action: 'issue' | 'return' | 'lost' | 'found' | 'retire'
  memberId: number | null
  memberName: string | null
  byName: string | null
  note: string | null
  at: string
}

export interface ClubKey {
  id: number
  label: string
  number: string | null
  kind: KeyKind
  opens: string | null
  status: KeyStatus
  holderId: number | null
  holderName: string | null
  depositChf: string | null
  codeId: number | null
  notes: string | null
  updatedAt: string | null
  history?: KeyHandover[]
}

export interface KeyInput {
  label?: string
  number?: string | null
  kind?: KeyKind
  opens?: string | null
  deposit_chf?: number | null
  notes?: string | null
}

export const listKeys = () => apiFetch<ClubKey[]>('/keys/')
export const listMyKeys = () => apiFetch<ClubKey[]>('/keys/mine')
export const getKey = (id: number) => apiFetch<ClubKey>(`/keys/${id}`)

export const createKey = (input: KeyInput) =>
  apiFetch<ClubKey>('/keys/', { method: 'POST', body: JSON.stringify(input) })

export const updateKey = (id: number, input: KeyInput) =>
  apiFetch<ClubKey>(`/keys/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(input),
  })

export const deleteKey = (id: number) => apiFetch<void>(`/keys/${id}`, { method: 'DELETE' })

export const issueKey = (id: number, memberId: number, note?: string) =>
  apiFetch<ClubKey>(`/keys/${id}/issue`, {
    method: 'POST',
    body: JSON.stringify({ member_id: memberId, note }),
  })

export type KeyAction = 'return' | 'lost' | 'found' | 'retire'

export const keyAction = (id: number, action: KeyAction, note?: string) =>
  apiFetch<ClubKey>(`/keys/${id}/${action}`, {
    method: 'POST',
    body: JSON.stringify({ note }),
  })
