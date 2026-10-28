import type { ReactNode } from 'react'
import { Box, Group, Text } from '@mantine/core'
import { useInstance } from '@/context/InstanceContext'

/** Centered card with the club's name, shared by the signed-out pages. */
export function AuthFrame({ children }: { children: ReactNode }) {
  const { info } = useInstance()
  return (
    <div
      className="graph-bg"
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 32,
      }}
    >
      <Box style={{ width: '100%', maxWidth: 380 }}>
        <Group gap={10} mb={32}>
          <div className="logo-mark" />
          <Box>
            <Text fz="md" fw={700}>
              {info.club?.name ?? 'Hubra'}
            </Text>
            <Text
              fz="xs"
              c="#8a6a00"
              ff="'JetBrains Mono', monospace"
              style={{ letterSpacing: '0.06em' }}
            >
              Hubra
            </Text>
          </Box>
        </Group>
        {children}
      </Box>
    </div>
  )
}
