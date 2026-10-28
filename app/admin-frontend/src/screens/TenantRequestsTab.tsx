import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Table,
  Paper,
  Badge,
  Button,
  Group,
  Text,
  Modal,
  TextInput,
  Stack,
  Anchor,
} from '@mantine/core'
import { SSO_URL } from '@hubra/api-client'
import {
  listTenantRequests,
  approveTenantRequest,
  rejectTenantRequest,
  type TenantRequest,
} from '@/api/tenants'
import { useAdmin } from '@/context/AdminContext'

const STATUS_COLORS: Record<string, string> = {
  pending: 'yellow',
  approved: 'green',
  rejected: 'red',
}

/**
 * New clubs people asked for, for platform staff to review. People ask for
 * a club on the SSO site (/start), not here.
 */
export function TenantRequestsTab() {
  const { hasGlobalPermission, notify } = useAdmin()
  const queryClient = useQueryClient()
  const [rejectTarget, setRejectTarget] = useState<TenantRequest | null>(null)
  const [rejectNote, setRejectNote] = useState('')
  const canReview = hasGlobalPermission('requests.approve')

  const { data, isLoading } = useQuery({
    queryKey: ['tenant-requests'],
    queryFn: () => listTenantRequests(),
  })

  const approveMutation = useMutation({
    mutationFn: (id: number) => approveTenantRequest(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenant-requests'] })
      queryClient.invalidateQueries({ queryKey: ['tenants'] })
      notify('success', 'Request approved', 'Tenant has been provisioned.')
    },
    onError: (err: Error) => {
      notify('error', 'Approval failed', err.message)
    },
  })

  const rejectMutation = useMutation({
    mutationFn: ({ id, note }: { id: number; note?: string }) =>
      rejectTenantRequest(id, note),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenant-requests'] })
      notify('success', 'Request rejected', 'The tenant request has been rejected.')
      setRejectTarget(null)
      setRejectNote('')
    },
    onError: (err: Error) => {
      notify('error', 'Reject failed', err.message)
    },
  })

  const requests = data?.requests ?? []

  return (
    <div>
      <Group justify="space-between" mb={16}>
        <Text fw={600} size="lg">
          Club Requests
        </Text>
        <Anchor href={`${SSO_URL}/start`} size="sm" target="_blank" rel="noreferrer">
          Request page
        </Anchor>
      </Group>

      <Paper withBorder shadow="sm" radius="lg">
        {isLoading && (
          <Text p={40} ta="center" c="dimmed">
            Loading requests...
          </Text>
        )}

        {!isLoading && requests.length === 0 && (
          <Text p={40} ta="center" c="dimmed">
            No tenant requests.
          </Text>
        )}

        {requests.length > 0 && (
          <Table highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Name</Table.Th>
                <Table.Th>Slug</Table.Th>
                <Table.Th>Plan</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Created</Table.Th>
                {canReview && <Table.Th>Actions</Table.Th>}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {requests.map((r: TenantRequest) => (
                <Table.Tr key={r.id}>
                  <Table.Td fw={600}>{r.name}</Table.Td>
                  <Table.Td style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 14 }}>
                    {r.slug}
                  </Table.Td>
                  <Table.Td>
                    <Badge variant="light" color="blue" size="sm">
                      {r.plan}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Badge variant="light" color={STATUS_COLORS[r.status] ?? 'gray'} size="sm">
                      {r.status}
                    </Badge>
                  </Table.Td>
                  <Table.Td style={{ color: '#5e5873', fontSize: 14 }}>
                    {r.created_at ? new Date(r.created_at).toLocaleDateString() : '-'}
                  </Table.Td>
                  {canReview && (
                    <Table.Td>
                      {r.status === 'pending' && (
                        <Group gap="xs">
                          <Button
                            size="xs"
                            color="green"
                            variant="light"
                            loading={approveMutation.isPending}
                            onClick={() => approveMutation.mutate(r.id)}
                          >
                            Approve
                          </Button>
                          <Button
                            size="xs"
                            color="red"
                            variant="light"
                            onClick={() => setRejectTarget(r)}
                          >
                            Reject
                          </Button>
                        </Group>
                      )}
                    </Table.Td>
                  )}
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Paper>

      <Modal
        opened={!!rejectTarget}
        onClose={() => { setRejectTarget(null); setRejectNote('') }}
        title="Reject Tenant Request"
        size="md"
      >
        <Stack gap={16}>
          <Text size="sm" c="dimmed">
            Rejecting <strong>{rejectTarget?.name}</strong> ({rejectTarget?.slug}).
            The requester will be able to submit a new request with a different slug.
          </Text>
          <TextInput
            label="Note (optional)"
            value={rejectNote}
            onChange={(e) => setRejectNote(e.target.value)}
            placeholder="Reason for rejection"
          />
          <Group justify="flex-end" mt={8}>
            <Button variant="default" onClick={() => { setRejectTarget(null); setRejectNote('') }}>
              Cancel
            </Button>
            <Button
              color="red"
              loading={rejectMutation.isPending}
              onClick={() => rejectTarget && rejectMutation.mutate({ id: rejectTarget.id, note: rejectNote || undefined })}
            >
              Reject Request
            </Button>
          </Group>
        </Stack>
      </Modal>
    </div>
  )
}
