import type { ReactNode } from 'react'
import { Box, Group, Stack, Text, Title } from '@mantine/core'
import { useInstance } from '@/context/InstanceContext'
import { useT } from '@/locales/i18n'

/**
 * Signed-out pages: the form on the left, the Hubra brand panel on the right
 * (hidden on phones). The same layout as the SSO portal.
 */
export function AuthFrame({ children, wide = false }: { children: ReactNode; wide?: boolean }) {
  const { info } = useInstance()
  const { t } = useT()
  const clubName = info.club?.name

  return (
    <div className="auth-layout">
      <main className="auth-main">
        <Box style={{ width: '100%', maxWidth: wide ? 480 : 400 }}>
          <Group gap={10} mb={40} wrap="nowrap">
            <div className="logo-mark" style={{ width: 36, height: 36 }} />
            <Box style={{ minWidth: 0 }}>
              {clubName ? (
                <>
                  <Text fz="md" fw={700} lh={1.2} truncate>
                    {clubName}
                  </Text>
                  <Text fz="xs" c="dimmed">
                    {t('auth.poweredBy', 'mit Hubra')}
                  </Text>
                </>
              ) : (
                <Text fz={26} className="wordmark">
                  hubra
                </Text>
              )}
            </Box>
          </Group>
          {children}
        </Box>
      </main>
      <BrandPanel />
    </div>
  )
}

function BrandPanel() {
  const { t } = useT()
  const points = [
    t('auth.brand.point1', 'Mitglieder, Beiträge und Rechnungen'),
    t('auth.brand.point2', 'Anlässe, Umfragen und Beiträge'),
    t('auth.brand.point3', 'Inventar, Schlüssel und Zugänge'),
  ]
  return (
    <aside className="auth-brand" aria-hidden="true">
      <div className="auth-brand-inner">
        <img src="/hubra-mark.svg" alt="" width={56} height={56} style={{ borderRadius: 14 }} />
        <Title order={2} c="white" fz={34} lh={1.1} mt={32} maw={420}>
          {t('auth.brand.headline', 'Euer Verein. Alles an einem Ort.')}
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
