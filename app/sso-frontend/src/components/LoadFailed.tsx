import { Button, Stack, Text } from '@mantine/core'
import { tr } from '@/lang'

/** A load that failed: say so and offer a retry, instead of an endless spinner. */
export function LoadFailed({ onRetry }: { onRetry: () => void }) {
  return (
    <Stack align="center" gap="xs" py="md" ta="center">
      <Text size="sm" c="dimmed">
        {tr('Das konnte nicht geladen werden.', 'This could not be loaded.')}
      </Text>
      <Button size="xs" variant="default" onClick={onRetry}>
        {tr('Erneut versuchen', 'Try again')}
      </Button>
    </Stack>
  )
}
