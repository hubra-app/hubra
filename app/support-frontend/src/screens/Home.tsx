import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Badge,
  Box,
  Group,
  Paper,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  ThemeIcon,
} from '@mantine/core'
import {
  IconBook,
  IconBug,
  IconBulb,
  IconCode,
  IconMap,
  IconMessageCircle,
  IconRocket,
  IconSearch,
  IconSparkles,
} from '@tabler/icons-react'
import { ARTICLES, CATEGORIES } from '@/content/help'
import { useLang } from '@/lang'
import { getStatus, STATUS_COLOR } from '@/api/status'

function StatusPill() {
  const { tr } = useLang()
  const q = useQuery({ queryKey: ['status', null], queryFn: () => getStatus(null), refetchInterval: 60_000 })
  const text = !q.data
    ? q.isError
      ? tr('Status nicht abrufbar', 'Status unavailable')
      : tr('Status wird geladen', 'Loading status')
    : {
        operational: tr('Alles funktioniert', 'Everything is working'),
        degraded: tr('Teilweise eingeschränkt', 'Partly limited'),
        down: tr('Störung', 'Outage'),
        maintenance: tr('Wartung läuft', 'Maintenance'),
      }[q.data.overall]
  const color = q.data ? STATUS_COLOR[q.data.overall] : q.isError ? 'red' : 'gray'
  return (
    <Badge
      component={Link}
      to="/status"
      size="lg"
      radius="xl"
      variant="light"
      color={color}
      leftSection={<Box w={8} h={8} style={{ borderRadius: 99, background: `var(--mantine-color-${color}-filled)` }} />}
      style={{ cursor: 'pointer', textTransform: 'none' }}
    >
      {text}
    </Badge>
  )
}

export function HomeScreen() {
  const { tr, lang } = useLang()
  const navigate = useNavigate()
  const [q, setQ] = useState('')

  const tiles = [
    {
      to: '/hilfe',
      icon: IconBook,
      color: 'acc',
      title: tr('Hilfe und Anleitungen', 'Help and guides'),
      text: tr('Schritt für Schritt durch Mitglieder, Finanzen, Anlässe und Konto.', 'Step by step through members, finance, events and your account.'),
    },
    {
      to: '/start',
      icon: IconRocket,
      color: 'gold',
      title: tr('Verein einrichten', 'Set up a club'),
      text: tr('Die Checkliste für neue Vereine, vom Logo bis zur ersten Rechnung.', 'The checklist for new clubs, from the logo to the first invoice.'),
    },
    {
      to: '/melden',
      icon: IconBug,
      color: 'red',
      title: tr('Problem melden', 'Report a problem'),
      text: tr('Etwas funktioniert nicht? Sag uns, was passiert ist.', 'Something not working? Tell us what happened.'),
    },
    {
      to: '/idee',
      icon: IconBulb,
      color: 'orange',
      title: tr('Idee vorschlagen', 'Suggest an idea'),
      text: tr('Was fehlt dir in Hubra? Andere Vereine können dafür stimmen.', 'What is missing in Hubra? Other clubs can vote for it.'),
    },
    {
      to: '/roadmap',
      icon: IconMap,
      color: 'violet',
      title: 'Roadmap',
      text: tr('Woran wir arbeiten, was als Nächstes kommt, und abstimmen.', 'What we are working on, what comes next, and vote.'),
    },
    {
      to: '/neuigkeiten',
      icon: IconSparkles,
      color: 'green',
      title: tr('Neuigkeiten', "What's new"),
      text: tr('Was sich in den letzten Versionen geändert hat.', 'What changed in the latest versions.'),
    },
    {
      to: '/entwickler',
      icon: IconCode,
      color: 'blue',
      title: tr('Für Entwickler', 'For developers'),
      text: tr('API-Tokens, der Claude-Connector und Plugins.', 'API tokens, the Claude connector and plugins.'),
    },
    {
      to: '/kontakt',
      icon: IconMessageCircle,
      color: 'gray',
      title: tr('Kontakt', 'Contact'),
      text: tr('Eine Frage, die keine Störung und keine Idee ist.', 'A question that is not a problem or an idea.'),
    },
  ]

  const popular = ['verein-starten', 'mitglieder-einladen', 'rechnungen-qr', 'anmelden-zwei-faktor']
    .map((s) => ARTICLES.find((a) => a.slug === s))
    .filter((a): a is (typeof ARTICLES)[number] => !!a)

  return (
    <>
      <Box className="sp-hero">
        <Box className="sp-wrap" py={{ base: 36, sm: 56 }}>
          <Stack gap="md" maw={680}>
            <StatusPill />
            <Text component="h1" className="sp-h1" fz={{ base: 30, sm: 40 }}>
              {tr('Wie können wir helfen?', 'How can we help?')}
            </Text>
            <form
              onSubmit={(e) => {
                e.preventDefault()
                navigate(`/hilfe?q=${encodeURIComponent(q)}`)
              }}
              role="search"
            >
              <TextInput
                size="lg"
                radius="md"
                value={q}
                onChange={(e) => setQ(e.currentTarget.value)}
                placeholder={tr('Suche in der Hilfe, z. B. «Rechnung»', 'Search the help, e.g. "invoice"')}
                leftSection={<IconSearch size={20} />}
                aria-label={tr('Hilfe durchsuchen', 'Search help')}
              />
            </form>
            <Group gap={6}>
              <Text size="sm" c="dimmed">
                {tr('Oft gesucht:', 'Popular:')}
              </Text>
              {popular.map((a) => (
                <Badge
                  key={a.slug}
                  component={Link}
                  to={`/hilfe/${a.slug}`}
                  variant="default"
                  radius="xl"
                  style={{ cursor: 'pointer', textTransform: 'none', fontWeight: 600 }}
                >
                  {a.title[lang]}
                </Badge>
              ))}
            </Group>
          </Stack>
        </Box>
      </Box>
      <Box className="sp-wrap" py={{ base: 28, sm: 44 }}>
        <SimpleGrid cols={{ base: 1, xs: 2, md: 4 }} spacing="md">
          {tiles.map((t) => (
            <Paper key={t.to} component={Link} to={t.to} withBorder p="lg" radius="lg" className="sp-tile">
              <ThemeIcon size={40} radius="md" variant="light" color={t.color} mb="sm">
                <t.icon size={22} />
              </ThemeIcon>
              <Text fw={700}>{t.title}</Text>
              <Text size="sm" c="dimmed" mt={4}>
                {t.text}
              </Text>
            </Paper>
          ))}
        </SimpleGrid>
        <Text fw={700} fz="lg" mt={40} mb="sm">
          {tr('Themen', 'Topics')}
        </Text>
        <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }} spacing="md">
          {Object.entries(CATEGORIES).map(([id, name]) => {
            const list = ARTICLES.filter((a) => a.category === id)
            return (
              <Paper key={id} withBorder p="md" radius="lg">
                <Text fw={700} mb={6}>
                  {name[lang]}
                </Text>
                <Stack gap={4}>
                  {list.map((a) => (
                    <Text key={a.slug} component={Link} to={`/hilfe/${a.slug}`} size="sm" c="acc">
                      {a.title[lang]}
                    </Text>
                  ))}
                </Stack>
              </Paper>
            )
          })}
        </SimpleGrid>
      </Box>
    </>
  )
}
