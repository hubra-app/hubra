import { IconLanguage } from '@tabler/icons-react'
import { tr } from '@/lang'
import { lazyNamed } from '@/lazyNamed'
import { definePage, icon } from '../registry'

const SettingsSection = lazyNamed(() => import('@/screens/platform/SettingsSection'), 'SettingsSection')
const PlatformTranslations = lazyNamed(() => import('@/screens/platform/Translations'), 'PlatformTranslations')

export default definePage('services', 70, () => ({
  id: 'translations',
  label: tr('Übersetzungen', 'Translations'),
  icon: icon(IconLanguage),
  desc: tr(
    'Die Texte der Apps in jeder Sprache, und was Vereine dazu vorschlagen.',
    'The texts of the apps in every language, and what clubs suggest for them.',
  ),
  tabs: [
    {
      id: 'all',
      path: '/app/platform/translations',
      label: tr('Texte', 'Texts'),
      perm: 'platform.settings',
      render: () => <PlatformTranslations />,
    },
    {
      id: 'settings',
      path: '/app/platform/translations/settings',
      label: tr('Einstellungen', 'Settings'),
      perm: 'platform.settings',
      render: () => <SettingsSection section="translate" />,
    },
  ],
}))
