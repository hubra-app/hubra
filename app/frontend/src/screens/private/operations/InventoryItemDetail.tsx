import { Button } from '@mantine/core'
import { useT } from '@/locales/i18n'
import { useNav } from '@/context/AppContext'

export function InventoryItemDetailScreen() {
  const { t } = useT()
  const { go } = useNav()
  return (
    <div style={{ padding: 40, textAlign: 'center', color: '#99a2ac' }}>
      <div style={{ fontSize: 'var(--mantine-font-size-sm)' }}>
        {t('inventory.noItemSelected', 'Kei Item usgwehlt.')}
      </div>
      <Button
        variant="filled"
        style={{ marginTop: 16 }}
        onClick={() => go('/app/inventory')}
      >
        {t('inventory.backToInventory', 'Zrugg zum Inventar')}
      </Button>
    </div>
  )
}
