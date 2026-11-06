import type { ReactNode } from 'react'
import {
  IconBell,
  IconBrandDiscord,
  IconCreditCard,
  IconWorldWww,
  IconBuildingCommunity,
  IconDatabase,
  IconHeartbeat,
  IconHome,
  IconKey,
  IconLanguage,
  IconLifebuoy,
  IconLock,
  IconMail,
  IconPuzzle,
  IconPlugConnected,
  IconShieldCheck,
  IconShieldLock,
  IconSparkles,
  IconTool,
} from '@tabler/icons-react'
import { Stack } from '@mantine/core'
import { tr } from '@/lang'
import { lazyNamed } from '@/lazyNamed'

// Every screen loads when its tab is first opened (TabbedPage's Suspense).
const MyTenantsTab = lazyNamed(() => import('@/screens/MyTenantsTab'), 'MyTenantsTab')
const TenantsTab = lazyNamed(() => import('@/screens/TenantsTab'), 'TenantsTab')
const TenantRequestsTab = lazyNamed(() => import('@/screens/TenantRequestsTab'), 'TenantRequestsTab')
const GlobalAuditTab = lazyNamed(() => import('@/screens/GlobalAuditTab'), 'GlobalAuditTab')
const SupportSessionsTab = lazyNamed(() => import('@/screens/SupportSessionsTab'), 'SupportSessionsTab')
const DataRequestsPanel = lazyNamed(() => import('@/screens/DataRequests'), 'DataRequestsPanel')
const RolesTab = lazyNamed(() => import('@/screens/RolesTab'), 'RolesTab')
const MarketplaceTab = lazyNamed(() => import('@/screens/MarketplaceTab'), 'MarketplaceTab')
const ChangelogPanel = lazyNamed(() => import('@/screens/Releases'), 'ChangelogPanel')
const RoadmapPanel = lazyNamed(() => import('@/screens/Releases'), 'RoadmapPanel')
const Backups = lazyNamed(() => import('@/screens/platform/Backups'), 'Backups')
const BackupsDesc = lazyNamed(() => import('@/screens/platform/Backups'), 'BackupsDesc')
const EventsPanel = lazyNamed(() => import('@/screens/platform/Alerts'), 'EventsPanel')
const MaintenancePanel = lazyNamed(() => import('@/screens/platform/Alerts'), 'MaintenancePanel')
const OverviewPanel = lazyNamed(() => import('@/screens/platform/Alerts'), 'OverviewPanel')
const RulesPanel = lazyNamed(() => import('@/screens/platform/Alerts'), 'RulesPanel')
const HealthPanel = lazyNamed(() => import('@/screens/platform/Diagnostics'), 'HealthPanel')
const MailServerPanel = lazyNamed(() => import('@/screens/platform/Diagnostics'), 'MailServerPanel')
const PermissionsPanel = lazyNamed(() => import('@/screens/platform/Diagnostics'), 'PermissionsPanel')
const JobsPanel = lazyNamed(() => import('@/screens/platform/Jobs'), 'JobsPanel')
const ErrorsPanel = lazyNamed(() => import('@/screens/platform/Errors'), 'ErrorsPanel')
const PerformancePanel = lazyNamed(() => import('@/screens/platform/Performance'), 'PerformancePanel')
const ApiErrorsPanel = lazyNamed(() => import('@/screens/platform/ApiErrors'), 'ApiErrorsPanel')
const MyAlertsCard = lazyNamed(() => import('@/screens/platform/MailMonitor'), 'MyAlertsCard')
const OutboundMailTab = lazyNamed(() => import('@/screens/platform/MailMonitor'), 'OutboundMailTab')
const DiscordPanel = lazyNamed(() => import('@/screens/platform/DiscordStatus'), 'DiscordPanel')
const DiscordClubsPanel = lazyNamed(() => import('@/screens/platform/DiscordClubs'), 'DiscordClubsPanel')
const SettingsSection = lazyNamed(() => import('@/screens/platform/SettingsSection'), 'SettingsSection')
const PlatformPlans = lazyNamed(() => import('@/screens/platform/Plans'), 'PlatformPlans')
const EarlyAccess = lazyNamed(() => import('@/screens/platform/EarlyAccess'), 'EarlyAccess')
const PlatformTranslations = lazyNamed(() => import('@/screens/platform/Translations'), 'PlatformTranslations')
const PlatformEncryption = lazyNamed(() => import('@/screens/platform/Encryption'), 'PlatformEncryption')
const AllApiTokens = lazyNamed(() => import('@/screens/platform/ApiTokens'), 'AllApiTokens')
const PlatformTokensPage = lazyNamed(() => import('@/screens/platform/ApiTokens'), 'PlatformTokensPage')
const OAuthApps = lazyNamed(() => import('@/screens/platform/OAuthApps'), 'OAuthApps')
const SupportCases = lazyNamed(() => import('@/screens/platform/Support'), 'SupportCases')

