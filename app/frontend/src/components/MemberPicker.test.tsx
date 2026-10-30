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

  it('lists everyone when opened on "nobody", not only matches for that label', async () => {
    renderWithProviders(
      <MemberPicker
        label="Eigentümer"
        noneLabel="Keine Eigentümer:in"
        value={null}
        onChange={() => {}}
      />,
    )
    const box = screen.getByRole('combobox', { name: 'Eigentümer' })
    await waitFor(() => expect(box).toHaveValue('Keine Eigentümer:in'))
    // Let the debounced search for the shown text settle first.
    await new Promise((r) => setTimeout(r, 400))
    await userEvent.click(box)
    expect(await screen.findByRole('option', { name: 'Anna Muster' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Ben Beispiel' })).toBeInTheDocument()
  })

  it('lists everyone when opened on a chosen member', async () => {
    renderWithProviders(<MemberPicker label="Mitglied" value="1" onChange={() => {}} />)
    const box = screen.getByRole('combobox', { name: 'Mitglied' })
    await waitFor(() => expect(box).toHaveValue('Anna Muster'))
    await new Promise((r) => setTimeout(r, 400))
    await userEvent.click(box)
    expect(await screen.findByRole('option', { name: 'Ben Beispiel' })).toBeInTheDocument()
  })
})
