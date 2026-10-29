import { describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '@/test/render'
import { DataTable } from './data'

const rows = [
  { id: 1, name: 'Anna' },
  { id: 2, name: 'Ben' },
]
const columns = [{ key: 'name', header: 'Name', render: (r: (typeof rows)[number]) => r.name }]

describe('DataTable', () => {
  it('shows one row per item', () => {
    renderWithProviders(<DataTable columns={columns} data={rows} getRowKey={(r) => r.id} />)
    expect(screen.getByText('Anna')).toBeInTheDocument()
    expect(screen.getByText('Ben')).toBeInTheDocument()
  })

  it('opens a row with a click, Enter or Space', async () => {
    const onRowClick = vi.fn()
    const user = userEvent.setup()
    renderWithProviders(
      <DataTable columns={columns} data={rows} getRowKey={(r) => r.id} onRowClick={onRowClick} />,
    )
    await user.click(screen.getByText('Anna'))
    expect(onRowClick).toHaveBeenLastCalledWith(rows[0])

    const row = screen.getByText('Ben').closest('tr')!
    row.focus()
    await user.keyboard('{Enter}')
    expect(onRowClick).toHaveBeenLastCalledWith(rows[1])
    await user.keyboard(' ')
    expect(onRowClick).toHaveBeenCalledTimes(3)
  })

  it('leaves rows out of the tab order when they do nothing', () => {
    renderWithProviders(<DataTable columns={columns} data={rows} getRowKey={(r) => r.id} />)
    expect(screen.getByText('Anna').closest('tr')).not.toHaveAttribute('tabindex')
  })
})
