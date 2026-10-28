import { useQuery } from '@tanstack/react-query'
import { Badge, Box, Group, Paper, Stack, Text, Button, Loader, Center } from '@mantine/core'
import { IconArrowRight, IconSearch, IconUsers } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import { SSO_URL } from '@hubra/api-client'
import { PageHead } from '@/components/ui'
import { getMyTenants, type MyTenant } from '@/api/tenants'

const COS_URL = import.meta.env.VITE_COS_URL ?? 'https://app.hubra.club'

export function MyTenantsTab() {
  const navigate = useNavigate()
  const { data, isLoading } = useQuery<{ tenants: MyTenant[] }>({
    queryKey: ['my-tenants'],
    queryFn: getMyTenants,
  })

  if (isLoading) {
    return (
      <Center>
        <Loader />
      </Center>
    )
  }

  const tenants = data?.tenants ?? []

  if (tenants.length === 0) {
    return (
      <div>
        <PageHead eyebrow="Clubs" title="My Clubs" />
        <Paper withBorder p="xl" radius="md">
          <Stack align="center" gap="sm">
            <Text c="dimmed">You are not a member of a club yet.</Text>
            <Group gap="sm" justify="center">
              <Button
                component="a"
                href={`${SSO_URL}/clubs`}
                leftSection={<IconSearch size={16} />}
              >
                Find a club
              </Button>
              <Button variant="default" onClick={() => navigate('/app/requests')}>
                Request a new club
              </Button>
            </Group>
          </Stack>
        </Paper>
      </div>
    )
  }

  return (
    <div>
      <PageHead eyebrow="Clubs" title="My Clubs" />
      <Stack gap="sm">
        {tenants.map((t) => (
          <Paper key={t.tenant_id} withBorder radius="md" p="md">
            <Group justify="space-between">
              <Box>
                <Group gap={8}>
                  <Text fw={600}>{t.tenant_name ?? t.tenant_slug ?? `Tenant ${t.tenant_id}`}</Text>
                  {t.admin_level && (
                    <Badge size="xs" variant="light" color="violet">
                      {t.admin_level === 'owner' ? 'Owner' : 'Admin'}
                    </Badge>
                  )}
                </Group>
                <Text fz="xs" c="dimmed">
                  {t.tenant_slug}
                </Text>
              </Box>
              <Group gap="xs">
                {t.admin_level && (
                  <Button
                    variant="default"
                    leftSection={<IconUsers size={16} />}
                    onClick={() => navigate(`/app/clubs/${t.tenant_id}/admins`)}
                  >
                    Admins
                  </Button>
                )}
                <Button
                  variant="light"
                  rightSection={<IconArrowRight size={16} />}
                  onClick={() => {
                    window.location.assign(`${COS_URL}/${t.tenant_slug}/app/dashboard`)
                  }}
                >
                  Enter
                </Button>
              </Group>
            </Group>
          </Paper>
        ))}
      </Stack>
    </div>
  )
}
