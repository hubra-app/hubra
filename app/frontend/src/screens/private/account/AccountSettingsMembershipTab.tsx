import { Badge, Group, Paper, Text } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { IconBuildingBank } from '@tabler/icons-react'
import * as authApi from '@/api/auth'
import { useAuth } from '@/context/AppContext'
import { LastSeenBadge } from '@/components/ui'
import { useT } from '@/locales/i18n'
import { PaymentPlanCard } from './PaymentPlanCard'

export function AccountSettingsMembershipTab() {
  const { t } = useT()
  const { currentUser } = useAuth()
  const myGroupsQuery = useQuery({
    queryKey: ['my-groups'],
    queryFn: () => authApi.getMyGroups(),
  })
  const myGroups = myGroupsQuery.data ?? []

  return (
    <>
      <Paper withBorder shadow="sm" radius="lg">
        <Group
          p="md"
          gap="sm"
          style={{
            borderBottom: '1px solid var(--mantine-color-gray-3)',
          }}
        >
          <IconBuildingBank
            size={16}
            style={{ color: 'var(--mantine-color-ink-4)' }}
          />
          <Text fw={700} fz="md">
            {t('account.membership.details', 'Mitgliedschaft-Datene')}
          </Text>
        </Group>
        <div style={{ padding: '4px 0' }}>
          {[
            {
              label: t('account.currentTier', 'Aktuelli Stuf'),
              value: currentUser?.tier ?? '?',
            },
            {
              label: t('account.memberSince', 'Mitglid siit'),
              value: currentUser?.joined ?? '?',
            },
            {
              label: t('common.roles', 'Roll'),
              value: currentUser?.roles?.join(', ') ?? '?',
            },
            {
              label: t('account.toolHours', 'Wärchzeug-Stunde'),
              value: `${currentUser?.toolHours ?? 0} h`,
            },
            {
              label: t('common.status', 'Status'),
              value: currentUser?.status ?? '?',
            },
          ].map(({ label, value }) => (
            <div
              key={label}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                padding: '13px 24px',
                borderBottom: '1px solid #f1eff7',
              }}
            >
              <span
                style={{
                  fontSize: 'var(--mantine-font-size-sm)',
                  color: 'var(--mantine-color-ink-4)',
                }}
              >
                {label}
              </span>
              <span
                style={{
                  fontSize: 'var(--mantine-font-size-sm)',
                  fontWeight: 500,
                  color: 'var(--mantine-color-ink-8)',
                }}
              >
                {value}
              </span>
            </div>
          ))}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              padding: '13px 24px',
            }}
          >
            <span
              style={{
                fontSize: 'var(--mantine-font-size-sm)',
                color: 'var(--mantine-color-ink-4)',
              }}
            >
              {t('account.lastSeen', 'Zuletzt gseh')}
            </span>
            <span
              style={{
                fontSize: 'var(--mantine-font-size-sm)',
                fontWeight: 500,
                color: 'var(--mantine-color-ink-8)',
              }}
            >
              <LastSeenBadge lastSeen={currentUser?.lastSeen ?? ''} />
            </span>
          </div>
        </div>
      </Paper>

      <Paper withBorder shadow="sm" radius="lg">
        <Group
          p="md"
          gap="sm"
          style={{
            borderBottom: '1px solid var(--mantine-color-gray-3)',
          }}
        >
          <Text fw={700} fz="md">
            {t('account.groupsCategories', 'Gruppen & Kategorie')}
          </Text>
        </Group>
        <div
          style={{
            padding: '20px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
          }}
        >
          <div>
            <div
              style={{
                fontSize: 'var(--mantine-font-size-xs)',
                fontWeight: 600,
                color: 'var(--mantine-color-ink-3)',
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                marginBottom: 8,
              }}
            >
              {t('account.groups', 'Gruppen')}
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {myGroups.length > 0 ? (
                myGroups.map((g: { id: string; name: string }) => (
                  <Badge key={g.id} variant="light">
                    {g.name}
                  </Badge>
                ))
              ) : (
                <span
                  style={{
                    fontSize: 'var(--mantine-font-size-sm)',
                    color: 'var(--mantine-color-ink-3)',
                  }}
                >
                  {t('account.noGroupsAssigned', 'Cheni Gruppe zuegwise')}
                </span>
              )}
            </div>
          </div>
        </div>
      </Paper>

      <PaymentPlanCard />

      <div
        style={{
          padding: '14px 20px',
          background: 'var(--mantine-color-surface-1)',
          borderRadius: 10,
          fontSize: 'var(--mantine-font-size-sm)',
          color: 'var(--mantine-color-ink-4)',
        }}
      >
        {t(
          'account.contactAdminToChange',
          'Wen dini Stuf, Gruppe oder Kategorie wetsch ändere, kontaktier en Administrator.',
        )}
      </div>
    </>
  )
}
