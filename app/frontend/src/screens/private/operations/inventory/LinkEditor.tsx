import { Button, TextInput } from '@mantine/core'
import { useT } from '@/locales/i18n'
import { IconPlus, IconX } from '@tabler/icons-react'
import type { InventoryLink } from '@/types'

export function LinkEditor({
  links,
  onChange,
}: {
  links: InventoryLink[]
  onChange: (l: InventoryLink[]) => void
}) {
  const { t } = useT()
  const add = () => onChange([...links, { label: '', url: '' }])
  const remove = (i: number) => onChange(links.filter((_, idx) => idx !== i))
  const update = (i: number, field: 'label' | 'url', val: string) =>
    onChange(links.map((l, idx) => (idx === i ? { ...l, [field]: val } : l)))

  return (
    <div>
      {links.map((l, i) => (
        <div
          key={l.url + i}
          className="grid-3"
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr auto',
            gap: 6,
            marginBottom: 6,
          }}
        >
          <TextInput
            placeholder={t('inventory.linkLabel', 'Bezeichnung')}
            value={l.label}
            onChange={(e) => update(i, 'label', e.target.value)}
            style={{ height: 34, fontSize: 'var(--mantine-font-size-xs)' }}
          />
          <TextInput
            placeholder="https://…"
            value={l.url}
            onChange={(e) => update(i, 'url', e.target.value)}
            style={{ height: 34, fontSize: 'var(--mantine-font-size-xs)' }}
          />
          <Button
            size="sm"
            variant="subtle"
            style={{ color: '#ff4d3d' }}
            onClick={() => remove(i)}
          >
            <IconX size={16} />
          </Button>
        </div>
      ))}
      <Button
        size="sm"
        variant="subtle"
        onClick={add}
        style={{ fontSize: 'var(--mantine-font-size-xs)', color: '#2596be' }}
      >
        <IconPlus size={16} />
        {t('inventory.addLink', 'Link hinzufügen')}
      </Button>
    </div>
  )
}
