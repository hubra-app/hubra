import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert,
  Anchor,
  Badge,
  Button,
  Center,
  Group,
  List,
  Loader,
  Paper,
  Radio,
  SegmentedControl,
  Stack,
  Text,
  ThemeIcon,
  Title,
} from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { IconAlertTriangle, IconLogin2, IconPlugConnected, IconShieldCheck, IconUsers } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import { useSso } from '@/context/SsoContext'
import { SignedInFrame } from '@/components/SignedInFrame'
import { LoadFailed } from '@/components/LoadFailed'
import * as authApi from '@/api/auth'
import { useLang } from '@/lang'

/** The query of /oauth/authorize, as the app sent it. */
function useAuthorizeParams(): Record<string, string> {
  return useMemo(() => {
    const out: Record<string, string> = {}
    new URLSearchParams(window.location.search).forEach((v, k) => {
      out[k] = v
    })
    return out
  }, [])
}

/**
 * The consent page of Hubra's OAuth server (docs/oauth.md): an app such as
 * Claude asks to read Hubra for the person. They pick the club (or the
 * platform) and how long; the app then gets a sign-in that never has more
 * rights than they have themselves, and they can end it any time under
 * Mein Konto › Apps.
 */
export function OAuthAuthorizeScreen() {
  const { authStatus } = useSso()
  const navigate = useNavigate()
  const { tr } = useLang()
  const params = useAuthorizeParams()
  const [target, setTarget] = useState<string | null>(null)
  const [days, setDays] = useState<string | null>(null)
  const [busy, setBusy] = useState<'allow' | 'deny' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [leaving, setLeaving] = useState(false)

  // prompt=none (OpenID): never ask; the app hears "login_required".
  const silent = (params.prompt ?? '').split(' ').includes('none')
  useEffect(() => {
    if (authStatus === 'anon' && !silent)
      navigate(`/login?redirect=${encodeURIComponent(window.location.href)}`, { replace: true })
  }, [authStatus, navigate, silent])

  const consent = useQuery({
    queryKey: ['oauth-consent', params],
    queryFn: () => authApi.getOAuthConsent(params),
    enabled: authStatus === 'authed' || (authStatus === 'anon' && silent),
    retry: false,
  })
  const data = consent.data

  // A bad request the app should hear about goes straight back to it.
  const sendBack = data?.problem?.redirect
  useEffect(() => {
    if (sendBack) window.location.replace(sendBack)
  }, [sendBack])

  // The only club that works is picked already.
  const open = data && !data.problem ? data.clubs.filter((c) => c.available) : []
  const preset = open.length === 1 && !data?.platform?.available ? `club:${open[0].slug}` : null
  const chosen = target ?? preset

  const reasonText = (reason: string | null): string => {
    switch (reason) {
      case 'MEMBERS_OFF':
        return tr(
          'Dieser Verein erlaubt Mitgliedern keinen Zugang mit Apps. Admins schalten das unter Einstellungen › API & Webhooks ein.',
          'This club does not let members connect apps. Admins turn it on under Settings › API & webhooks.',
        )
      case 'AI_OFF':
        return tr(
          'Dieser Verein hat KI-Assistenten nicht erlaubt. Admins schalten das unter Einstellungen › API & Webhooks ein.',
          'This club has not allowed AI assistants. Admins turn it on under Settings › API & webhooks.',
        )
      case 'MFA_SETUP_FIRST':
        return tr(
          'Richte zuerst die Zwei-Faktor-Anmeldung ein (Mein Konto › Zwei-Faktor).',
          'Set up two-factor sign-in first (My account › Two-factor).',
        )
      default:
        return tr('Nicht verfügbar', 'Not available')
    }
  }

  const answer = async (allow: boolean) => {
    if (!data) return
    setBusy(allow ? 'allow' : 'deny')
    setError(null)
    try {
      const platform = chosen === 'platform'
      const club = chosen?.startsWith('club:') ? chosen.slice(5) : undefined
      const chosenDays = days
        ? Number(days)
        : platform
          ? data.days.defaultPlatform
          : data.days.defaultClub
      const res = await authApi.answerOAuthConsent({
        params,
        allow,
        ...(allow ? { club, platform: platform || undefined, days: chosenDays } : {}),
      })
      const to = res.redirect ?? res.problem?.redirect
      if (to) {
        setLeaving(true)
        window.location.assign(to)
        return
      }
      setError(res.problem?.message ?? tr('Das hat nicht geklappt.', 'That did not work.'))
    } catch (err) {
      setError(err instanceof Error ? err.message : tr('Das hat nicht geklappt.', 'That did not work.'))
    } finally {
      setBusy(null)
    }
  }

  // Signed in to this app before with the same details: no question.
  const remembered = Boolean(data && !data.problem && data.remembered)
  const autoSent = useRef(false)
  useEffect(() => {
    if (!remembered || autoSent.current) return
    autoSent.current = true
    void answer(true)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once, for this request
  }, [remembered])

  if (authStatus !== 'authed' || consent.isLoading || leaving || sendBack || (remembered && !error))
    return (
      <Center h="100vh">
        <Loader />
      </Center>
    )
  if (consent.isError || !data) return <LoadFailed onRetry={() => consent.refetch()} />

  if (data.problem)
    return (
      <SignedInFrame width={520}>
        <Paper withBorder p="xl">
          <Stack gap="sm">
            <ThemeIcon size={48} radius="xl" variant="light" color="red">
              <IconAlertTriangle size={24} />
            </ThemeIcon>
            <Title order={2}>{tr('Diese Anfrage stimmt nicht', 'This request is not valid')}</Title>
            <Text size="sm" c="dimmed">
              {tr(
                'Die App hat eine Anmeldung verlangt, die Hubra nicht kennt oder die nicht zu ihr passt. Es wurde nichts freigegeben.',
                'The app asked for a sign-in Hubra does not know or that does not match it. Nothing was shared.',
              )}
            </Text>
            <Text size="xs" c="dimmed">
              {data.problem.message}
            </Text>
          </Stack>
        </Paper>
      </SignedInFrame>
    )

  const { client } = data
  if (data.mode === 'identity')
    return (
      <SignedInFrame width={520}>
        <Paper withBorder p="xl">
          <IdentityConsent data={data} busy={busy} error={error} onAnswer={answer} />
        </Paper>
      </SignedInFrame>
    )
  const mcp = data.resource === 'mcp'
  const write = data.scopes.includes('write')
  const platformChosen = chosen === 'platform'
  const dayOptions = (platformChosen ? data.days.platform : data.days.club).map((d) => ({
    value: String(d),
    label: tr(`${d} Tage`, `${d} days`),
  }))
  const currentDays =
    days && dayOptions.some((o) => o.value === days)
      ? days
      : String(platformChosen ? data.days.defaultPlatform : data.days.defaultClub)
  const nothing = data.clubs.every((c) => !c.available) && !data.platform?.available

  return (
    <SignedInFrame width={560}>
      <Paper withBorder p="xl">
        <Stack gap="md">
          <Group gap="sm" wrap="nowrap">
            <ThemeIcon size={48} radius="xl" variant="light">
              <IconPlugConnected size={24} />
            </ThemeIcon>
            <div style={{ minWidth: 0 }}>
              <Title order={2} style={{ overflowWrap: 'anywhere' }}>
                {tr(`${client.name} mit Hubra verbinden`, `Connect ${client.name} to Hubra`)}
              </Title>
              <Text size="sm" c="dimmed">
                {tr(`Angemeldet als ${data.user.name}`, `Signed in as ${data.user.name}`)} ({data.user.email})
              </Text>
            </div>
          </Group>

          {client.verified ? (
            <Group gap={6}>
              <Badge color="green" variant="light" leftSection={<IconShieldCheck size={12} />}>
                {tr('Bei Hubra registriert', 'Registered with Hubra')}
              </Badge>
              {client.clientUri && (
                <Anchor href={client.clientUri} target="_blank" rel="noreferrer" size="xs">
                  {new URL(client.clientUri).host}
                </Anchor>
              )}
            </Group>
          ) : (
            <Alert color="yellow" variant="light" icon={<IconAlertTriangle size={18} />}>
              {tr(
                `Diese App hat sich selbst angemeldet; Hubra hat sie nicht geprüft. Sie bekommt den Zugang über ${client.redirectHost ?? '?'}. Erlaube das nur, wenn du die App gerade selbst verbinden wolltest.`,
                `This app registered itself; Hubra has not checked it. It receives the access through ${client.redirectHost ?? '?'}. Only allow this if you just asked to connect it yourself.`,
              )}
            </Alert>
          )}
          {client.description && <Text size="sm">{client.description}</Text>}

          <Stack gap={4}>
            <Text fw={600} size="sm">
              {tr('Was die App darf', 'What the app may do')}
            </Text>
            <Text size="sm">
              {write
                ? tr(
                    'Lesen und ändern, was du im gewählten Verein darfst.',
                    'Read and change what you may in the chosen club.',
                  )
                : tr('Lesen, was du sehen darfst. Sie kann nichts ändern.', 'Read what you may see. It cannot change anything.')}
              {mcp &&
                tr(
                  ' Nur über den Hubra-Connector für Claude.',
                  ' Only through the Hubra connector for Claude.',
                )}
            </Text>
            <Text size="xs" c="dimmed">
              {tr(
                'Nie mehr als deine eigenen Rechte. Passwort, Konto und Zugangsdaten bleiben aussen vor. Beenden kannst du den Zugang jederzeit unter Mein Konto › Apps.',
                'Never more than your own rights. Password, account and credentials stay out of reach. You can end the access any time under My account › Apps.',
              )}
            </Text>
          </Stack>

          <Radio.Group
            label={tr('Für welchen Verein?', 'For which club?')}
            value={chosen}
            onChange={setTarget}
          >
            <Stack gap="xs" mt={6}>
              {data.clubs.map((c) => (
                <Radio
                  key={c.slug}
                  value={`club:${c.slug}`}
                  disabled={!c.available}
                  label={c.name}
                  description={c.available ? (c.isAdmin ? tr('Du bist Admin', 'You are an admin') : undefined) : reasonText(c.reason)}
                />
              ))}
              {data.platform && (
                <Radio
                  value="platform"
                  disabled={!data.platform.available}
                  label={tr('Plattform (manage, nur lesen)', 'Platform (manage, read only)')}
                  description={
                    data.platform.available
                      ? tr('Diagnose und Einstellungen, die du sehen darfst', 'Diagnostics and settings you may see')
                      : reasonText(data.platform.reason)
                  }
                />
              )}
              {data.clubs.length === 0 && !data.platform && (
                <Text size="sm" c="dimmed">
                  {tr('Du bist in keinem Verein.', 'You are not in any club.')}
                </Text>
              )}
            </Stack>
          </Radio.Group>

          <Stack gap={4}>
            <Text fw={600} size="sm">
              {tr('Wie lange?', 'For how long?')}
            </Text>
            <SegmentedControl data={dayOptions} value={currentDays} onChange={setDays} />
            <Text size="xs" c="dimmed">
              {tr(
                'Danach muss die App dich nochmals fragen.',
                'After that the app has to ask you again.',
              )}
            </Text>
          </Stack>

          {error && (
            <Alert color="red" variant="light">
              {error}
            </Alert>
          )}

          <Group justify="flex-end">
            <Button variant="default" loading={busy === 'deny'} disabled={busy !== null} onClick={() => answer(false)}>
              {tr('Ablehnen', 'Deny')}
            </Button>
            <Button
              loading={busy === 'allow'}
              disabled={busy !== null || !chosen || nothing}
              onClick={() => answer(true)}
            >
              {tr('Erlauben', 'Allow')}
            </Button>
          </Group>
        </Stack>
      </Paper>
    </SignedInFrame>
  )
}

