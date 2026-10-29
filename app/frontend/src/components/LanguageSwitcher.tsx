import { useMemo } from 'react'
import { Menu, Button } from '@mantine/core'
import { IconWorld, IconCheck } from '@tabler/icons-react'
import { useQuery } from '@tanstack/react-query'
import { setLanguage, getCurrentLanguage, useT } from '@/locales/i18n'
import { fetchLanguages } from '@/api/i18n'
import { qk } from '@/data/keys'

const FALLBACK_LANGUAGES = ['de-CH', 'en-GB']

const LANGUAGE_LABELS: Record<string, string> = {
  'de-CH': 'Deutsch',
  'en-GB': 'English',
}

const LANGUAGE_SHORT: Record<string, string> = {
  'de-CH': 'DE',
  'en-GB': 'EN',
}

export function LanguageSwitcher() {
  const { i18n } = useT()
  const { data, isError } = useQuery({
    queryKey: qk.languages,
    queryFn: fetchLanguages,
  })

  const languages = useMemo(() => {
    if (data && data.length > 0) return data
    if (isError) return FALLBACK_LANGUAGES
    return FALLBACK_LANGUAGES
  }, [data, isError])

  const current = getCurrentLanguage() || i18n.language

  return (
    <Menu shadow="md" width={160} position="bottom-end">
      <Menu.Target>
        <Button
          variant="subtle"
          color="gray"
          size="sm"
          px={10}
          leftSection={<IconWorld size={17} />}
          aria-label={LANGUAGE_LABELS[current] || current}
        >
          {LANGUAGE_SHORT[current] || current}
        </Button>
      </Menu.Target>
      <Menu.Dropdown>
        {languages.map((lang) => (
          <Menu.Item
            key={lang}
            onClick={() => setLanguage(lang)}
            rightSection={lang === current ? <IconCheck size={14} /> : null}
          >
            {LANGUAGE_LABELS[lang] || lang}
          </Menu.Item>
        ))}
      </Menu.Dropdown>
    </Menu>
  )
}
