import { useState } from 'react'
import { Group, Paper, Text } from '@mantine/core'
import { IconCheck, IconGlobe } from '@tabler/icons-react'
import * as authApi from '@/api/auth'
import { useToast } from '@/context/AppContext'
import { useT, setLanguage, getCurrentLanguage } from '@/locales/i18n'

export function AccountSettingsLanguageTab() {
  const { t } = useT()
  const { notify } = useToast()
  const [language, setLanguageState] = useState(getCurrentLanguage())

  return (
    <>
      <Paper withBorder shadow="sm" radius="lg">
        <Group
          p="md"
          gap="sm"
          style={{
            borderBottom: '1px solid var(--mantine-color-gray-3)',
          }}
        >
          <IconGlobe
            size={16}
            style={{ color: 'var(--mantine-color-ink-4)' }}
          />
          <Text fw={700} fz="md">
            {t('account.language', 'Spraach')}
          </Text>
        </Group>
        <div
          style={{
            padding: '20px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
          }}
        >
          <p
            style={{
              margin: 0,
              fontSize: 'var(--mantine-font-size-sm)',
              color: 'var(--mantine-color-ink-4)',
            }}
          >
            {t(
              'account.language.description',
              'Wähl dii bevorzugti Spraach für d Oberflächi.',
            )}
          </p>
          {[
            { code: 'en', label: 'English', nativeLabel: 'English' },
            {
              code: 'de-CH',
              label: 'Swiss German',
              nativeLabel: 'Schwiizerdütsch',
            },
          ].map((lang) => (
            <label
              key={lang.code}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: '14px 16px',
                border: `1px solid ${
                  language === lang.code
                    ? 'var(--mantine-color-acc-4)'
                    : 'var(--mantine-color-line-3)'
                }`,
                borderRadius: 10,
                cursor: 'pointer',
                background:
                  language === lang.code
                    ? 'rgba(116,65,224,.08)'
                    : 'transparent',
              }}
              onClick={async () => {
                setLanguageState(lang.code)
                setLanguage(lang.code)
                notify(
                  'success',
                  t('account.language.changed', 'Spraach gändert'),
                  t(
                    'account.language.changedMsg',
                    `Oberflächi isch jetzt uf ${lang.nativeLabel}.`,
                  ),
                )
                try {
                  await authApi.updateAccount({ language: lang.code })
                } catch {
                  // Language already updated in localStorage via setLanguage
                }
              }}
            >
              <div
                style={{
                  width: 18,
                  height: 18,
                  borderRadius: '50%',
                  border: `2px solid ${
                    language === lang.code
                      ? 'var(--mantine-color-acc-4)'
                      : 'var(--mantine-color-line-3)'
                  }`,
                  background:
                    language === lang.code
                      ? 'var(--mantine-color-acc-4)'
                      : 'transparent',
                  flexShrink: 0,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                {language === lang.code && (
                  <IconCheck size={11} color="#1a1625" strokeWidth={3} />
                )}
              </div>
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 2,
                }}
              >
                <span
                  style={{
                    fontSize: 'var(--mantine-font-size-sm)',
                    fontWeight: 500,
                    color: 'var(--mantine-color-ink-8)',
                  }}
                >
                  {lang.nativeLabel}
                </span>
                <span
                  style={{
                    fontSize: 'var(--mantine-font-size-xs)',
                    color: 'var(--mantine-color-ink-4)',
                  }}
                >
                  {lang.label}
                </span>
              </div>
            </label>
          ))}
        </div>
      </Paper>
    </>
  )
}