/** The badge or warning that says who registered the app. */
function AppOrigin({ client, clubName }: { client: authApi.OAuthApp; clubName?: string }) {
  const { tr } = useLang()
  if (client.kind === 'club')
    return (
      <Group gap={6}>
        <Badge color="green" variant="light" leftSection={<IconUsers size={12} />}>
          {tr(`Vom Verein ${clubName ?? ''} eingerichtet`, `Set up by the club ${clubName ?? ''}`)}
        </Badge>
        {client.clientUri && (
          <Anchor href={client.clientUri} target="_blank" rel="noreferrer" size="xs">
            {new URL(client.clientUri).host}
          </Anchor>
        )}
      </Group>
    )
  if (client.verified)
    return (
      <Group gap={6}>
        <Badge color="green" variant="light" leftSection={<IconShieldCheck size={12} />}>
          {tr('Bei Hubra registriert', 'Registered with Hubra')}
        </Badge>
        {client.clientUri && (
          <Anchor href={client.clientUri} target="_blank" rel="noreferrer" size="xs">
            {new URL(client.clientUri).host}
          </Anchor>
        )}
      </Group>
    )
  return (
    <Alert color="yellow" variant="light" icon={<IconAlertTriangle size={18} />}>
      {tr(
        `Diese App hat sich selbst angemeldet; Hubra hat sie nicht geprüft. Sie bekommt den Zugang über ${client.redirectHost ?? '?'}.`,
        `This app registered itself; Hubra has not checked it. It receives the access through ${client.redirectHost ?? '?'}.`,
      )}
    </Alert>
  )
}

