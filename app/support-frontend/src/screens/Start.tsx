import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Anchor,
  Box,
  Checkbox,
  Group,
  Paper,
  Progress,
  Select,
  Stack,
  Text,
} from '@mantine/core'
import { IconExternalLink } from '@tabler/icons-react'
import { Page } from '@/components/Layout'
import { useAuth } from '@/auth'
import { ACCOUNT_URL, APP_URL } from '@/urls'
import { useLang } from '@/lang'
import { myClubs } from '@/api/support'

interface Step {
  id: string
  title: [string, string]
  text: [string, string]
  /** Club app path after /<club>/app/. */
  app?: string
  help?: string
  optional?: boolean
}

const STEPS: Step[] = [
  {
    id: 'club',
    title: ['Vereinsdaten und Logo', 'Club details and logo'],
    text: [
      'Name, Beschreibung, Farben und Logo. Sie erscheinen in der App, auf Rechnungen und in Mails.',
      'Name, description, colours and logo. They show in the app, on invoices and in mails.',
    ],
    app: 'settings/club',
    help: 'verein-starten',
  },
  {
    id: 'modules',
    title: ['Module wählen', 'Choose modules'],
    text: [
      'Schalte aus, was ihr nicht braucht. So bleibt das Menü kurz; die Daten bleiben erhalten.',
      "Switch off what you don't need. That keeps the menu short; the data stays.",
    ],
    app: 'settings/modules',
    help: 'module',
  },
  {
    id: 'bank',
    title: ['Bankverbindung', 'Bank details'],
    text: [
      'IBAN bzw. QR-IBAN und Adresse, damit Rechnungen einen QR-Einzahlungsschein bekommen.',
      'IBAN or QR-IBAN and address, so invoices get a Swiss QR bill.',
    ],
    app: 'settings/bank',
    help: 'rechnungen-qr',
  },
  {
    id: 'tiers',
    title: ['Mitgliedschaften und Beiträge', 'Memberships and fees'],
    text: [
      'Die Stufen (Aktiv, Passiv, Junior …), was sie kosten und wann sie verrechnet werden.',
      'The tiers (active, passive, junior …), what they cost and when they are billed.',
    ],
    app: 'members/tiers',
    help: 'rechnungen-qr',
  },
  {
    id: 'roles',
    title: ['Rollen prüfen', 'Check the roles'],
    text: [
      'Wer darf was? Lieber eine Rolle mehr als allen Admin-Rechte.',
      'Who may do what? Rather one more role than admin rights for everyone.',
    ],
    app: 'system/roles',
    help: 'rollen-und-rechte',
  },
  {
    id: 'groups',
    title: ['Gruppen und Teams', 'Groups and teams'],
    text: [
      'Teams, Vorstand, Kommissionen. Trainings und Rechte können an einer Gruppe hängen.',
      'Teams, board, committees. Trainings and rights can be tied to a group.',
    ],
    app: 'groups',
    optional: true,
  },
  {
    id: 'mfa',
    title: ['Zwei-Faktor für den Vorstand', 'Two-factor for the board'],
    text: [
      'Wer Mitglieder- und Finanzdaten sieht, sollte sich mit Passkey oder Authenticator-App anmelden.',
      'Whoever sees member and finance data should sign in with a passkey or authenticator app.',
    ],
    help: 'anmelden-zwei-faktor',
  },
  {
    id: 'invite',
    title: ['Mitglieder einladen', 'Invite members'],
    text: [
      'Einzeln oder per CSV. Jede Person nimmt ihre Einladung selbst an.',
      'One by one or by CSV. Each person accepts their invitation themselves.',
    ],
    app: 'members',
    help: 'mitglieder-einladen',
  },
  {
    id: 'events',
    title: ['Erster Anlass oder Training', 'First event or training'],
    text: [
      'Ein Anlass mit Anmeldung oder eine wöchentliche Trainingsserie mit Anwesenheit.',
      'An event with registration, or a weekly training series with attendance.',
    ],
    app: 'operations/events',
    help: 'trainings-anwesenheit',
  },
  {
    id: 'backup',
    title: ['Eigener Backup-Schlüssel', 'Your own backup key'],
    text: [
      'Damit ihr eure Backups jederzeit selbst öffnen könnt.',
      'So you can open your backups yourselves at any time.',
    ],
    app: 'settings/encryption',
    help: 'backups-schluessel',
    optional: true,
  },
]

const STORE = 'hubra_support_start'

function readDone(): string[] {
  try {
    const v = JSON.parse(localStorage.getItem(STORE) ?? '[]')
    return Array.isArray(v) ? v.filter((x) => typeof x === 'string') : []
  } catch {
    return []
  }
}

