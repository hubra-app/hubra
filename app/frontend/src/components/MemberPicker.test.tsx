import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '@/test/render'
import type { Member } from '@/types'
import { MemberPicker } from './MemberPicker'

const anna = { id: '1', name: 'Anna Muster', tier: 'Aktiv' } as Member
const ben = { id: '2', name: 'Ben Beispiel', tier: 'Passiv' } as Member

const listMembers = vi.fn(async ({ search = '' }: { search?: string }) => {
  const members = [anna, ben].filter((m) => m.name.toLowerCase().includes(search.toLowerCase()))
  return { members, total: members.length }
})
const getMember = vi.fn(async (id: string) => [anna, ben].find((m) => m.id === id)!)

vi.mock('@/api/members', () => ({
  listMembers: (f: { search?: string }) => listMembers(f),
  getMember: (id: string) => getMember(id),
}))

describe('MemberPicker', () => {
  it('asks the server for what was typed and hands back the member', async () => {
    const onChange = vi.fn()
    renderWithProviders(<MemberPicker label="Mitglied" value={null} onChange={onChange} />)
    await userEvent.type(screen.getByRole('combobox', { name: 'Mitglied' }), 'ben')
    await waitFor(() =>
      expect(listMembers).toHaveBeenCalledWith(expect.objectContaining({ search: 'ben' })),
    )
    await userEvent.click(await screen.findByRole('option', { name: 'Ben Beispiel' }))
    expect(onChange).toHaveBeenCalledWith('2', ben)
  })

  it('shows the chosen member even when the server did not list them', async () => {
    listMembers.mockResolvedValueOnce({ members: [], total: 0 })
    renderWithProviders(<MemberPicker label="Mitglied" value="1" onChange={() => {}} />)
    await waitFor(() =>
      expect(screen.getByRole('combobox', { name: 'Mitglied' })).toHaveValue('Anna Muster'),
    )
  })
})
