import { useState, useEffect, useMemo } from 'react'
import {
  TextInput,
  Textarea,
  Button,
  Alert,
  Text,
  Title,
  Stack,
  Group,
  Radio,
  SimpleGrid,
  ThemeIcon,
} from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { useT } from '@/locales/i18n'
import { IconCheck, IconArrowLeft } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import { submitApplication } from '@/api/applications'
import { getLookups } from '@/api/lookups'
import { AuthFrame } from './auth/AuthFrame'

export function ApplyScreen() {
  const { t } = useT()
  const navigate = useNavigate()
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [email, setEmail] = useState('')
  const [tier, setTier] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)

  const { data: lookupsData } = useQuery({
    queryKey: ['lookups'],
    queryFn: () => getLookups(),
  })

  const tiers = useMemo(
    () =>
      lookupsData
        ? [...lookupsData.tiersByName.entries()].map(([name, id]) => ({
            id,
            name,
          }))
        : [],
    [lookupsData],
  )

  useEffect(() => {
    if (tiers.length && !tier) {
      queueMicrotask(() => setTier(tiers[0].name))
    }
  }, [tiers, tier])

  const valid = firstName.trim() && lastName.trim() && email.includes('@')

  const handleSubmit = async () => {
    if (!valid) return
    setError('')
    setLoading(true)
    try {
      const selectedTier = tiers.find((t) => t.name === tier)
      await submitApplication({
        firstName: firstName.trim(),
        lastName: lastName.trim(),
        email: email.trim().toLowerCase(),
        wantsTierId: selectedTier?.id,
        message: message.trim(),
      })
      setDone(true)
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : t('apply.submissionFailed', 'Senden fehlgeschlagen. Bitte versuche es nochmals.'),
      )
    } finally {
      setLoading(false)
    }
  }

  if (done)
    return (
      <AuthFrame>
        <Stack align="center" ta="center" gap="xs">
          <ThemeIcon size={56} radius="xl" color="green" variant="light" mb="sm">
            <IconCheck size={28} />
          </ThemeIcon>
          <Title order={2}>{t('apply.applicationReceived', 'Antrag erhalten')}</Title>
          <Text size="sm" c="dimmed">
            {t(
              'apply.thanksText',
              'Danke, {{name}}. Wir prüfen deinen Antrag und melden uns unter {{email}}.',
              { name: `${firstName} ${lastName}`.trim(), email },
            )}
          </Text>
          <Text size="sm" c="dimmed" mb="md">
            {t('apply.usuallyTakesTime', 'Das dauert normalerweise 1–3 Arbeitstage.')}
          </Text>
          <Button
            variant="subtle"
            leftSection={<IconArrowLeft size={16} />}
            onClick={() => navigate('/login')}
          >
            {t('common.backToLogin', 'Zurück zur Anmeldung')}
          </Button>
        </Stack>
      </AuthFrame>
    )

  return (
    <AuthFrame wide>
      <Title order={1} fz={28} mb={6}>
        {t('apply.applyForMembership', 'Mitgliedschaft beantragen')}
      </Title>
      <Text size="md" c="dimmed" mb={32}>
        {t('apply.fillInDetails', 'Fülle deine Angaben aus. Der Verein prüft deinen Antrag.')}
      </Text>

      {error && (
        <Alert color="red" variant="light" mb="md">
          {error}
        </Alert>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault()
          handleSubmit()
        }}
      >
        <Stack gap="md">
          <SimpleGrid cols={{ base: 1, xs: 2 }} spacing="sm">
            <TextInput
              label={t('common.firstName', 'Vorname')}
              size="md"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              autoComplete="given-name"
              required
              autoFocus
            />
            <TextInput
              label={t('common.lastName', 'Nachname')}
              size="md"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              autoComplete="family-name"
              required
            />
          </SimpleGrid>

          <TextInput
            label={t('common.email', 'E-Mail')}
            type="email"
            size="md"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder={t('apply.emailPlaceholder', 'anna@beispiel.ch')}
            autoComplete="email"
            required
          />

          {tiers.length > 0 && (
            <Radio.Group
              label={t('apply.membershipTier', 'Mitgliedschaftsstufe')}
              value={tier}
              onChange={setTier}
            >
              <Stack gap={8} mt={4}>
                {tiers.map((tr) => (
                  <Radio.Card
                    key={tr.name}
                    value={tr.name}
                    radius="md"
                    p="sm"
                    style={{
                      borderColor: tier === tr.name ? 'var(--mantine-color-acc-6)' : undefined,
                      background: tier === tr.name ? 'var(--mantine-color-acc-0)' : undefined,
                    }}
                  >
                    <Group gap="sm" wrap="nowrap">
                      <Radio.Indicator />
                      <Text fw={600} size="sm">
                        {tr.name}
                      </Text>
                    </Group>
                  </Radio.Card>
                ))}
              </Stack>
            </Radio.Group>
          )}

          <Textarea
            label={t('apply.message', 'Nachricht')}
            description={t('common.optional', 'optional')}
            size="md"
            autosize
            minRows={3}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder={t(
              'apply.messagePlaceholder',
              'Erzähl uns kurz etwas über dich und was dich am Verein interessiert.',
            )}
          />

          <Button type="submit" size="md" fullWidth mt={4} loading={loading} disabled={!valid}>
            {t('apply.submitApplication', 'Antrag senden')}
          </Button>

          <Button
            variant="subtle"
            leftSection={<IconArrowLeft size={16} />}
            onClick={() => navigate('/login')}
          >
            {t('common.backToLogin', 'Zurück zur Anmeldung')}
          </Button>
        </Stack>
      </form>
    </AuthFrame>
  )
}
