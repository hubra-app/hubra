import { describe, expect, it } from 'vitest'
import { DASHBOARD_TEMPLATES, parseLinks, templateWidgets, type WidgetDef } from './widgets'

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

describe('templateWidgets', () => {
  it('keeps only the widgets this member may add', () => {
    const def = (type: string, perm?: string): WidgetDef => ({
      type,
      label: type,
      description: '',
      size: 's',
      perm,
      render: () => null,
    })
    const catalogue = [
      def('stat.openInvoices'),
      def('w:finance.invoices.ageing'),
      def('w:kasse.claims', 'kasse.claims.read'),
    ]
    const treasurer = DASHBOARD_TEMPLATES.find((tpl) => tpl.key === 'treasurer')!
    const got = templateWidgets(treasurer, catalogue, (d) => !d.perm)
    expect(got.map((x) => x.type)).toEqual(['stat.openInvoices', 'w:finance.invoices.ageing'])
    expect(got[1].w).toBe(6)
  })
})
