import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '@/test/render'
import type { DashboardWidget } from '@/api/dashboards'

const go = vi.fn()
vi.mock('@/context/AppContext', () => ({
  useAuth: () => ({ hasPermission: () => true, currentUser: { id: 'm1' } }),
  useNav: () => ({ go }),
}))
vi.mock('@/modules/useModules', () => ({
  useModules: () => ({ has: () => true, canUse: () => true, list: [], loaded: true }),
}))
vi.mock('@hubra/api-client', () => ({
  apiFetch: () => Promise.resolve({ items: [] }),
}))

const { WidgetBoard } = await import('./WidgetBoard')

const note = (id: string, config: Record<string, unknown>, more: Partial<DashboardWidget> = {}) =>
  ({ id, type: 'note', size: 's', config, ...more }) as DashboardWidget

function board(widgets: DashboardWidget[], editing = false, save = vi.fn()) {
  renderWithProviders(
    <WidgetBoard
      widgets={widgets}
      editing={editing}
      busy={false}
      save={save}
      picking={false}
      setPicking={() => {}}
      empty={<p>leer</p>}
    />,
  )
  return save
}

beforeEach(() => go.mockReset())

describe('WidgetBoard', () => {
  it('draws widgets on the shared grid in the shared card', () => {
    board([note('a', { title: 'Hinweise', text: 'Zeile eins\nZeile zwei' })])
    expect(screen.getByRole('region', { name: 'Widgets' })).toHaveClass('bnb-grid')
    expect(screen.getByRole('heading', { name: 'Hinweise' })).toBeInTheDocument()
    expect(screen.getByText(/Zeile eins/)).toHaveStyle({ whiteSpace: 'pre-wrap' })
    expect(screen.getByTestId('widget-note')).toHaveAttribute('data-h', 'auto')
  })

  it('leaves out a widget with nothing to show', () => {
    const cards = { id: 'p', type: 'plugins.cards', size: 'l', config: {} } as DashboardWidget
    board([cards, note('a', { title: 'Hinweise' })])
    expect(document.querySelectorAll('.bnb-grid-item')).toHaveLength(1)
    expect(screen.getByTestId('widget-note').closest('.bnb-grid-item')).toHaveStyle({
      gridRow: '1 / span 4',
    })
  })

  it('shows the empty state without widgets', () => {
    board([])
    expect(screen.getByText('leer')).toBeInTheDocument()
  })

  it('offers the grip in edit mode and saves spots with a removal', async () => {
    const save = board([note('a', {}), note('b', {}, { h: 3 })], true)
    expect(screen.getAllByRole('button', { name: 'Widget verschieben' })).toHaveLength(2)
    await userEvent.click(screen.getAllByRole('button', { name: 'Entfernen' })[0])
    expect(save).toHaveBeenCalledTimes(1)
    const [next] = save.mock.calls[0] as [DashboardWidget[]]
    expect(next).toHaveLength(1)
    expect(next[0]).toMatchObject({ id: 'b', h: 3, x: 4, y: 0, w: 4 })
  })

  it('moves a widget with the keyboard and keeps its content height', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const save = board([note('a', {}), note('b', {})], true)
    screen.getAllByRole('button', { name: 'Widget verschieben' })[1].focus()
    await userEvent.keyboard('{ArrowRight}')
    await vi.advanceTimersByTimeAsync(500)
    vi.useRealTimers()
    expect(save).toHaveBeenCalledTimes(1)
    const [next] = save.mock.calls[0] as [DashboardWidget[]]
    expect(next.find((w) => w.id === 'b')).toMatchObject({ x: 5, y: 0 })
    expect(next.find((w) => w.id === 'b')).not.toHaveProperty('h')
  })
})
