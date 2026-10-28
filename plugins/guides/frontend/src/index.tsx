import { registerPlugin } from '@hubra/plugin-sdk'
import { GuideSection } from './GuideSection'
import translations from './translations.json'

registerPlugin({
  id: 'guides',
  slots: [{ slot: 'inventory.item', module: 'inventory.guides', component: GuideSection }],
  translations,
})
