import { Button, Paper, Stack, Text, ThemeIcon } from '@mantine/core'
import { IconLock } from '@tabler/icons-react'
import { Loader, Center } from '@mantine/core'
import { useAuth } from '@/auth'
import { useLang } from '@/lang'

/**
 * Shown instead of a page that needs an account. Signing in happens on SSO,
 * which sends the person straight back here.
 */
export function SignInNeeded({ why }: { why: string }) {
  const { tr } = useLang()
  const { status, signInUrl } = useAuth()
  if (status === 'loading')
    return (
      <Center py={60}>
        <Loader />
      </Center>
    )
  return (
    <Paper withBorder p="xl" radius="lg" maw={520}>
      <Stack align="flex-start" gap="sm">
        <ThemeIcon size={44} radius="xl" variant="light">
          <IconLock size={22} />
        </ThemeIcon>
        <Text fw={700} fz="lg">
          {tr('Bitte melde dich an', 'Please sign in')}
        </Text>
        <Text c="dimmed">{why}</Text>
        <Button component="a" href={signInUrl()} mt={4}>
          {tr('Anmelden', 'Sign in')}
        </Button>
        <Text size="sm" c="dimmed">
          {tr(
            'Du nutzt dasselbe Konto wie in der Vereins-App.',
            'You use the same account as in the club app.',
          )}
        </Text>
      </Stack>
    </Paper>
  )
}
