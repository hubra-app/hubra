import { Page } from '@/components/Layout'
import { Markdown } from '@/components/Markdown'
import { DEVELOPERS, SECURITY } from '@/content/pages'
import { useLang } from '@/lang'

/** /entwickler: API tokens, the Claude connector, public data, plugins. */
export function DevelopersScreen() {
  const { tr, lang } = useLang()
  return (
    <Page
      narrow
      title={tr('Für Entwickler', 'For developers')}
      intro={tr('Hubra aus Skripten, Integrationen und Claude nutzen.', 'Use Hubra from scripts, integrations and Claude.')}
    >
      <Markdown source={DEVELOPERS[lang]} />
    </Page>
  )
}

/** /sicherheit: how to report a vulnerability (security.txt points here). */
export function SecurityScreen() {
  const { tr, lang } = useLang()
  return (
    <Page narrow title={tr('Sicherheit', 'Security')}>
      <Markdown source={SECURITY[lang]} />
    </Page>
  )
}