// The whole manage navigation in one place: sidebar sections, the pages in
// them and each page's tabs. A tab is its own URL; App.tsx makes a route for
// every tab and redirects the old URLs (see LEGACY_REDIRECTS) so bookmarks
// and links in alert mails, Discord posts and the event log still work.
//
// Rule of thumb: a page is one job an operator does, and its tabs are parts
// of that job. Settings live on the page they configure (the mail relay
// under Mail, the backup storage under Backups), not on a settings page.

export interface PageTab {
  id: string
  path: string
  label: string
  /** Any one of these global permissions shows the tab; none: everyone. */
  perm?: string | string[]
  /** Replaces the page description while this tab is open. */
  desc?: ReactNode
  render: () => ReactNode
}

export interface NavPage {
  id: string
  /** Sidebar label (short). */
  label: string
  /** Page title; the label when left out. */
  title?: string
  icon: ReactNode
  desc?: ReactNode
  /** The screen draws its own heading (it has buttons in it). */
  ownHead?: boolean
  tabs: PageTab[]
}

export interface NavSection {
  id: string
  label: string
  pages: NavPage[]
}

const icon = (I: typeof IconHome) => <I size={24} />

export function navSections(): NavSection[] {
  return [
    {
      id: 'clubs',
      label: tr('Vereine', 'Clubs'),
      pages: [
        {
          id: 'my-clubs',
          label: tr('Deine Vereine', 'Clubs you run'),
          icon: icon(IconHome),
          ownHead: true,
          tabs: [{ id: 'list', path: '/app/my-tenants', label: '', render: () => <MyTenantsTab /> }],
        },
        {
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
              render: () => (
                <Stack gap="lg">
                  <PlatformPlans />
                  <SettingsSection section="limits" />
                </Stack>
              ),
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
          ],
        },
        {
          id: 'reports',
          label: tr('Meldungen & Ideen', 'Reports & ideas'),
          icon: icon(IconLifebuoy),
          ownHead: true,
          tabs: [
            {
              id: 'list',
              path: '/app/reports',
              label: '',
              perm: 'support.cases',
              render: () => <SupportCases />,
            },
          ],
        },
        {
          id: 'plugins',
          label: tr('Plugin-Katalog', 'Plugin catalogue'),
          icon: icon(IconPuzzle),
          desc: tr(
            'Plugins bringen Module, die ohne neues Hubra-Release ausgeliefert und aktualisiert werden. Hier geprüfte und installierte Plugins erscheinen bei den Vereinen als normale Module unter Einstellungen → Module.',
            'Plugins bring modules that are shipped and updated without a new Hubra release. Plugins vetted and installed here show up for clubs as ordinary modules under Settings → Modules.',
          ),
          tabs: [
            { id: 'list', path: '/app/plugins', label: '', perm: 'plugins.manage', render: () => <MarketplaceTab /> },
          ],
        },
      ],
    },
    {
      id: 'operations',
      label: tr('Betrieb', 'Operations'),
      pages: [
        {
          id: 'alerts',
          label: tr('Warnungen', 'Alerts'),
          icon: icon(IconBell),
          desc: tr(
            'Was gerade nicht stimmt, alles, was passiert ist, und wer welche Warnung bekommt.',
            'What is wrong right now, everything that happened, and who gets which alert.',
          ),
          tabs: [
            {
              id: 'overview',
              path: '/app/platform/alerts',
              label: tr('Übersicht', 'Overview'),
              perm: 'platform.diagnostics',
              render: () => <OverviewPanel />,
            },
            {
              id: 'events',
              path: '/app/platform/alerts/events',
              label: tr('Ereignisse', 'Event log'),
              perm: 'platform.diagnostics',
              render: () => <EventsPanel />,
            },
            {
              id: 'rules',
              path: '/app/platform/alerts/rules',
              label: tr('Benachrichtigungen', 'Notifications'),
              perm: 'platform.diagnostics',
              render: () => <RulesPanel />,
            },
            {
              id: 'mine',
              path: '/app/platform/alerts/mine',
              label: tr('Meine Warnungen', 'My alerts'),
              perm: 'platform.diagnostics',
              render: () => <MyAlertsCard />,
            },
          ],
        },
        {
          id: 'diagnostics',
          label: tr('Diagnose', 'Diagnostics'),
          icon: icon(IconHeartbeat),
          desc: tr(
            'Wie es den Diensten geht, welche Fehler auftreten, wie schnell die API antwortet und was im Hintergrund läuft.',
            'How the services are doing, which errors happen, how fast the API answers and what runs in the background.',
          ),
          tabs: [
            {
              id: 'health',
              path: '/app/platform/diagnostics',
              label: tr('Systemzustand', 'System health'),
              perm: 'platform.diagnostics',
              render: () => <HealthPanel />,
            },
            {
              id: 'errors',
              path: '/app/platform/diagnostics/errors',
              label: tr('Fehler', 'Errors'),
              perm: 'platform.diagnostics',
              render: () => <ErrorsPanel />,
            },
            {
              id: 'api-errors',
              path: '/app/platform/diagnostics/api-errors',
              label: tr('API-Fehler', 'API errors'),
              perm: 'platform.diagnostics',
              render: () => <ApiErrorsPanel />,
            },
            {
              id: 'performance',
              path: '/app/platform/diagnostics/performance',
              label: tr('Leistung', 'Performance'),
              perm: 'platform.diagnostics',
              render: () => (
                <>
                  <PerformancePanel />
                  <div style={{ marginTop: 20 }}>
                    <SettingsSection section="performance" />
                  </div>
                </>
              ),
            },
            {
              id: 'jobs',
              path: '/app/platform/diagnostics/jobs',
              label: tr('Hintergrundjobs', 'Background jobs'),
              perm: 'platform.diagnostics',
              render: () => <JobsPanel />,
            },
          ],
        },
        {
          id: 'backups',
          label: tr('Backups', 'Backups'),
          icon: icon(IconDatabase),
          desc: <BackupsDesc />,
          tabs: [
            {
              id: 'list',
              path: '/app/platform/backups',
              label: tr('Backups', 'Backups'),
              perm: 'backups.manage',
              render: () => <Backups />,
            },
            {
              id: 'storage',
              path: '/app/platform/backups/storage',
              label: tr('Speicher', 'Storage'),
              perm: 'platform.settings',
              desc: tr(
                'Wohin die verschlüsselten Backups und die Dateien der Vereine gehen.',
                "Where the encrypted backups and the clubs' files go.",
              ),
              render: () => (
                <>
                  <SettingsSection section="backups" />
                  <SettingsSection section="files" />
                </>
              ),
            },
          ],
        },
        {
          id: 'maintenance',
          label: tr('Wartung', 'Maintenance'),
          icon: icon(IconTool),
          desc: tr(
            'Den Wartungsmodus jetzt ein- und ausschalten oder ein Wartungsfenster planen, das die Vereine vorher sehen.',
            'Switch maintenance mode on or off now, or plan a maintenance window clubs see in advance.',
          ),
          tabs: [
            {
              id: 'now',
              path: '/app/platform/maintenance',
              label: '',
              perm: 'platform.diagnostics',
              render: () => <MaintenancePanel />,
            },
          ],
        },
      ],
    },
    {
      id: 'services',
      label: tr('Dienste', 'Services'),
      pages: [
        {
          id: 'mail',
          label: tr('Mail', 'Mail'),
          icon: icon(IconMail),
          desc: tr(
            'Was Hubra verschickt, über welches Relay und von welchem Absender, und der gemeinsame Mailserver der Vereine.',
            'What Hubra sends, through which relay and from which sender, and the shared mail server of the clubs.',
          ),
          tabs: [
            {
              id: 'outbound',
              path: '/app/platform/mail',
              label: tr('Versand', 'Outbound'),
              perm: 'platform.diagnostics',
              render: () => <OutboundMailTab />,
            },
            {
              id: 'relay',
              path: '/app/platform/mail/relay',
              label: tr('Relay', 'Relay'),
              perm: 'platform.settings',
              render: () => <SettingsSection section="relay" />,
            },
            {
              id: 'sender',
              path: '/app/platform/mail/sender',
              label: tr('Systemabsender', 'System sender'),
              perm: 'platform.settings',
              render: () => <SettingsSection section="sender" />,
            },
            {
              id: 'server',
              path: '/app/platform/mail/server',
              label: tr('Mailserver', 'Mail server'),
              perm: 'platform.diagnostics',
              render: () => <MailServerPanel />,
            },
          ],
        },
        {
          id: 'discord',
          label: 'Discord',
          icon: icon(IconBrandDiscord),
          desc: tr(
            'Die Hubra-App auf Discord: ob der Bot läuft, alle Vereinsserver, die Zugangsdaten und die Kanäle der Plattform.',
            'The Hubra app on Discord: whether the bot runs, every club server, its credentials and the platform channels.',
          ),
          tabs: [
            {
              id: 'status',
              path: '/app/platform/discord',
              label: tr('Status', 'Status'),
              perm: 'platform.diagnostics',
              render: () => <DiscordPanel />,
            },
            {
              id: 'clubs',
              path: '/app/platform/discord/clubs',
              label: tr('Vereinsserver', 'Club servers'),
              perm: 'platform.diagnostics',
              render: () => <DiscordClubsPanel />,
            },
            {
              id: 'setup',
              path: '/app/platform/discord/setup',
              label: tr('Einrichtung', 'Setup'),
              perm: 'platform.settings',
              render: () => <SettingsSection section="discord-app" />,
            },
            {
              id: 'channels',
              path: '/app/platform/discord/channels',
              label: tr('Kanäle', 'Channels'),
              perm: 'platform.settings',
              render: () => <SettingsSection section="discord-channels" />,
            },
          ],
        },
        {
          id: 'domains',
          label: tr('Vereinsdomains', 'Club domains'),
          icon: icon(IconWorldWww),
          desc: tr(
            'Eigene Domains der Vereine: Zertifikat und Ingress pro bestätigter Domain, und der Notschalter.',
            "Clubs' own domains: certificate and Ingress per verified domain, and the kill switch.",
          ),
          tabs: [
            {
              id: 'serving',
              path: '/app/platform/domains',
              label: '',
              perm: 'platform.settings',
              render: () => <SettingsSection section="domains" />,
            },
          ],
        },
        {
          id: 'payments',
          label: tr('Zahlungen', 'Payments'),
          icon: icon(IconCreditCard),
          desc: tr(
            'Stripe: der Schlüssel des Plattform-Kontos, die Plattformgebühr für Online-Zahlungen der Vereine (Connect) und die Abrechnung der Vereine (Billing).',
            "Stripe: the platform account's key, the platform fee for clubs' online payments (Connect) and billing clubs (Billing).",
          ),
          tabs: [
            {
              id: 'stripe',
              path: '/app/platform/payments',
              label: '',
              perm: 'platform.settings',
              render: () => (
                <Stack gap="lg">
                  <SettingsSection section="payments" />
                  <SettingsSection section="billing" />
                </Stack>
              ),
            },
          ],
        },
        {
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
              label: '',
              perm: 'platform.settings',
              render: () => <PlatformTranslations />,
            },
          ],
        },
      ],
    },
    {
      id: 'access',
      label: tr('Zugriff & Sicherheit', 'Access & security'),
      pages: [
        {
          id: 'roles',
          label: tr('Rollen', 'Roles'),
          icon: icon(IconKey),
          desc: tr('Wer auf der Plattform was verwalten darf.', 'Who may manage what on the platform.'),
          tabs: [
            {
              id: 'platform',
              path: '/app/roles',
              label: tr('Plattform-Rollen', 'Platform roles'),
              perm: 'roles.manage',
              render: () => <RolesTab />,
            },
            {
              id: 'api',
              path: '/app/roles/api',
              label: tr('API-Berechtigungen', 'API permissions'),
              perm: 'platform.diagnostics',
              desc: tr(
                'Welche Berechtigung jede Route der Vereins-API verlangt.',
                'Which permission each route of the club API needs.',
              ),
              render: () => <PermissionsPanel />,
            },
          ],
        },
        {
          id: 'api-tokens',
          label: tr('API-Tokens', 'API tokens'),
          icon: icon(IconPlugConnected),
          desc: tr(
            'Lesende Tokens für Skripte und den Claude-Connector, und Apps mit OAuth-Anmeldung.',
            'Read-only tokens for scripts and the Claude connector, and apps that sign in with OAuth.',
          ),
          tabs: [
            {
              id: 'mine',
              path: '/app/api-tokens',
              label: tr('Meine Tokens', 'My tokens'),
              render: () => <PlatformTokensPage />,
            },
            {
              id: 'all',
              path: '/app/api-tokens/all',
              label: tr('Alle Tokens', 'All tokens'),
              perm: 'platform.settings',
              render: () => <AllApiTokens />,
            },
            {
              id: 'apps',
              path: '/app/api-tokens/apps',
              label: tr('Apps (OAuth)', 'Apps (OAuth)'),
              perm: 'platform.settings',
              render: () => <OAuthApps />,
            },
          ],
        },
        {
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
        },
        {
          id: 'privacy',
          label: tr('Datenschutz', 'Data protection'),
          icon: icon(IconShieldLock),
          desc: tr(
            'Wenn jemand eine Kopie seiner Daten in einem Verein will oder sie gelöscht haben möchte. Frist 30 Tage; hier steht, wer jede Anfrage wann erledigt hat.',
            'When someone wants a copy of their data in a club, or wants it deleted. 30-day deadline; this records who handled each request and when.',
          ),
          tabs: [
            {
              id: 'requests',
              path: '/app/privacy',
              label: '',
              perm: 'privacy.requests',
              render: () => <DataRequestsPanel />,
            },
          ],
        },
        {
          id: 'encryption',
          label: tr('Verschlüsselung', 'Encryption'),
          icon: icon(IconLock),
          desc: tr(
            'Die Schlüssel, mit denen Hubra Geheimnisse und Vereinsdaten verschlüsselt.',
            'The keys Hubra encrypts secrets and club data with.',
          ),
          tabs: [
            {
              id: 'keys',
              path: '/app/platform/encryption',
              label: '',
              perm: 'platform.settings',
              render: () => <PlatformEncryption />,
            },
          ],
        },
      ],
    },
    {
      id: 'hubra',
      label: 'Hubra',
      pages: [
        {
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
        },
      ],
    },
  ]
}

