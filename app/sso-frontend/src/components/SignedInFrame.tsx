import type { ReactNode } from 'react'
import { Box, Button, Group, Text } from '@mantine/core'
import { IconLogout } from '@tabler/icons-react'
import { clearTokens } from '@hubra/api-client'
import * as authApi from '@/api/auth'
import { LangSwitch } from '@/components/LangSwitch'
import { tr, useLang } from '@/lang'

async function signOut() {
  await authApi.logout()
  clearTokens()
  window.location.assign('/login')
}

/** Logo, sign-out and a centred column: the frame of the signed-in pages. */
export function SignedInFrame({
  width = 520,
  actions,
  children,
}: {
  width?: number
  actions?: ReactNode
  children: ReactNode
}) {
  useLang()
  return (
    <div className="graph-bg" style={{ minHeight: '100vh', padding: '32px 16px' }}>
      <Box style={{ width: '100%', maxWidth: width, margin: '0 auto' }}>
        <Group justify="space-between" mb={32} wrap="nowrap">
          <Group gap={10} wrap="nowrap">
            <div className="logo-mark" />
            <Text fz={20} className="wordmark">
              hubra
            </Text>
          </Group>
          <Group gap={4} wrap="nowrap">
            <LangSwitch />
            {actions}
            <Button
              variant="subtle"
              size="xs"
              leftSection={<IconLogout size={16} />}
              onClick={signOut}
            >
              {tr('Abmelden', 'Sign out')}
            </Button>
          </Group>
        </Group>
        {children}
      </Box>
    </div>
  )
}
