import { useState, type ReactNode } from 'react'
import { Button, Group, Paper, Select, Stack, Tabs, Text, TextInput } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { IconLanguage, IconPlus, IconTrash, IconWand } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useToast } from '@/context/AppContext'
import { qk } from '@/data/keys'
import { getTranslationAvailable, machineTranslate } from '@/api/posts'
import type { ContentLanguage, PostText } from '@/types'
import { CONTENT_LANGUAGES, useLanguageNames } from './contentLanguages'

type Translations = Partial<Record<ContentLanguage, PostText>>

/**
 * The post's language and its other languages, in the post editor. Each
 * language gets title, summary and text; "Translate" pre-fills one from
 * the original when the platform set up machine translation.
 */
export function PostLanguagesField({
  language,
  translations,
  original,
  onLanguage,
  onTranslations,
  renderBody,
}: {
  language: ContentLanguage
  translations: Translations
  original: PostText
  onLanguage: (lang: ContentLanguage) => void
  onTranslations: (next: Translations) => void
  renderBody: (value: string, onChange: (v: string) => void) => ReactNode
}) {
  const { t } = useT()
  const { notify } = useToast()
  const names = useLanguageNames()
  const added = (Object.keys(translations) as ContentLanguage[]).filter((l) => l !== language)
  const [tab, setTab] = useState<string | null>(added[0] ?? null)
  const [busy, setBusy] = useState<ContentLanguage | null>(null)
  const mt = useQuery({ queryKey: qk.posts.translation, queryFn: getTranslationAvailable, staleTime: 600_000 })
  const free = CONTENT_LANGUAGES.filter((l) => l !== language && !added.includes(l))
  const active = (added.includes(tab as ContentLanguage) ? tab : added[0]) as ContentLanguage | undefined

  const set = (lang: ContentLanguage, patch: Partial<PostText>) =>
    onTranslations({
      ...translations,
      [lang]: { title: '', summary: null, body: '', ...translations[lang], ...patch },
    })
  const add = (lang: ContentLanguage) => {
    set(lang, {})
    setTab(lang)
  }
  const remove = (lang: ContentLanguage) => {
    const next = { ...translations }
    delete next[lang]
    onTranslations(next)
    setTab(null)
  }
  const translate = async (lang: ContentLanguage) => {
    if (!original.title.trim() && !original.body.trim()) return
    setBusy(lang)
    try {
      set(lang, await machineTranslate(lang, language, original))
    } catch (err) {
      notify('error', t('common.error'), err instanceof Error ? err.message : '')
    } finally {
      setBusy(null)
    }
  }

  return (
    <Paper withBorder p="sm" radius="md" data-testid="post-languages">
      <Stack gap="sm">
        <Group gap="sm" wrap="wrap" align="flex-end">
          <Select
            label={t('content.language', 'Sprache des Beitrags')}
            leftSection={<IconLanguage size={16} />}
            data={CONTENT_LANGUAGES.map((l) => ({ value: l, label: names[l] }))}
            value={language}
            allowDeselect={false}
            onChange={(v) => v && onLanguage(v as ContentLanguage)}
            w={220}
          />
          {free.map((l) => (
            <Button
              key={l}
              size="xs"
              variant="default"
              leftSection={<IconPlus size={14} />}
              onClick={() => add(l)}
            >
              {names[l]}
            </Button>
          ))}
        </Group>
        {added.length === 0 ? (
          <Text fz="xs" c="dimmed">
            {t(
              'content.languagesHint',
              'Schreibst du für Mitglieder in mehreren Sprachen? Füge eine Sprache hinzu. Jedes Mitglied sieht den Beitrag in seiner Sprache, sonst im Original.',
            )}
          </Text>
        ) : (
          <Tabs value={active ?? null} onChange={setTab}>
            <Tabs.List>
              {added.map((l) => (
                <Tabs.Tab key={l} value={l}>
                  {names[l]}
                </Tabs.Tab>
              ))}
            </Tabs.List>
            {added.map((l) => (
              <Tabs.Panel key={l} value={l} pt="sm">
                <Stack gap="sm">
                  <Group justify="space-between" gap="xs">
                    {mt.data?.available ? (
                      <Button
                        size="xs"
                        variant="light"
                        leftSection={<IconWand size={14} />}
                        loading={busy === l}
                        onClick={() => translate(l)}
                      >
                        {t('content.translate', {
                          defaultValue: 'Aus {{lang}} übersetzen',
                          lang: names[language],
                        })}
                      </Button>
                    ) : (
                      <span />
                    )}
                    <Button
                      size="xs"
                      variant="subtle"
                      color="red"
                      leftSection={<IconTrash size={14} />}
                      onClick={() => remove(l)}
                    >
                      {t('content.removeLanguage', 'Sprache entfernen')}
                    </Button>
                  </Group>
                  <TextInput
                    label={t('posts.titleLabel', 'Titel')}
                    value={translations[l]?.title ?? ''}
                    onChange={(e) => set(l, { title: e.currentTarget.value })}
                  />
                  <TextInput
                    label={t('posts.summaryLabel', 'Zusammenfassung (optional)')}
                    value={translations[l]?.summary ?? ''}
                    onChange={(e) => set(l, { summary: e.currentTarget.value || null })}
                  />
                  {renderBody(translations[l]?.body ?? '', (v) => set(l, { body: v }))}
                </Stack>
              </Tabs.Panel>
            ))}
          </Tabs>
        )}
      </Stack>
    </Paper>
  )
}
