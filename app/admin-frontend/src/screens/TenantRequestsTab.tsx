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
import { tr } from '@/lang'
import { formatDate } from '@/format'
import { planLabel } from '@/labels'

const STATUS_COLORS: Record<string, string> = {
  pending: 'yellow',
  approved: 'green',
  rejected: 'red',
}

function requestStatus(status: string) {
  const labels: Record<string, [string, string]> = {
    pending: ['Offen', 'Pending'],
    approved: ['Angenommen', 'Approved'],
    rejected: ['Abgelehnt', 'Rejected'],
  }
  const l = labels[status]
  return l ? tr(l[0], l[1]) : status
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
      notify('success', tr('Anfrage angenommen', 'Request approved'), tr('Der Verein ist eingerichtet.', 'The club has been set up.'))
    },
    onError: (err: Error) => {
      notify('error', tr('Annehmen fehlgeschlagen', 'Approval failed'), err.message)
    },
  })

  const rejectMutation = useMutation({
    mutationFn: ({ id, note }: { id: number; note?: string }) =>
      rejectTenantRequest(id, note),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenant-requests'] })
      notify('success', tr('Anfrage abgelehnt', 'Request rejected'), tr('Die Anfrage wurde abgelehnt.', 'The request has been rejected.'))
      setRejectTarget(null)
      setRejectNote('')
    },
    onError: (err: Error) => {
      notify('error', tr('Ablehnen fehlgeschlagen', 'Reject failed'), err.message)
    },
  })

  const requests = data?.requests ?? []

  return (
    <div>
      <Group justify="flex-end" mb="md">
        <Anchor href={`${SSO_URL}/start`} size="sm" target="_blank" rel="noreferrer">
          {tr('Seite für neue Vereine', 'Request page')}
        </Anchor>
      </Group>

      <Paper withBorder style={{ overflow: 'hidden' }}>
        {isLoading && (
          <Text p={40} ta="center" c="dimmed">
            {tr('Anfragen werden geladen …', 'Loading requests…')}
          </Text>
        )}

        {!isLoading && requests.length === 0 && (
          <Text p={40} ta="center" c="dimmed">
            {tr('Noch keine Anfragen.', 'No requests yet.')}
          </Text>
        )}

        {requests.length > 0 && (
          <Table.ScrollContainer minWidth={640}>
          <Table highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{tr('Name', 'Name')}</Table.Th>
                <Table.Th>{tr('Kürzel', 'Slug')}</Table.Th>
                <Table.Th>{tr('Plan', 'Plan')}</Table.Th>
                <Table.Th>{tr('Status', 'Status')}</Table.Th>
                <Table.Th>{tr('Erstellt', 'Created')}</Table.Th>
                {canReview && <Table.Th>{tr('Aktionen', 'Actions')}</Table.Th>}
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {requests.map((r: TenantRequest) => (
                <Table.Tr key={r.id}>
                  <Table.Td fw={600}>{r.name}</Table.Td>
                  <Table.Td className="num" fz="sm" c="dimmed">
                    {r.slug}
                  </Table.Td>
                  <Table.Td>
                    <Badge variant="light" color="acc" size="sm">
                      {planLabel(r.plan, tr)}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Badge variant="light" color={STATUS_COLORS[r.status] ?? 'gray'} size="sm">
                      {requestStatus(r.status)}
                    </Badge>
                  </Table.Td>
                  <Table.Td fz="sm" c="dimmed">
                    {r.created_at ? formatDate(r.created_at) : '–'}
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
                            {tr('Annehmen', 'Approve')}
                          </Button>
                          <Button
                            size="xs"
                            color="red"
                            variant="light"
                            onClick={() => setRejectTarget(r)}
                          >
                            {tr('Ablehnen', 'Reject')}
                          </Button>
                        </Group>
                      )}
                    </Table.Td>
                  )}
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
          </Table.ScrollContainer>
        )}
      </Paper>

      <Modal
        opened={!!rejectTarget}
        onClose={() => { setRejectTarget(null); setRejectNote('') }}
        title={tr('Anfrage ablehnen', 'Reject request')}
        size="md"
      >
        <Stack gap={16}>
          <Text size="sm" c="dimmed">
            {tr(
              `Du lehnst «${rejectTarget?.name}» (${rejectTarget?.slug}) ab. Die Person kann danach eine neue Anfrage mit einem anderen Kürzel stellen.`,
              `You are rejecting "${rejectTarget?.name}" (${rejectTarget?.slug}). The requester can then send a new request with a different slug.`,
            )}
          </Text>
          <TextInput
            label={tr('Notiz (optional)', 'Note (optional)')}
            value={rejectNote}
            onChange={(e) => setRejectNote(e.target.value)}
            placeholder={tr('Grund für die Ablehnung', 'Reason for rejection')}
          />
          <Group justify="flex-end" mt={8}>
            <Button variant="default" onClick={() => { setRejectTarget(null); setRejectNote('') }}>
              {tr('Abbrechen', 'Cancel')}
            </Button>
            <Button
              color="red"
              loading={rejectMutation.isPending}
              onClick={() => rejectTarget && rejectMutation.mutate({ id: rejectTarget.id, note: rejectNote || undefined })}
            >
              {tr('Anfrage ablehnen', 'Reject request')}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </div>
  )
}
