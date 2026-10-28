import { apiFetch } from '@hubra/plugin-sdk'

export interface Guide {
  itemId: number
  itemName: string
  guide: string | null
  guideUrl: string | null
  instructionRequired: boolean
}

export const getGuide = (itemId: number) => apiFetch<Guide>(`/guides/${itemId}`)

export const saveGuide = (
  itemId: number,
  input: { guide: string | null; guideUrl: string | null },
) =>
  apiFetch<Guide>(`/guides/${itemId}`, {
    method: 'PUT',
    body: JSON.stringify({ guide: input.guide, guide_url: input.guideUrl }),
  })
