import { apiFetch } from '@hubra/api-client'

/** One text as the editor lists it (GET /i18n/<locale>?list=1). */
export interface TranslationRow {
  key: string
  value: string
  default_value: string | null
  needs_attention: boolean
  is_missing: boolean
  alias_for: string | null
  updated_at: string | null
}

export interface TranslationRequest {
  id: number
  tenantId: number | null
  tenantName: string | null
  locale: string
  key: string
  currentValue: string | null
  proposedValue: string
  note: string | null
  status: 'pending' | 'accepted' | 'rejected'
  decisionNote: string | null
  decidedAt: string | null
  createdAt: string | null
  /** The text now; it may have changed since the suggestion. */
  liveValue: string | null
}

export function listTranslations(locale: string) {
  return apiFetch<TranslationRow[]>(`/i18n/${locale}?list=1`)
}

export function saveTranslation(locale: string, key: string, value: string) {
  return apiFetch(`/i18n/${locale}`, {
    method: 'POST',
    body: JSON.stringify({ key, value }),
  })
}

export function listTranslationRequests(status?: 'pending' | 'accepted' | 'rejected') {
  return apiFetch<TranslationRequest[]>(
    `/manager/platform/translation-requests${status ? `?status=${status}` : ''}`,
  )
}

export function decideTranslationRequest(
  id: number,
  accept: boolean,
  opts: { value?: string; note?: string } = {},
) {
  return apiFetch<TranslationRequest>(`/manager/platform/translation-requests/${id}`, {
    method: 'POST',
    body: JSON.stringify({ accept, ...opts }),
  })
}
