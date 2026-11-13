import { IconSparkles } from '@tabler/icons-react'
import { tr } from '@/lang'
import { lazyNamed } from '@/lazyNamed'
import { definePage, icon } from '../registry'

const ChangelogPanel = lazyNamed(() => import('@/screens/Releases'), 'ChangelogPanel')
const RoadmapPanel = lazyNamed(() => import('@/screens/Releases'), 'RoadmapPanel')

export default definePage('hubra', 10, () => ({
  id: 'whats-new',
  label: tr('Neuigkeiten', "What's new"),
  icon: icon(IconSparkles),
  tabs: [
    {
      id: 'changelog',
      path: '/app/whats-new',
      label: tr('Änderungen', 'Changelog'),
      desc: tr('Was sich in Hubra geändert hat, neueste Version zuerst.', 'What changed in Hubra, newest version first.'),
      render: () => <ChangelogPanel />,
    },
    {
      id: 'roadmap',
      path: '/app/whats-new/roadmap',
      label: 'Roadmap',
      desc: tr('Woran wir arbeiten und was als Nächstes kommt.', 'What we are working on and what comes next.'),
      render: () => <RoadmapPanel />,
    },
  ],
}))
