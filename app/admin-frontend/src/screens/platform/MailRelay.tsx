import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Badge,
  Button,
  Group,
  Paper,
  PasswordInput,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { PageHead } from '@/components/ui'
import { useAdmin } from '@/context/AdminContext'
import {
  getPlatformSettings,
  sendPlatformTestMail,
  updatePlatformSettings,
  type PlatformSetting,
} from '@/api/platform'

const RELAY = ['mail.relay.host', 'mail.relay.port', 'mail.relay.user', 'mail.relay.password']
const SENDER = ['mail.system.sender_email', 'mail.system.sender_name']

function SourceBadge({ s }: { s: PlatformSetting }) {
  return s.source === 'platform' ? (
    <Badge size="xs" variant="light">
      Set here
    </Badge>
  ) : (
    <Badge size="xs" variant="outline" color="gray">
      From env
    </Badge>
  )
}

/**
 * The outbound mail relay for the whole platform. Sign-in, SSO and platform
 * mail always go out through it from the system sender; club mail does too,
 * with the club's address as Reply-To.
 */
export function MailRelay() {
  const { notify } = useAdmin()
  const queryClient = useQueryClient()
  const { data: settings = [], isLoading } = useQuery({
    queryKey: ['platform-settings'],
    queryFn: getPlatformSettings,
  })
  // Only the fields edited since the last save; the rest show the saved value.
  const [draft, setDraft] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [testTo, setTestTo] = useState('')
  const [testing, setTesting] = useState(false)

  const byKey = Object.fromEntries(settings.map((s) => [s.key, s]))
  // A secret field left empty keeps the stored value.
  const changed = settings.filter((s) =>
    s.secret ? !!draft[s.key] : s.key in draft && draft[s.key] !== s.value,
  )

  const save = async (values: Record<string, string | null>) => {
    setSaving(true)
    try {
      const fresh = await updatePlatformSettings(values)
      queryClient.setQueryData(['platform-settings'], fresh)
      setDraft({})
      notify('success', 'Mail relay saved')
    } catch (err) {
      notify('error', 'Could not save', err instanceof Error ? err.message : undefined)
    } finally {
      setSaving(false)
    }
  }

  const sendTest = async () => {
    setTesting(true)
    try {
      await sendPlatformTestMail(testTo.trim())
      notify('success', 'Test mail sent', testTo.trim())
    } catch (err) {
      notify('error', 'Test mail failed', err instanceof Error ? err.message : undefined)
    } finally {
      setTesting(false)
    }
  }

  const field = (key: string) => {
    const s = byKey[key]
    if (!s) return null
    const label = (
      <Group gap={6} component="span">
        {s.label}
        <SourceBadge s={s} />
      </Group>
    )
    const common = {
      key,
      label,
      description: s.description,
      value: draft[key] ?? s.value,
      onChange: (e: React.ChangeEvent<HTMLInputElement>) =>
        setDraft((d) => ({ ...d, [key]: e.currentTarget.value })),
    }
    return s.secret ? (
      <PasswordInput {...common} placeholder={s.isSet ? '•••••••• (unchanged)' : ''} />
    ) : (
      <TextInput {...common} />
    )
  }

  const resetButton = (keys: string[]) =>
    keys.some((k) => byKey[k]?.source === 'platform') && (
      <Button
        variant="subtle"
        color="gray"
        size="xs"
        disabled={saving}
        onClick={() =>
          save(
            Object.fromEntries(
              keys.filter((k) => byKey[k]?.source === 'platform').map((k) => [k, null]),
            ),
          )
        }
      >
        Reset to env
      </Button>
    )

  return (
    <div>
      <PageHead eyebrow="Platform" title="Mail relay" />
      <Text size="sm" c="dimmed" mb={20} maw={720}>
        Every mail Hubra sends goes through this relay. Sign-in, SSO and platform notices come from
        the system sender. Club mail comes from the system sender too, with the club&apos;s address
        as Reply-To, unless the club has its own sender mailbox.
      </Text>

      {isLoading ? (
        <Text size="sm" c="dimmed">
          Loading…
        </Text>
      ) : (
        <Stack gap={20} maw={720}>
          <Paper withBorder shadow="sm" radius="lg" p="lg">
            <Group justify="space-between" mb={12}>
              <Title order={3}>Relay</Title>
              {resetButton(RELAY)}
            </Group>
            <Stack gap="sm">{RELAY.map(field)}</Stack>
          </Paper>

          <Paper withBorder shadow="sm" radius="lg" p="lg">
            <Group justify="space-between" mb={12}>
              <Title order={3}>System sender</Title>
              {resetButton(SENDER)}
            </Group>
            <Stack gap="sm">{SENDER.map(field)}</Stack>
          </Paper>

          <Group>
            <Button
              loading={saving}
              disabled={changed.length === 0}
              onClick={() => save(Object.fromEntries(changed.map((s) => [s.key, draft[s.key]])))}
            >
              Save
            </Button>
          </Group>

          <Paper withBorder shadow="sm" radius="lg" p="lg">
            <Title order={3} mb={12}>
              Test mail
            </Title>
            <Group align="flex-end">
              <TextInput
                label="Send to"
                placeholder="you@example.com"
                value={testTo}
                onChange={(e) => setTestTo(e.currentTarget.value)}
                style={{ flex: 1, minWidth: 220 }}
              />
              <Button
                variant="light"
                loading={testing}
                disabled={!testTo.includes('@') || changed.length > 0}
                onClick={sendTest}
              >
                Send test
              </Button>
            </Group>
            {changed.length > 0 && (
              <Text size="xs" c="dimmed" mt={6}>
                Save your changes first; the test uses the saved settings.
              </Text>
            )}
          </Paper>
        </Stack>
      )}
    </div>
  )
}
