import { useMemo } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { Anchor, Box, Button, Group, Paper, SimpleGrid, Stack, Text, TextInput } from '@mantine/core'
import { IconArrowLeft, IconSearch } from '@tabler/icons-react'
import { Page } from '@/components/Layout'
import { Markdown } from '@/components/Markdown'
import { headingsOf } from '@/lib/markdown'
import { ARTICLES, CATEGORIES, articleBySlug, searchArticles, type Category } from '@/content/help'
import { useLang } from '@/lang'

/** /hilfe (?q=): every article by topic, or the search results. */
export function HelpIndexScreen() {
  const { tr, lang } = useLang()
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const results = useMemo(() => searchArticles(q, lang), [q, lang])

  return (
    <Page
      title={tr('Hilfe', 'Help')}
      intro={tr(
        'Anleitungen für Vereins-Admins und Mitglieder. Nichts gefunden? Frag uns über das Kontaktformular.',
        "Guides for club admins and members. Can't find it? Ask us through the contact form.",
      )}
    >
      <TextInput
        size="md"
        radius="md"
        maw={560}
        mb="xl"
        value={q}
        onChange={(e) => setParams(e.currentTarget.value ? { q: e.currentTarget.value } : {}, { replace: true })}
        placeholder={tr('Suchen …', 'Search …')}
        leftSection={<IconSearch size={18} />}
        aria-label={tr('Hilfe durchsuchen', 'Search help')}
      />
      {q.trim() ? (
        results.length ? (
          <Stack gap="sm" maw={760}>
            {results.map((a) => (
              <Paper key={a.slug} component={Link} to={`/hilfe/${a.slug}`} withBorder radius="lg" p="md" className="sp-tile">
                <Text fw={650}>{a.title[lang]}</Text>
                <Text size="sm" c="dimmed">
                  {CATEGORIES[a.category][lang]} · {a.summary[lang]}
                </Text>
              </Paper>
            ))}
          </Stack>
        ) : (
          <Stack gap="sm" align="flex-start">
            <Text c="dimmed">{tr(`Nichts gefunden zu «${q}».`, `Nothing found for "${q}".`)}</Text>
            <Button component={Link} to="/kontakt" variant="light">
              {tr('Frage stellen', 'Ask a question')}
            </Button>
          </Stack>
        )
      ) : (
        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="lg">
          {(Object.keys(CATEGORIES) as Category[]).map((cat) => (
            <Box key={cat}>
              <Text fw={700} fz="lg" mb={8}>
                {CATEGORIES[cat][lang]}
              </Text>
              <Stack gap={8}>
                {ARTICLES.filter((a) => a.category === cat).map((a) => (
                  <Paper key={a.slug} component={Link} to={`/hilfe/${a.slug}`} withBorder radius="md" p="sm" className="sp-tile">
                    <Text fw={600} size="sm">
                      {a.title[lang]}
                    </Text>
                    <Text size="xs" c="dimmed">
                      {a.summary[lang]}
                    </Text>
                  </Paper>
                ))}
              </Stack>
            </Box>
          ))}
        </SimpleGrid>
      )}
    </Page>
  )
}

/** /hilfe/:slug: one article with its contents list. */
export function HelpArticleScreen() {
  const { tr, lang } = useLang()
  const { slug = '' } = useParams()
  const article = articleBySlug(slug)
  if (!article)
    return (
      <Page narrow title={tr('Anleitung nicht gefunden', 'Guide not found')}>
        <Anchor component={Link} to="/hilfe">
          {tr('Zur Hilfe', 'To help')}
        </Anchor>
      </Page>
    )
  const body = article.body[lang]
  const toc = headingsOf(body)
  const related = ARTICLES.filter((a) => a.category === article.category && a.slug !== article.slug)

  return (
    <Box className="sp-wrap" py={{ base: 24, sm: 40 }}>
      <Anchor component={Link} to="/hilfe" size="sm" display="inline-flex" style={{ alignItems: 'center', gap: 4 }}>
        <IconArrowLeft size={14} /> {CATEGORIES[article.category][lang]}
      </Anchor>
      <Group align="flex-start" gap={48} wrap="nowrap" mt="sm">
        <Box style={{ flex: 1, minWidth: 0 }}>
          <Text component="h1" className="sp-h1" mb={6}>
            {article.title[lang]}
          </Text>
          <Text c="dimmed" mb="lg">
            {article.summary[lang]}
          </Text>
          <Markdown source={body} />
          <Paper withBorder radius="lg" p="md" mt={40} maw={720}>
            <Text fw={650}>{tr('Hat das geholfen?', 'Did this help?')}</Text>
            <Text size="sm" c="dimmed" mb="sm">
              {tr('Wenn nicht, sag uns, was gefehlt hat.', 'If not, tell us what was missing.')}
            </Text>
            <Group gap="xs">
              <Button component={Link} to="/kontakt" size="xs" variant="light">
                {tr('Frage stellen', 'Ask a question')}
              </Button>
              <Button component={Link} to="/melden" size="xs" variant="default">
                {tr('Problem melden', 'Report a problem')}
              </Button>
            </Group>
          </Paper>
        </Box>
        <Box w={240} visibleFrom="md" style={{ position: 'sticky', top: 88, flexShrink: 0 }}>
          {toc.length > 1 && (
            <>
              <Text size="xs" fw={700} c="dimmed" tt="uppercase" mb={6}>
                {tr('Inhalt', 'Contents')}
              </Text>
              <Stack gap={4} mb="lg">
                {toc.map((h) => (
                  <Anchor key={h.id} href={`#${h.id}`} size="sm" c="var(--hb-text-2)">
                    {h.text}
                  </Anchor>
                ))}
              </Stack>
            </>
          )}
          {related.length > 0 && (
            <>
              <Text size="xs" fw={700} c="dimmed" tt="uppercase" mb={6}>
                {tr('Mehr dazu', 'Related')}
              </Text>
              <Stack gap={4}>
                {related.map((a) => (
                  <Anchor key={a.slug} component={Link} to={`/hilfe/${a.slug}`} size="sm">
                    {a.title[lang]}
                  </Anchor>
                ))}
              </Stack>
            </>
          )}
        </Box>
      </Group>
    </Box>
  )
}
