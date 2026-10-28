import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Badge,
  Button,
  Center,
  Group,
  Loader,
  Paper,
  SegmentedControl,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { IconArrowLeft, IconUserMinus, IconUserPlus } from '@tabler/icons-react'
import { PageHead } from '@/components/ui'
import { useAdmin } from '@/context/AdminContext'
import { addClubAdmin, getClubAdmins, removeClubAdmin, type ClubAdmin } from '@/api/tenants'

/**
 * Who administers a club. The club's own owners and admins manage this
 * themselves; platform managers can for any club. Only owners (and the
 * platform) name or remove owners, and the last owner stays.
 */
export function ClubAdminsPanel({ tenantId }: { tenantId: number }) {
  const { notify } = useAdmin()
  const queryClient = useQueryClient()
  const { data, isLoading, error } = useQuery({
    queryKey: ['club-admins', tenantId],
    queryFn: () => getClubAdmins(tenantId),
  })
  const [email, setEmail] = useState('')
  const [level, setLevel] = useState<'admin' | 'owner'>('admin')
  const [busy, setBusy] = useState(false)

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['club-admins', tenantId] })

  const add = async () => {
    setBusy(true)
    try {
      await addClubAdmin(tenantId, email.trim(), level)
      notify('success', level === 'owner' ? 'Owner added' : 'Admin added', email.trim())
      setEmail('')
      await refresh()
    } catch (err) {
      notify('error', 'Could not add', err instanceof Error ? err.message : undefined)
    } finally {
      setBusy(false)
    }
  }

  const remove = async (a: ClubAdmin) => {
    try {
      await removeClubAdmin(tenantId, a.user_id)
      notify('success', 'Removed', `${a.email} stays a member of the club.`)
      await refresh()
    } catch (err) {
      notify('error', 'Could not remove', err instanceof Error ? err.message : undefined)
    }
  }

  const owners = data?.admins.filter((a) => a.level === 'owner').length ?? 0

  return (
    <Paper withBorder shadow="sm" radius="lg" p="lg" mb={20}>
      <Stack gap={4} mb={12}>
        <Title order={3}>Admins</Title>
        <Text size="sm" c="dimmed">
          Admins run the club. Owners can also name and remove other owners; a club always keeps at
          least one owner. Removing someone here keeps them as a member.
        </Text>
      </Stack>

      {isLoading ? (
        <Text size="sm" c="dimmed">
          Loading…
        </Text>
      ) : error || !data ? (
        <Text size="sm" c="red">
          {error instanceof Error ? error.message : 'Could not load the admins.'}
        </Text>
      ) : (
        <>
          <Table verticalSpacing="xs" mb="md">
            <Table.Tbody>
              {data.admins.map((a) => {
                const locked = a.level === 'owner' && (!data.canManageOwners || owners <= 1)
                return (
                  <Table.Tr key={a.user_id}>
                    <Table.Td>
                      <Text size="sm" fw={600}>
                        {a.name || a.email}
                      </Text>
                      <Text size="xs" c="dimmed">
                        {a.email}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Badge
                        size="sm"
                        variant={a.level === 'owner' ? 'filled' : 'light'}
                        color="violet"
                      >
                        {a.level === 'owner' ? 'Owner' : 'Admin'}
                      </Badge>
                    </Table.Td>
                    <Table.Td style={{ textAlign: 'right' }}>
                      <Button
                        size="xs"
                        variant="subtle"
                        color="red"
                        leftSection={<IconUserMinus size={14} />}
                        disabled={locked}
                        title={
                          locked
                            ? owners <= 1
                              ? 'A club needs at least one owner'
                              : 'Only an owner can remove an owner'
                            : undefined
                        }
                        onClick={() => remove(a)}
                      >
                        Remove
                      </Button>
                    </Table.Td>
                  </Table.Tr>
                )
              })}
            </Table.Tbody>
          </Table>

          <Group align="flex-end" wrap="wrap">
            <TextInput
              label="Add by email"
              description="They need a Hubra account. If they are not a member yet, they become one."
              placeholder="name@example.com"
              value={email}
              onChange={(e) => setEmail(e.currentTarget.value)}
              style={{ flex: 1, minWidth: 240 }}
            />
            {data.canManageOwners && (
              <SegmentedControl
                value={level}
                onChange={(v) => setLevel(v as 'admin' | 'owner')}
                data={[
                  { value: 'admin', label: 'Admin' },
                  { value: 'owner', label: 'Owner' },
                ]}
              />
            )}
            <Button
              leftSection={<IconUserPlus size={16} />}
              loading={busy}
              disabled={!email.includes('@')}
              onClick={add}
            >
              Add
            </Button>
          </Group>
        </>
      )}
    </Paper>
  )
}

/** /app/clubs/:id/admins — a club admin's page for their own club. */
export function ClubAdmins() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const tenantId = Number(id)
  const { data, isLoading } = useQuery({
    queryKey: ['club-admins', tenantId],
    queryFn: () => getClubAdmins(tenantId),
    enabled: Number.isFinite(tenantId),
  })

  if (isLoading)
    return (
      <Center>
        <Loader />
      </Center>
    )

  return (
    <div>
      <Button
        variant="subtle"
        size="xs"
        leftSection={<IconArrowLeft size={14} />}
        onClick={() => navigate('/app/my-tenants')}
        mb={8}
      >
        My Clubs
      </Button>
      <PageHead eyebrow="Club admin" title={data?.club.name ?? 'Club'} />
      <ClubAdminsPanel tenantId={tenantId} />
    </div>
  )
}
