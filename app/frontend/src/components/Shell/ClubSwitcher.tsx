import { useMemo, useState } from 'react'
import { Box, Group, Menu, Text, TextInput, UnstyledButton } from '@mantine/core'
import { IconCheck, IconSearch, IconSelector, IconWorldSearch } from '@tabler/icons-react'
import { clubLogoUrl } from '@hubra/api-client'
import { useT } from '@/locales/i18n'
import { useAuth, useData } from '@/context/AppContext'
import { useInstance } from '@/context/InstanceContext'
import { useClubLogo, useClubProfile } from '@/data/clubProfile'
import { useMyTenants } from '@/data/lists'
import { URL_CLUB } from '@/clubBase'
import { initials } from './nav'

// From this many clubs on, the list gets a filter field.
const FILTER_FROM = 7

/** The club's logo, or its initials on a tile while it has none. */
function ClubBadge({ name, logo, size }: { name: string; logo?: string; size: number }) {
  if (logo)
    return (
      <img
        src={logo}
        alt=""
        style={{ width: size, height: size, objectFit: 'contain', flexShrink: 0, borderRadius: 6 }}
      />
    )
  return (
    <Box
      aria-hidden
      style={{
        width: size,
        height: size,
        flexShrink: 0,
        borderRadius: 8,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--mantine-primary-color-light)',
        color: 'var(--mantine-primary-color-light-color)',
        fontSize: Math.round(size * 0.4),
        fontWeight: 700,
      }}
    >
      {initials(name)}
    </Box>
  )
}

/**
 * The current club in the top bar: its logo and name, and a menu to open
 * another of the member's clubs or find one to join (the SSO club picker).
 */
export function ClubSwitcher() {
  const { t } = useT()
  const { tenantSlug } = useAuth()
  const { switchTenant } = useData()
  const { ssoUrl } = useInstance()
  const { data: club } = useClubProfile()
  const logo = useClubLogo()
  const tenants = useMyTenants()
  const [filter, setFilter] = useState('')

  const current = tenantSlug ?? URL_CLUB
  const name = club?.club_name ?? tenants.find((x) => x.tenant_slug === current)?.tenant_name ?? ''

  const shown = useMemo(() => {
    const q = filter.trim().toLowerCase()
    const list = [...tenants].sort((a, b) =>
      (a.tenant_name ?? a.tenant_slug ?? '').localeCompare(b.tenant_name ?? b.tenant_slug ?? ''),
    )
    if (!q) return list
    return list.filter((x) =>
      `${x.tenant_name ?? ''} ${x.tenant_slug ?? ''}`.toLowerCase().includes(q),
    )
  }, [tenants, filter])

  // The profile isn't there yet: the Hubra mark, as before.
  if (!name) {
    return (
      <Group gap={8} wrap="nowrap" style={{ flexShrink: 0 }}>
        <div className="logo-mark" />
        <Text fz={22} className="wordmark mantine-visible-from-xs">
          hubra
        </Text>
      </Group>
    )
  }

  return (
    <Menu
      position="bottom-start"
      width={300}
      shadow="lg"
      radius="md"
      withinPortal
      onClose={() => setFilter('')}
    >
      <Menu.Target>
        <UnstyledButton
          data-testid="club-switcher"
          aria-label={t('shell.clubSwitcher.label', 'Verein wechseln, aktuell: {{name}}', { name })}
          className="hubra-club-switcher"
        >
          <ClubBadge name={name} logo={logo} size={32} />
          <Text fz="md" fw={700} truncate className="hubra-club-switcher-name">
            {name}
          </Text>
          <IconSelector size={16} style={{ flexShrink: 0, color: 'var(--mantine-color-dimmed)' }} />
        </UnstyledButton>
      </Menu.Target>

      <Menu.Dropdown data-testid="club-switcher-menu" style={{ maxWidth: 'calc(100vw - 16px)' }}>
        <Menu.Label>{t('shell.clubSwitcher.yourClubs', 'Deine Vereine')}</Menu.Label>
        {tenants.length >= FILTER_FROM && (
          <Box px={6} pb={6}>
            <TextInput
              size="xs"
              value={filter}
              onChange={(e) => setFilter(e.currentTarget.value)}
              placeholder={t('shell.clubSwitcher.filter', 'Verein suchen')}
              leftSection={<IconSearch size={14} />}
              aria-label={t('shell.clubSwitcher.filter', 'Verein suchen')}
              // Arrow keys and typing stay in the field, not the menu.
              onKeyDown={(e) => e.stopPropagation()}
            />
          </Box>
        )}
        <Box style={{ maxHeight: 320, overflowY: 'auto' }}>
          {shown.map((x) => {
            const slug = x.tenant_slug
            const label = x.tenant_name ?? slug ?? ''
            const isCurrent = slug === current
            const role =
              x.admin_level === 'owner'
                ? t('shell.clubSwitcher.owner', 'Inhaber/in')
                : x.admin_level === 'admin'
                  ? t('shell.clubSwitcher.admin', 'Admin')
                  : null
            return (
              <Menu.Item
                key={slug ?? label}
                aria-current={isCurrent ? 'true' : undefined}
                onClick={() => {
                  if (slug && !isCurrent) switchTenant(slug)
                }}
                leftSection={
                  <ClubBadge
                    name={label}
                    logo={isCurrent ? logo : clubLogoUrl(slug, x.logo_version)}
                    size={28}
                  />
                }
                rightSection={
                  isCurrent ? (
                    <IconCheck size={16} color="var(--mantine-primary-color-filled)" />
                  ) : undefined
                }
                style={isCurrent ? { background: 'var(--mantine-primary-color-light)' } : undefined}
              >
                <Text fz="sm" fw={isCurrent ? 600 : 500} truncate>
                  {label}
                </Text>
                {role && (
                  <Text fz="xs" c="dimmed" lh={1.2}>
                    {role}
                  </Text>
                )}
              </Menu.Item>
            )
          })}
          {shown.length === 0 && (
            <Text fz="sm" c="dimmed" px="sm" py={6}>
              {t('shell.clubSwitcher.noMatch', 'Kein Verein gefunden')}
            </Text>
          )}
        </Box>
        <Menu.Divider />
        <Menu.Item
          component="a"
          href={`${ssoUrl}/clubs`}
          leftSection={<IconWorldSearch size={16} />}
        >
          {t('shell.clubSwitcher.find', 'Weiteren Verein finden')}
        </Menu.Item>
      </Menu.Dropdown>
    </Menu>
  )
}
