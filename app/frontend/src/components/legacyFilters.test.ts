import { describe, expect, it, vi } from 'vitest'
import { legacyFilterGroups } from './legacyFilters'

describe('legacyFilterGroups', () => {
  it('turns a row of old chips into one panel group', () => {
    const paid = vi.fn()
    const [g] = legacyFilterGroups([
      { label: 'Alle', value: 'all', active: false, onClick: vi.fn() },
      { label: 'Bezahlt', value: 'paid', active: true, onClick: paid },
    ])
    expect(g.value).toBe('paid')
    expect(g.defaultValue).toBe('all')
    g.onChange('paid')
    expect(paid).toHaveBeenCalled()
  })

  it('keeps select slots as selects', () => {
    const change = vi.fn()
    const [g] = legacyFilterGroups(undefined, [
      {
        label: 'Typ',
        type: 'select',
        selectValue: 'b',
        selectOptions: [
          { value: 'a', label: 'A' },
          { value: 'b', label: 'B' },
        ],
        onSelectChange: change,
      },
    ])
    expect(g.kind).toBe('select')
    expect(g.value).toBe('b')
    g.onChange('a')
    expect(change).toHaveBeenCalledWith('a')
  })
})