/**
 * Old URLs and where they live now. The query string is kept, so links like
 * …/diagnostics/outbound-mail?level=error still filter.
 */
export const LEGACY_REDIRECTS: Record<string, string> = {
  // Settings moved to the page each one configures.
  '/app/platform/settings': '/app/platform/mail/relay',
  '/app/platform/settings/mail': '/app/platform/mail/relay',
  '/app/platform/settings/sender': '/app/platform/mail/sender',
  '/app/platform/settings/backups': '/app/platform/backups/storage',
  '/app/platform/settings/discord': '/app/platform/discord/setup',
  '/app/platform/settings/alerts': '/app/platform/alerts/rules',
  '/app/platform/settings/limits': '/app/tenants/plans',
  '/app/tenants/limits': '/app/tenants/plans',
  '/app/tenants/prices': '/app/tenants/plans',
  '/app/platform/settings/encryption': '/app/platform/encryption',
  '/app/platform/settings/translations': '/app/platform/translations',
  // Diagnostics kept health, performance and jobs.
  '/app/platform/diagnostics/health': '/app/platform/diagnostics',
  '/app/platform/diagnostics/outbound-mail': '/app/platform/mail',
  '/app/platform/diagnostics/mail-server': '/app/platform/mail/server',
  '/app/platform/diagnostics/discord': '/app/platform/discord',
  '/app/platform/diagnostics/permissions': '/app/roles/api',
  '/app/platform/diagnostics/events': '/app/platform/alerts/events',
  // Alerts: performance went to Diagnostics, maintenance got its own page.
  '/app/platform/alerts/overview': '/app/platform/alerts',
  '/app/platform/alerts/performance': '/app/platform/diagnostics/performance',
  '/app/platform/alerts/settings': '/app/platform/alerts/mine',
  '/app/whats-new/changelog': '/app/whats-new',
}

/** Every tab a person may open, in sidebar order. */
export function visibleTabs(page: NavPage, can: (perm: string) => boolean): PageTab[] {
  return page.tabs.filter((t) => {
    if (!t.perm) return true
    return (Array.isArray(t.perm) ? t.perm : [t.perm]).some(can)
  })
}
