import { useQuery } from '@tanstack/react-query'
import {
  Avatar,
  Badge,
  Button,
  Center,
  Group,
  Loader,
  Paper,
  SimpleGrid,
  Stack,
  Text,
  ThemeIcon,
  Title,
} from '@mantine/core'
import { IconArrowRight, IconBuildingCommunity, IconPlus, IconUsers } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import { SSO_URL, clubLogoUrl } from '@hubra/api-client'
import { PageHead } from '@/components/ui'
import { getMyTenants, type MyTenant } from '@/api/tenants'
import { useLang } from '@/lang'

const COS_URL = import.meta.env.VITE_COS_URL ?? 'https://app.hubra.club'

function clubName(t: MyTenant) {
  return t.tenant_name ?? t.tenant_slug ?? `#${t.tenant_id}`
}

export function MyTenantsTab() {
  const navigate = useNavigate()
  const { tr } = useLang()
  const { data, isLoading } = useQuery<{ tenants: MyTenant[] }>({
    queryKey: ['my-tenants'],
    queryFn: getMyTenants,
  })

  const actions = (
    <>
      <Button component="a" href={`${SSO_URL}/start`} leftSection={<IconPlus size={16} />}>
        {tr('Verein gründen', 'Start a club')}
      </Button>
    </>
  )

  const head = (
    <PageHead
      title={tr('Deine Vereine verwalten', 'Clubs you run')}
      desc={tr(
        'Admins der Vereine, die du leitest. Alles andere stellst du im Verein selbst ein.',
        'Admins of the clubs you run. Everything else is set inside the club.',
      )}
      actions={actions}
    />
  )

  if (isLoading) {
    return (
      <>
        {head}
        <Center py="xl">
          <Loader />
        </Center>
      </>
    )
  }

  // Clubs someone is only a member of are opened from «Meine Vereine».
  const tenants = (data?.tenants ?? []).filter((t) => t.admin_level)

  if (tenants.length === 0) {
    return (
      <>
        {head}
        <Paper withBorder p="xl">
          <Stack align="center" gap="sm" py="lg" ta="center">
            <ThemeIcon size={52} radius="xl" variant="light">
              <IconBuildingCommunity size={26} />
            </ThemeIcon>
            <Title order={3}>{tr('Du leitest noch keinen Verein', 'You do not run a club yet')}</Title>
            <Text c="dimmed" maw={420}>
              {tr(
                'Gründe einen Verein auf Hubra. Vereine, in denen du Mitglied bist, öffnest du unter «Meine Vereine».',
                'Start a club on Hubra. Clubs you are a member of open from «My clubs».',
              )}
            </Text>
          </Stack>
        </Paper>
      </>
    )
  }

  return (
    <>
      {head}
      <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="md">
        {tenants.map((t) => (
          <Paper key={t.tenant_id} withBorder p="lg">
            <Stack gap="lg">
              <Group gap="md" wrap="nowrap">
                <Avatar
                  size={48}
                  radius="md"
                  color="acc"
                  variant="light"
                  src={clubLogoUrl(t.tenant_slug, t.logo_version)}
                  alt=""
                  styles={{ image: { objectFit: 'contain' } }}
                >
                  {clubName(t).slice(0, 2).toUpperCase()}
                </Avatar>
                <div style={{ minWidth: 0, flex: 1 }}>
                  <Group gap={8} wrap="nowrap">
                    <Text fw={700} fz="lg" truncate>
                      {clubName(t)}
                    </Text>
                    {t.admin_level && (
                      <Badge size="xs" variant="light" style={{ flexShrink: 0 }}>
                        {t.admin_level === 'owner' ? tr('Inhaber', 'Owner') : tr('Admin', 'Admin')}
                      </Badge>
                    )}
                  </Group>
                </div>
              </Group>
              <Group gap="xs" grow>
                {t.admin_level && (
                  <Button
                    variant="default"
                    leftSection={<IconUsers size={16} />}
                    onClick={() => navigate(`/app/clubs/${t.tenant_id}/admins`)}
                  >
                    {tr('Admins', 'Admins')}
                  </Button>
                )}
                <Button
                  variant="light"
                  rightSection={<IconArrowRight size={16} />}
                  disabled={!t.tenant_slug}
                  onClick={() => {
                    window.location.assign(`${COS_URL}/${t.tenant_slug}/app/dashboard`)
                  }}
                >
                  {tr('Verein öffnen', 'Open club')}
                </Button>
              </Group>
            </Stack>
          </Paper>
        ))}
      </SimpleGrid>
    </>
  )
}
