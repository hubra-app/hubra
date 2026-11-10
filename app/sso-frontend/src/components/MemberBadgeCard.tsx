import { Avatar, Badge, Group, Paper, Skeleton, Stack, Text, UnstyledButton } from '@mantine/core'
import { useMutation, useQuery } from '@tanstack/react-query'
import { IconId } from '@tabler/icons-react'
import { clubLogoUrl } from '@hubra/api-client'
import { getLang, tr } from '@/lang'
import * as authApi from '@/api/auth'
import type { BadgeMembership } from '@/api/auth'

const TYPES: Record<string, () => string> = {
  honorary: () => tr('Ehrenmitglied', 'Honorary member'),
  passive: () => tr('Passivmitglied', 'Passive member'),
  trial: () => tr('Probemitglied', 'Trial member'),
}

const STATUS: Record<string, { label: () => string; color: string }> = {
  trial: { label: () => tr('Probezeit', 'Trial'), color: 'blue' },
  inactive: { label: () => tr('Inaktiv', 'Inactive'), color: 'gray' },
  suspended: { label: () => tr('Gesperrt', 'Suspended'), color: 'red' },
}

function day(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(getLang() === 'en' ? 'en-GB' : 'de-CH', {
    dateStyle: 'medium',
  })
}

function initials(name: string): string {
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((p) => p[0])
      .join('')
      .toUpperCase() || '?'
  )
}

function Membership({ m }: { m: BadgeMembership }) {
  // A club may already name the kind in its tier ("Ehrenmitglied").
  const type =
    TYPES[m.membershipType] && TYPES[m.membershipType]() !== m.tier?.name
      ? TYPES[m.membershipType]
      : undefined
  const status = STATUS[m.status]
  return (
    <Group gap="sm" wrap="nowrap" align="center" className="member-badge-club">
      <Avatar
        radius="md"
        size={36}
        color="acc"
        variant="light"
        src={clubLogoUrl(m.club.slug, m.club.logoVersion)}
        alt=""
        styles={{ image: { objectFit: 'contain' } }}
      >
        {m.club.name.slice(0, 2).toUpperCase()}
      </Avatar>
      <div style={{ flex: 1, minWidth: 0 }}>
        <Text size="sm" fw={600} truncate>
          {m.club.name}
        </Text>
        <Text size="xs" c="dimmed">
          {m.joined ? tr(`Mitglied seit ${day(m.joined)}`, `Member since ${day(m.joined)}`) : ''}
          {m.until ? ` · ${tr(`bis ${day(m.until)}`, `until ${day(m.until)}`)}` : ''}
        </Text>
      </div>
      <Group gap={4} wrap="wrap" justify="flex-end" style={{ flexShrink: 1 }}>
        {m.tier && (
          <Badge
            variant="light"
            color={m.tier.color ?? 'acc'}
            style={{ maxWidth: 160 }}
            title={m.tier.name}
          >
            {m.tier.name}
          </Badge>
        )}
        {type && (
          <Badge variant="outline" color="gold">
            {type()}
          </Badge>
        )}
        {status && (
          <Badge variant="light" color={status.color}>
            {status.label()}
          </Badge>
        )}
      </Group>
    </Group>
  )
}

/**
 * Google's own "Add to Google Wallet" button (black, not to be restyled; see
 * developers.google.com/wallet/generic/resources/brand-guidelines). The
 * click writes the pass and opens Google's save page.
 */
function GoogleWalletButton() {
  const add = useMutation({
    mutationFn: authApi.addBadgeToGoogleWallet,
    onSuccess: ({ url }) => {
      window.location.href = url
    },
  })
  const lang = getLang() === 'en' ? 'en' : 'de'
  const label = tr('Zu Google Wallet hinzufügen', 'Add to Google Wallet')
  return (
    <Stack gap={4} align="flex-start" className="member-badge-wallet">
      <UnstyledButton
        onClick={() => add.mutate()}
        disabled={add.isPending}
        aria-label={label}
        aria-busy={add.isPending}
        style={{ padding: 8, margin: -8, opacity: add.isPending ? 0.6 : 1, maxWidth: '100%' }}
      >
        {/* Scaled as a whole (never stretched); 48 px high where it fits. */}
        <img
          src={`/google-wallet/add-${lang}.svg`}
          alt={label}
          style={{ display: 'block', width: lang === 'en' ? 281 : 352, maxWidth: '100%', height: 'auto' }}
        />
      </UnstyledButton>
      {add.isError && (
        <Text size="xs" c="red">
          {tr(
            'Google Wallet ist gerade nicht erreichbar. Bitte später nochmals versuchen.',
            'Google Wallet is not reachable right now. Please try again later.',
          )}
        </Text>
      )}
    </Stack>
  )
}

/**
 * The person's member badge: one per person, the same number in every club,
 * with their memberships (tier, kind, since when) below it.
 */
export function MemberBadgeCard() {
  const badge = useQuery({ queryKey: ['badge'], queryFn: authApi.getBadge })
  if (badge.isError) return null
  if (!badge.data) return <Skeleton h={168} radius="md" />
  const b = badge.data

  return (
    <Paper withBorder radius="md" className="member-badge" aria-label={tr('Mitgliederausweis', 'Member badge')}>
      <div className="member-badge-head">
        <Avatar size={64} radius="xl" color={b.avatarColor} variant="filled" className="member-badge-avatar">
          {initials(b.name)}
        </Avatar>
        <div className="member-badge-text" style={{ minWidth: 0, flex: 1 }}>
          <Group gap={6} c="var(--member-badge-dim)">
            <IconId size={14} />
            <Text size="xs" fw={600} tt="uppercase" style={{ letterSpacing: '0.08em' }}>
              {tr('Mitgliederausweis', 'Member badge')}
            </Text>
          </Group>
          <Text fw={700} fz={22} lh={1.2} truncate>
            {b.name}
          </Text>
          <Text className="member-badge-code" aria-label={tr('Ausweisnummer', 'Badge number')}>
            {b.code}
          </Text>
        </div>
        <img
          className="member-badge-qr"
          src={`data:image/svg+xml;utf8,${encodeURIComponent(b.qrSvg)}`}
          alt={tr(`QR-Code der Ausweisnummer ${b.code}`, `QR code of badge number ${b.code}`)}
          width={96}
          height={96}
        />
      </div>
      <Stack gap="sm" p="md">
        {b.memberships.length === 0 ? (
          <Text size="sm" c="dimmed">
            {tr('Noch in keinem Verein.', 'Not in a club yet.')}
          </Text>
        ) : (
          b.memberships.map((m) => <Membership key={m.club.slug} m={m} />)
        )}
        <Text size="xs" c="dimmed">
          {tr(
            'Eine Nummer für dich, gleich in allen deinen Vereinen.',
            'One number for you, the same in all your clubs.',
          )}
          {b.since ? ` ${tr(`Bei Hubra seit ${day(b.since)}.`, `On Hubra since ${day(b.since)}.`)}` : ''}
        </Text>
        {b.googleWallet && <GoogleWalletButton />}
      </Stack>
    </Paper>
  )
}
