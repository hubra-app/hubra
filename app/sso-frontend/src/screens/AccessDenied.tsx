import { Button, Stack, Text, Title, Paper, Box, Group } from '@mantine/core'
import { IconArrowLeft, IconShieldX } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import { useSso } from '@/context/SsoContext'

export function AccessDenied() {
  const navigate = useNavigate()
  const { redirectTarget } = useSso()

  const cosUrl = import.meta.env.VITE_COS_URL ?? 'https://cos.vollbuild.ch'

  return (
    <div
      className="graph-bg"
      style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 32 }}
    >
      <Box style={{ width: '100%', maxWidth: 420, textAlign: 'center' }}>
        <Group gap={10} mb={32} justify="center">
          <div className="logo-mark" />
          <Box>
            <Text fz="md" fw={700}>Hubra</Text>
            <Text fz="xs" c="#8a6a00" ff="'JetBrains Mono', monospace" style={{ letterSpacing: '0.06em' }}>
              Makerspace · Schwyz
            </Text>
          </Box>
        </Group>

        <Paper withBorder shadow="sm" radius="lg" p="xl">
          <Stack gap="md" align="center">
            <div
              style={{
                width: 56, height: 56, borderRadius: '50%', background: 'rgba(220,38,38,.12)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}
            >
              <IconShieldX size={28} color="#dc2626" />
            </div>
            <Title order={2}>Access Denied</Title>
            <Text size="sm" c="dimmed" lh={1.6}>
              You are signed in, but your account does not have superadmin
              permissions required to access the admin portal.
            </Text>
            <Text size="xs" c="dimmed">
              Redirect target: {redirectTarget}
            </Text>
            <Button
              variant="filled"
              fullWidth
              mt={8}
              onClick={() => { window.location.assign(cosUrl) }}
            >
              Go to member portal
            </Button>
            <Button
              variant="subtle"
              fullWidth
              leftSection={<IconArrowLeft size={16} />}
              onClick={() => navigate('/login')}
            >
              Back to login
            </Button>
          </Stack>
        </Paper>
      </Box>
    </div>
  )
}