/**
 * /start: the checklist for a new club. The ticks stay in this browser only
 * (a convenience, nothing the club or Hubra needs to know).
 */
export function StartScreen() {
  const { tr, lang } = useLang()
  const i = lang === 'en' ? 1 : 0
  const { status } = useAuth()
  const clubs = useQuery({ queryKey: ['my-clubs'], queryFn: myClubs, enabled: status === 'authed' })
  const [club, setClub] = useState<string | null>(null)
  const [done, setDone] = useState<string[]>(readDone)
  const options = (clubs.data ?? []).map((c) => ({ value: c.tenant_slug, label: c.tenant_name }))
  const slug = club ?? options[0]?.value ?? null

  useEffect(() => {
    try {
      localStorage.setItem(STORE, JSON.stringify(done))
    } catch {
      /* private mode: keep the ticks for this visit */
    }
  }, [done])

  const toggle = (id: string) =>
    setDone((d) => (d.includes(id) ? d.filter((x) => x !== id) : [...d, id]))
  const required = STEPS.filter((s) => !s.optional)
  const doneCount = required.filter((s) => done.includes(s.id)).length

  return (
    <Page
      narrow
      title={tr('Verein einrichten', 'Set up a club')}
      intro={tr(
        'Die wichtigsten Schritte für einen neuen Verein auf Hubra, in einer sinnvollen Reihenfolge. Hake ab, was erledigt ist; dein Browser merkt es sich.',
        'The main steps for a new club on Hubra, in a sensible order. Tick off what is done; your browser remembers it.',
      )}
    >
      <Paper withBorder radius="lg" p="md" mb="lg">
        <Group justify="space-between" mb={8} wrap="wrap" gap="sm">
          <Text fw={650}>
            {tr(`${doneCount} von ${required.length} erledigt`, `${doneCount} of ${required.length} done`)}
          </Text>
          {options.length > 1 && (
            <Select
              size="xs"
              data={options}
              value={slug}
              onChange={setClub}
              allowDeselect={false}
              aria-label={tr('Verein', 'Club')}
              w={220}
            />
          )}
        </Group>
        <Progress value={(doneCount / required.length) * 100} radius="xl" />
        {status !== 'authed' && (
          <Text size="xs" c="dimmed" mt={8}>
            {tr(
              'Angemeldet führen die Links direkt in deinen Verein.',
              'Signed in, the links take you straight into your club.',
            )}
          </Text>
        )}
      </Paper>
      <Stack gap="sm">
        {STEPS.map((s, n) => {
          const checked = done.includes(s.id)
          return (
            <Paper key={s.id} withBorder radius="lg" p="md" style={checked ? { opacity: 0.7 } : undefined}>
              <Group align="flex-start" wrap="nowrap" gap="md">
                <Checkbox
                  mt={3}
                  checked={checked}
                  onChange={() => toggle(s.id)}
                  aria-label={s.title[i]}
                  radius="xl"
                />
                <Box style={{ flex: 1, minWidth: 0 }}>
                  <Text fw={650} td={checked ? 'line-through' : undefined}>
                    {n + 1}. {s.title[i]}
                    {s.optional && (
                      <Text span size="xs" c="dimmed" fw={500}>
                        {' '}
                        · {tr('optional', 'optional')}
                      </Text>
                    )}
                  </Text>
                  <Text size="sm" c="dimmed" mt={2}>
                    {s.text[i]}
                  </Text>
                  <Group gap="md" mt={6}>
                    {s.app && slug && (
                      <Anchor href={`${APP_URL}/${encodeURIComponent(slug)}/app/${s.app}`} size="sm">
                        {tr('In der App öffnen', 'Open in the app')}{' '}
                        <IconExternalLink size={13} style={{ verticalAlign: '-2px' }} />
                      </Anchor>
                    )}
                    {s.id === 'mfa' && (
                      <Anchor href={`${ACCOUNT_URL}/zwei-faktor`} size="sm">
                        {tr('Zwei-Faktor einrichten', 'Set up two-factor')}{' '}
                        <IconExternalLink size={13} style={{ verticalAlign: '-2px' }} />
                      </Anchor>
                    )}
                    {s.help && (
                      <Anchor component={Link} to={`/hilfe/${s.help}`} size="sm">
                        {tr('Anleitung', 'Guide')}
                      </Anchor>
                    )}
                  </Group>
                </Box>
              </Group>
            </Paper>
          )
        })}
      </Stack>
    </Page>
  )
}
