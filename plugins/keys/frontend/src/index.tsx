import { registerPlugin } from '@hubra/plugin-sdk'
import { KeysScreen } from './KeysScreen'
import { MyKeysCard } from './MyKeysCard'
import translations from './translations.json'

registerPlugin({
  id: 'keys',
  routes: [
    {
      path: 'inventory/keys',
      module: 'inventory.keys',
      perm: 'keys.keys.read',
      component: KeysScreen,
    },
  ],
  slots: [{ slot: 'account.cards', module: 'inventory.keys', component: MyKeysCard }],
  translations,
})
