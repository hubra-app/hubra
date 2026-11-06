import { useEffect } from 'react'
import { Link, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Anchor } from '@mantine/core'
import { Layout, Page } from '@/components/Layout'
import { useLang } from '@/lang'
import { HomeScreen } from '@/screens/Home'
import { HelpArticleScreen, HelpIndexScreen } from '@/screens/Help'
import { StartScreen } from '@/screens/Start'
import { RoadmapScreen } from '@/screens/Roadmap'
import { WhatsNewScreen } from '@/screens/WhatsNew'
import { StatusScreen } from '@/screens/Status'
import { ReportScreen } from '@/screens/ReportForm'
import { CaseScreen, MyCasesScreen } from '@/screens/MyCases'
import { DevelopersScreen, SecurityScreen } from '@/screens/Developers'
import { PrivacyScreen } from '@/screens/Privacy'
import { AccountHelpScreen } from '@/screens/AccountHelp'

function NotFound() {
  const { tr } = useLang()
  return (
    <Page narrow title={tr('Seite nicht gefunden', 'Page not found')}>
      <Anchor component={Link} to="/">
        {tr('Zur Startseite', 'To the start page')}
      </Anchor>
    </Page>
  )
}

/** The tab title follows the page, so history and bookmarks read well. */
function useTitle() {
  const { pathname } = useLocation()
  const { tr } = useLang()
  useEffect(() => {
    const first = pathname.split('/')[1] ?? ''
    const names: Record<string, string> = {
      hilfe: tr('Hilfe', 'Help'),
      start: tr('Verein einrichten', 'Set up a club'),
      roadmap: 'Roadmap',
      neuigkeiten: tr('Neuigkeiten', "What's new"),
      status: 'Status',
      melden: tr('Problem melden', 'Report a problem'),
      idee: tr('Idee vorschlagen', 'Suggest an idea'),
      kontakt: tr('Kontakt', 'Contact'),
      meine: tr('Meine Meldungen', 'My reports'),
      entwickler: tr('Entwickler', 'Developers'),
      sicherheit: tr('Sicherheit', 'Security'),
      datenschutz: tr('Meine Daten', 'My data'),
      konto: tr('Konto und Mails', 'Account and mails'),
    }
    document.title = names[first] ? `${names[first]} · Hubra Support` : 'Hubra Support'
    window.scrollTo(0, 0)
  }, [pathname, tr])
}

export default function App() {
  useTitle()
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<HomeScreen />} />
        <Route path="hilfe" element={<HelpIndexScreen />} />
        <Route path="hilfe/:slug" element={<HelpArticleScreen />} />
        <Route path="start" element={<StartScreen />} />
        <Route path="roadmap" element={<RoadmapScreen />} />
        <Route path="neuigkeiten" element={<WhatsNewScreen />} />
        <Route path="status" element={<StatusScreen />} />
        <Route path="melden" element={<ReportScreen key="bug" kind="bug" />} />
        <Route path="idee" element={<ReportScreen key="feature" kind="feature" />} />
        <Route path="kontakt" element={<ReportScreen key="question" kind="question" />} />
        <Route path="meine" element={<MyCasesScreen />} />
        <Route path="meine/:id" element={<CaseScreen />} />
        <Route path="entwickler" element={<DevelopersScreen />} />
        <Route path="sicherheit" element={<SecurityScreen />} />
        <Route path="datenschutz" element={<PrivacyScreen />} />
        <Route path="konto" element={<AccountHelpScreen />} />
        <Route path="nicht-ich" element={<Navigate to="/konto#nicht-ich" replace />} />
        <Route path="abmelden" element={<Navigate to="/konto#mails" replace />} />
        <Route path="unsubscribe" element={<Navigate to="/konto#mails" replace />} />
        {/* English and old addresses. */}
        <Route path="help/*" element={<Navigate to="/hilfe" replace />} />
        <Route path="whats-new" element={<Navigate to="/neuigkeiten" replace />} />
        <Route path="report" element={<Navigate to="/melden" replace />} />
        <Route path="idea" element={<Navigate to="/idee" replace />} />
        <Route path="contact" element={<Navigate to="/kontakt" replace />} />
        <Route path="developers" element={<Navigate to="/entwickler" replace />} />
        <Route path="security" element={<Navigate to="/sicherheit" replace />} />
        <Route path="privacy" element={<Navigate to="/datenschutz" replace />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
