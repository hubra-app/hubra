import { Button } from '@mantine/core'
import { useT } from '@/locales/i18n'
import { useNav } from '@/context/AppContext'

export function InventoryItemDetailScreen() {
  const { t } = useT()
  const { go } = useNav()
  return (
    <div style={{ padding: 40, textAlign: 'center', color: 'var(--hb-text-3)' }}>
      <div style={{ fontSize: 'var(--mantine-font-size-sm)' }}>
        {t('inventory.noItemSelected', 'Kein Gegenstand ausgewählt.')}
      </div>
      <Button
        variant="filled"
        style={{ marginTop: 16 }}
        onClick={() => go('/app/inventory')}
      >
        {t('inventory.backToInventory', 'Zurück zum Inventar')}
      </Button>
    </div>
  )
}
