import { IconShieldCheck } from '@tabler/icons-react'
import { tr } from '@/lang'
import { lazyNamed } from '@/lazyNamed'
import { definePage, icon } from '../registry'

const GlobalAuditTab = lazyNamed(() => import('@/screens/GlobalAuditTab'), 'GlobalAuditTab')
const SupportSessionsTab = lazyNamed(() => import('@/screens/SupportSessionsTab'), 'SupportSessionsTab')

export default definePage('access', 30, () => ({
  id: 'audit',
  label: tr('Audit-Log', 'Audit log'),
  icon: icon(IconShieldCheck),
  desc: tr('Wer auf der Plattform was getan hat.', 'Who did what on the platform.'),
  tabs: [
    {
      id: 'changes',
      path: '/app/audit',
      label: tr('Änderungen', 'Changes'),
      perm: 'audit.read',
      desc: tr(
        'Alle Änderungen auf der Plattform und in allen Vereinen, neueste zuerst. Suchen, filtern und als CSV exportieren.',
        'Every change on the platform and in every club, newest first. Search, filter and export as CSV.',
      ),
      render: () => <GlobalAuditTab />,
    },
    {
      id: 'support',
      path: '/app/support',
      label: tr('Support-Zugriffe', 'Support access'),
      perm: 'audit.read',
      desc: tr(
        'Wann Plattform-Admins einen Verein als eines seiner Mitglieder geöffnet haben: wer, warum, wie lange. Laufende Sitzungen lassen sich hier beenden.',
        'When platform admins opened a club as one of its members: who, why and for how long. Running sessions can be ended here.',
      ),
      render: () => <SupportSessionsTab />,
    },
  ],
}))
