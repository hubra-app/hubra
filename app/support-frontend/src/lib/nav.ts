import { useLang } from '@/lang'

/** The main sections, in the top bar and the phone menu. */
export function useNavItems() {
  const { tr } = useLang()
  return [
    { to: '/hilfe', label: tr('Hilfe', 'Help') },
    { to: '/roadmap', label: 'Roadmap' },
    { to: '/neuigkeiten', label: tr('Neuigkeiten', "What's new") },
    { to: '/status', label: 'Status' },
    { to: '/entwickler', label: tr('Entwickler', 'Developers') },
  ]
}