/**
 * Sign in with Hubra (OpenID Connect, docs/oidc.md): the app only learns
 * who the person is; it reads nothing in Hubra.
 */
function IdentityConsent({
  data,
  busy,
  error,
  onAnswer,
}: {
  data: authApi.OAuthConsent
  busy: 'allow' | 'deny' | null
  error: string | null
  onAnswer: (allow: boolean) => void
}) {
  const { tr } = useLang()
  const { client, club } = data
  const blocked = club !== null && !club.available
  const shares: string[] = [tr('eine Kennung, die nur diese App kennt', 'an id only this app knows')]
  if (data.oidc.includes('profile')) shares.push(tr('deinen Namen', 'your name'))
  if (data.oidc.includes('email')) shares.push(tr(`deine E-Mail-Adresse (${data.user.email})`, `your email address (${data.user.email})`))
  if (data.oidc.includes('club') && club)
    shares.push(
      tr(
        `deine Mitgliedschaft in ${club.name}: Status, ob du Admin bist, deine Gruppen`,
        `your membership of ${club.name}: status, whether you are an admin, your groups`,
      ),
    )
  return (
    <Stack gap="md">
      <Group gap="sm" wrap="nowrap">
        <ThemeIcon size={48} radius="xl" variant="light">
          <IconLogin2 size={24} />
        </ThemeIcon>
        <div style={{ minWidth: 0 }}>
          <Title order={2} style={{ overflowWrap: 'anywhere' }}>
            {tr(`Bei ${client.name} anmelden`, `Sign in to ${client.name}`)}
          </Title>
          <Text size="sm" c="dimmed">
            {tr(`mit deinem Hubra-Konto, ${data.user.name}`, `with your Hubra account, ${data.user.name}`)}
          </Text>
        </div>
      </Group>
      <AppOrigin client={client} clubName={club?.name} />
      {client.description && <Text size="sm">{client.description}</Text>}
      <Stack gap={4}>
        <Text fw={600} size="sm">
          {tr('Das erfährt die App', 'What the app learns')}
        </Text>
        <List size="sm" spacing={2}>
          {shares.map((s) => (
            <List.Item key={s}>{s}</List.Item>
          ))}
        </List>
        <Text size="xs" c="dimmed">
          {tr(
            'Sie kann in Hubra nichts lesen oder ändern. Du kannst die Anmeldung jederzeit unter Mein Konto › Apps beenden.',
            'It cannot read or change anything in Hubra. You can end the sign-in any time under My account › Apps.',
          )}
        </Text>
      </Stack>
      {blocked && (
        <Alert color="red" variant="light" icon={<IconAlertTriangle size={18} />}>
          {tr(
            `Hier melden sich nur Mitglieder von ${club.name} an. Mit diesem Konto bist du dort kein aktives Mitglied.`,
            `Only members of ${club.name} sign in here. With this account you are not an active member there.`,
          )}
        </Alert>
      )}
      {error && (
        <Alert color="red" variant="light">
          {error}
        </Alert>
      )}
      <Group justify="flex-end">
        <Button variant="default" loading={busy === 'deny'} disabled={busy !== null} onClick={() => onAnswer(false)}>
          {tr('Ablehnen', 'Deny')}
        </Button>
        <Button loading={busy === 'allow'} disabled={busy !== null || blocked} onClick={() => onAnswer(true)}>
          {tr('Anmelden', 'Sign in')}
        </Button>
      </Group>
    </Stack>
  )
}
