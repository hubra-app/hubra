import { describe, expect, it } from 'vitest'
import { parseLinks } from './widgets'

describe('parseLinks', () => {
  it('reads "label | url" lines and keeps only http(s) links', () => {
    expect(
      parseLinks(
        'Website | https://fc-demo.ch\nhttps://hubra.club\nBöse | javascript:alert(1)\n\nKalender | ftp://x',
      ),
    ).toEqual([
      { label: 'Website', url: 'https://fc-demo.ch' },
      { label: 'https://hubra.club', url: 'https://hubra.club' },
    ])
  })
})
