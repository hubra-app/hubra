import { describe, expect, it, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '@/test/render'

const state = vi.hoisted(() => ({ modules: new Set<string>(), perms: new Set<string>() }))

vi.mock('@/modules/useModules', () => ({
  useModules: () => ({ has: (code: string) => state.modules.has(code), list: [], loaded: true }),
}))
vi.mock('@/context/AppContext', () => ({
  useAuth: () => ({ hasPermission: (p: string) => state.perms.has(p) }),
}))

const { registerPlugin } = await import('./store')
const { PluginSlot } = await import('./slot')
const { PluginBoundary } = await import('./boundary')

function Broken(): never {
  throw new Error('plugin bug')
}

beforeEach(() => {
  state.modules = new Set(['keys'])
  state.perms = new Set()
  vi.spyOn(console, 'error').mockImplementation(() => {})
})

describe('PluginBoundary', () => {
  it('shows a notice instead of a screen that throws', () => {
    renderWithProviders(
      <PluginBoundary plugin="broken" notice>
        <Broken />
      </PluginBoundary>,
    )
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })

  it('renders nothing for a slot entry that throws', () => {
    renderWithProviders(
      <>
        <p>before</p>
        <PluginBoundary plugin="broken">
          <Broken />
        </PluginBoundary>
      </>,
    )
    expect(screen.getByText('before')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})

describe('PluginSlot', () => {
  it('renders entries in order and keeps going past one that throws', () => {
    registerPlugin({
      id: 'slot-test',
      slots: [
        { slot: 'account.cards', module: 'keys', order: 2, component: () => <p>second</p> },
        { slot: 'account.cards', module: 'keys', order: 1, component: () => <p>first</p> },
        { slot: 'account.cards', module: 'keys', order: 3, component: Broken },
      ],
    })
    renderWithProviders(<PluginSlot name="account.cards" />)
    const texts = screen.getAllByText(/first|second/).map((e) => e.textContent)
    expect(texts).toEqual(['first', 'second'])
  })

  it('leaves out entries whose module is off or whose permission is missing', () => {
    registerPlugin({
      id: 'gate-test',
      slots: [
        { slot: 'inventory.item', module: 'off', component: () => <p>module off</p> },
        { slot: 'inventory.item', module: 'keys', perm: 'keys.read', component: () => <p>needs perm</p> },
      ],
    })
    renderWithProviders(<PluginSlot name="inventory.item" props={{ itemId: 1 }} />)
    expect(screen.queryByText('module off')).not.toBeInTheDocument()
    expect(screen.queryByText('needs perm')).not.toBeInTheDocument()
  })
})
