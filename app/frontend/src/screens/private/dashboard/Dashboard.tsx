import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useLocation, useParams } from 'react-router-dom'
import { Button, Group, Text, TextInput } from '@mantine/core'
import { IconPlus } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useAuth, useNav, useToast } from '@/context/AppContext'
import { useModules } from '@/modules/useModules'
import { Modal, PageHead, Tabs } from '@/components/ui'
import { qk } from '@/data/keys'
import { createDashboard, listDashboards } from '@/api/dashboards'
import { AccountDashboardScreen } from '@/screens/private/account/Account'
import { GlobalOverviewScreen } from '@/screens/private/dashboard/DashboardGlobalTab'
import { CustomDashboard } from '@/screens/private/dashboard/CustomDashboard'

export function DashboardScreen() {
  const { t } = useT()
  const location = useLocation()
  const { id } = useParams()
  const { go } = useNav()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const modules = useModules()
  const { isAdmin, hasPermission } = useAuth()
  const [creating, setCreating] = useState<string | null>(null)
  const [fresh, setFresh] = useState<number | null>(null)
  const own = modules.has('dashboards')
  const { data } = useQuery({ queryKey: qk.dashboards, queryFn: listDashboards, enabled: own })
  const dashboards = data?.items ?? []
  // People who run the club start on the club overview, everyone else on
  // their own events and polls; both tabs have their own address too.
  const runsClub =
    isAdmin ||
    hasPermission('members.members.update') ||
    hasPermission('finance.invoices.update')

  const activeTab = id
    ? `d${id}`
    : location.pathname === '/app/dashboard/global'
      ? 'overview'
      : location.pathname === '/app/dashboard/me' || !runsClub
        ? 'account'
        : 'overview'
  const current = id ? dashboards.find((d) => String(d.id) === id) : undefined

  const create = async () => {
    const name = (creating ?? '').trim()
    if (!name) return
    setCreating(null)
    try {
      const d = await createDashboard(name)
      await queryClient.invalidateQueries({ queryKey: qk.dashboards })
      setFresh(d.id)
      go(`/app/dashboard/d/${d.id}`)
    } catch (err) {
      notify('error', t('common.error'), err instanceof Error ? err.message : '')
    }
  }

  return (
    <div>
      <PageHead title={current?.name ?? t('dashboard.title')} />
      <Tabs
        tabs={[
          { id: 'account', label: t('dashboard.tabs.account') },
          { id: 'overview', label: t('dashboard.tabs.overview') },
          ...dashboards.map((d) => ({ id: `d${d.id}`, label: d.name })),
          ...(own && (data?.items.filter((d) => d.mine).length ?? 0) < (data?.max ?? 0)
            ? [{ id: 'new', label: t('dashboards.new', 'Neues Dashboard'), icon: <IconPlus size={14} /> }]
            : []),
        ]}
        activeTab={activeTab}
        onTabChange={(tab) =>
          tab === 'new'
            ? setCreating('')
            : go(
                tab === 'overview'
                  ? '/app/dashboard/global'
                  : tab === 'account'
                    ? '/app/dashboard/me'
                    : `/app/dashboard/d/${tab.slice(1)}`,
              )
        }
      />
      {id ? (
        current ? (
          <CustomDashboard
            key={current.id}
            dashboard={current}
            canShare={data?.canShare ?? false}
            startEditing={fresh === current.id}
          />
        ) : data ? (
          <Text c="dimmed">{t('dashboards.notFound', 'Dieses Dashboard gibt es nicht (mehr).')}</Text>
        ) : null
      ) : activeTab === 'account' ? (
        <AccountDashboardScreen />
      ) : (
        <GlobalOverviewScreen />
      )}

      <Modal
        open={creating !== null}
        onClose={() => setCreating(null)}
        title={t('dashboards.new', 'Neues Dashboard')}
        subtitle={t(
          'dashboards.newHint',
          'Stell dir aus Widgets zusammen, was du im Blick haben willst. Es bleibt privat, bis du es mit dem Verein teilst.',
        )}
        onSubmit={(e) => {
          e?.preventDefault()
          create()
        }}
        footer={
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setCreating(null)}>
              {t('common.cancel', 'Abbrechen')}
            </Button>
            <Button type="submit" disabled={!(creating ?? '').trim()}>
              {t('dashboards.create', 'Erstellen')}
            </Button>
          </Group>
        }
      >
        <TextInput
          label={t('dashboards.name', 'Name')}
          placeholder={t('dashboards.namePlaceholder', 'z. B. Vorstand, Training, Finanzen')}
          maxLength={100}
          data-autofocus
          value={creating ?? ''}
          onChange={(e) => setCreating(e.currentTarget.value)}
        />
      </Modal>
    </div>
  )
}
