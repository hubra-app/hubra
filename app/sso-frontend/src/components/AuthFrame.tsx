import type { ReactNode } from 'react'
import { Box, Group, SegmentedControl, Stack, Text, Title } from '@mantine/core'
import { ThemeToggle } from '@hubra/ui'
import { themeLabels, useLang, type Lang } from '@/lang'

/**
 * Signed-out pages: the form on the left, the Hubra brand panel on the right
 * (hidden on phones). The club app's application page uses the same layout.
 */
export function AuthFrame({ children, wide = false }: { children: ReactNode; wide?: boolean }) {
  const { lang, setLang, tr } = useLang()
  return (
    <div className="auth-layout">
      <main className="auth-main">
        <Box style={{ width: '100%', maxWidth: wide ? 480 : 400 }}>
          <Group justify="space-between" mb={40} wrap="nowrap">
            <Group gap={10} wrap="nowrap">
              <div className="logo-mark" style={{ width: 36, height: 36 }} />
              <Text fz={26} className="wordmark">
                hubra
              </Text>
            </Group>
            <Group gap={4} wrap="nowrap">
              <ThemeToggle labels={themeLabels(tr)} />
              <SegmentedControl
                size="xs"
                radius="md"
                value={lang}
                onChange={(v) => setLang(v as Lang)}
                data={[
                  { value: 'de', label: 'DE' },
                  { value: 'en', label: 'EN' },
                ]}
                aria-label={tr('Sprache', 'Language')}
              />
            </Group>
          </Group>
          {children}
        </Box>
      </main>
      <BrandPanel />
    </div>
  )
}

function BrandPanel() {
  const { tr } = useLang()
  const points = [
    tr('Mitglieder, Beiträge und Rechnungen', 'Members, dues and invoices'),
    tr('Anlässe, Umfragen und Beiträge', 'Events, polls and posts'),
    tr('Inventar, Schlüssel und Zugänge', 'Inventory, keys and access'),
  ]
  return (
    <aside className="auth-brand" aria-hidden="true">
      <div className="auth-brand-inner">
        <img src="/hubra-mark.svg" alt="" width={56} height={56} style={{ borderRadius: 14 }} />
        <Title order={2} c="white" fz={34} lh={1.1} mt={32} maw={420}>
          {tr('Euer Verein. Alles an einem Ort.', 'Your club. All in one place.')}
        </Title>
        <Stack gap={14} mt={28}>
          {points.map((p) => (
            <Group key={p} gap={12} wrap="nowrap">
              <span className="auth-brand-dot" />
              <Text c="white" fz="md" style={{ opacity: 0.92 }}>
                {p}
              </Text>
            </Group>
          ))}
        </Stack>
      </div>
    </aside>
  )
}

/** Round icon above a heading, e.g. the envelope on "Passwort vergessen". */
export function AuthIcon({ children, tone = 'violet' }: { children: ReactNode; tone?: 'violet' | 'green' | 'red' }) {
  const bg = { violet: 'var(--mantine-color-acc-light)', green: 'rgba(31,157,87,.12)', red: 'rgba(220,38,38,.10)' }[tone]
  return (
    <div
      style={{
        width: 52,
        height: 52,
        borderRadius: '50%',
        background: bg,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        marginBottom: 20,
      }}
    >
      {children}
    </div>
  )
}
