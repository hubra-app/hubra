import { useQuery } from '@tanstack/react-query'
import { Box, Group, Paper, Stack, Text, Button, Loader, Center } from '@mantine/core'
import { IconArrowRight } from '@tabler/icons-react'
import { PageHead } from '@/components/ui'
import { getMyTenants, type MyTenant } from '@/api/tenants'

const COS_URL = import.meta.env.VITE_COS_URL ?? 'https://cos.vollbuild.ch'

export function MyTenantsTab() {
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
        <PageHead eyebrow="Spaces" title="My Spaces" />
        <Paper withBorder p="xl" radius="md">
          <Stack align="center" gap="sm">
            <Text c="dimmed">You are not a member of any spaces yet.</Text>
            <Text size="sm" c="dimmed">
              Request a space from the Requests tab, or ask an administrator to add you.
            </Text>
          </Stack>
        </Paper>
      </div>
    )
  }

  return (
    <div>
      <PageHead eyebrow="Spaces" title="My Spaces" />
      <Stack gap="sm">
        {tenants.map((t) => (
          <Paper key={t.tenant_id} withBorder radius="md" p="md">
            <Group justify="space-between">
              <Box>
                <Text fw={600}>{t.tenant_name ?? t.tenant_slug ?? `Tenant ${t.tenant_id}`}</Text>
                <Text fz="xs" c="dimmed">
                  {t.tenant_slug}
                </Text>
              </Box>
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
          </Paper>
        ))}
      </Stack>
    </div>
  )
}
