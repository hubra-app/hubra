import { IconBuildingCommunity } from '@tabler/icons-react'
import { tr } from '@/lang'
import { lazyNamed } from '@/lazyNamed'
import { definePage, icon } from '../registry'

const TenantsTab = lazyNamed(() => import('@/screens/TenantsTab'), 'TenantsTab')
const TenantRequestsTab = lazyNamed(() => import('@/screens/TenantRequestsTab'), 'TenantRequestsTab')
const SettingsSection = lazyNamed(() => import('@/screens/platform/SettingsSection'), 'SettingsSection')
const PlatformPlans = lazyNamed(() => import('@/screens/platform/Plans'), 'PlatformPlans')
const EarlyAccess = lazyNamed(() => import('@/screens/platform/EarlyAccess'), 'EarlyAccess')

export default definePage('clubs', 20, () => ({
  id: 'tenants',
  label: tr('Alle Vereine', 'All clubs'),
  icon: icon(IconBuildingCommunity),
  desc: tr('Alle Vereine auf dieser Hubra-Plattform.', 'Every club on this Hubra platform.'),
  tabs: [
    {
      id: 'list',
      path: '/app/tenants',
      label: tr('Vereine', 'Clubs'),
      perm: 'tenants.read',
      render: () => <TenantsTab />,
    },
    {
      id: 'requests',
      path: '/app/tenants/requests',
      label: tr('Anfragen', 'Requests'),
      perm: 'requests.read.all',
      desc: tr(
        'Neue Vereine, die Leute auf der Anmeldeseite beantragt haben. Hier prüfst du sie und gibst sie frei.',
        'New clubs people asked for on the sign-in site. Review and approve them here.',
      ),
      render: () => <TenantRequestsTab />,
    },
    {
      id: 'plans',
      path: '/app/tenants/plans',
      label: tr('Tarife & Preise', 'Plans & prices'),
      perm: 'platform.settings',
      desc: tr(
        'Tarife mit Preisen, Limits und Leistungen, und Listenpreise für Zusatzmodule. Was öffentlich ist, zeigt die Website. Eigenen Preis, Rabatt und Sponsor für einen Verein setzt du auf seiner Seite.',
        'Plans with prices, limits and features, and list prices for add-ons. What is public shows on the website. A club’s own price, discount and sponsor are set on its page.',
      ),
      render: () => <PlatformPlans />,
    },
    {
      id: 'early-access',
      path: '/app/tenants/early-access',
      label: tr('Früher Zugang', 'Early access'),
      perm: 'platform.settings',
      desc: tr(
        'Neue Funktionen zuerst für ausgewählte Vereine einschalten.',
        'Switch new features on for chosen clubs first.',
      ),
      render: () => <EarlyAccess />,
    },
    {
      id: 'settings',
      path: '/app/tenants/settings',
      label: tr('Einstellungen', 'Settings'),
      perm: 'platform.settings',
      render: () => <SettingsSection section="limits" />,
    },
  ],
}))
