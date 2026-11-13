import { IconPuzzle } from '@tabler/icons-react'
import { tr } from '@/lang'
import { lazyNamed } from '@/lazyNamed'
import { definePage, icon } from '../registry'

const MarketplaceTab = lazyNamed(() => import('@/screens/MarketplaceTab'), 'MarketplaceTab')

export default definePage('clubs', 40, () => ({
  id: 'plugins',
  label: tr('Plugin-Katalog', 'Plugin catalogue'),
  icon: icon(IconPuzzle),
  desc: tr(
    'Plugins bringen Module, die ohne neues Hubra-Release ausgeliefert und aktualisiert werden. Hier geprüfte und installierte Plugins erscheinen bei den Vereinen als normale Module unter Einstellungen › Module.',
    'Plugins bring modules that are shipped and updated without a new Hubra release. Plugins vetted and installed here show up for clubs as ordinary modules under Settings › Modules.',
  ),
  tabs: [
    { id: 'list', path: '/app/plugins', label: '', perm: 'plugins.manage', render: () => <MarketplaceTab /> },
  ],
}))
