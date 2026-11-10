import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useLocation, useParams } from 'react-router-dom'
import { Button, Group, Radio, Stack, Text, TextInput } from '@mantine/core'
import { IconPlus } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useAuth, useNav, useToast } from '@/context/AppContext'
import { useModules } from '@/modules/useModules'
import { Modal, PageHead, Tabs } from '@/components/ui'
import { qk } from '@/data/keys'
import { createDashboard, listDashboards, shareDashboard } from '@/api/dashboards'
import { SharingField } from './SharingField'
import { sharingBody, sharingValid, type Sharing } from './sharing'
import { HomeDashboard } from '@/screens/private/dashboard/HomeDashboard'
import { CustomDashboard } from '@/screens/private/dashboard/CustomDashboard'
import {
  DASHBOARD_TEMPLATES,
  templateWidgets,
  useWidgetAllowed,
  useWidgetCatalogue,
} from '@/screens/private/dashboard/widgets'

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
  const [sharing, setSharing] = useState<Sharing>({ visibility: 'private', groupIds: [] })
  const [fresh, setFresh] = useState<number | null>(null)
  const [template, setTemplate] = useState('')
  const catalogue = useWidgetCatalogue()
  const allowed = useWidgetAllowed()
  // Templates offered: those with at least two widgets this member may add.
  const templates = DASHBOARD_TEMPLATES.map((tpl) => ({
    ...tpl,
    widgets: templateWidgets(tpl, catalogue, allowed),
  })).filter((tpl) => tpl.widgets.length >= 2)
  const chosen = templates.find((tpl) => tpl.key === template)
  const own = modules.has('dashboards')
  const { data } = useQuery({ queryKey: qk.dashboards, queryFn: listDashboards, enabled: own })
  const dashboards = data?.items ?? []
  const canShare = data?.canShare ?? false
  // People who run the club start on the club overview, everyone else on
  // their own events and polls; both tabs have their own address too.
  const runsClub =
    isAdmin || hasPermission('members.members.update') || hasPermission('finance.invoices.update')

  const activeTab = id
    ? `d${id}`
    : location.pathname === '/app/dashboard/global'
      ? 'overview'
      : location.pathname === '/app/dashboard/me' || !runsClub
        ? 'account'
        : 'overview'
  const current = id ? dashboards.find((d) => String(d.id) === id) : undefined

  const openNew = () => {
    setCreating('')
    setSharing({ visibility: 'private', groupIds: [] })
    setTemplate('')
  }

  const create = async () => {
    const name = (creating ?? '').trim() || (chosen ? t(...chosen.name) : '')
    if (!name || !sharingValid(sharing)) return
    setCreating(null)
    setTemplate('')
    try {
      const d = await createDashboard(name, chosen?.widgets ?? [])
      // A new dashboard starts private; share it right away when asked.
      if (canShare && sharing.visibility !== 'private') {
        const body = sharingBody(sharing)
        await shareDashboard(d.id, body.shared, body.groupIds)
      }
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
            ? [
                {
                  id: 'new',
                  label: t('dashboards.new', 'Neues Dashboard'),
                  icon: <IconPlus size={14} />,
                },
              ]
            : []),
        ]}
        activeTab={activeTab}
        onTabChange={(tab) =>
          tab === 'new'
            ? openNew()
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
          <Text c="dimmed">
            {t('dashboards.notFound', 'Dieses Dashboard gibt es nicht (mehr).')}
          </Text>
        ) : null
      ) : activeTab === 'account' ? (
        <HomeDashboard key="me" kind="me" />
      ) : (
        <HomeDashboard key="club" kind="club" />
      )}

      <Modal
        open={creating !== null}
        onClose={() => setCreating(null)}
        title={t('dashboards.new', 'Neues Dashboard')}
        subtitle={t(
          'dashboards.newHint2',
          'Stell dir aus Widgets zusammen, was du im Blick haben willst.',
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
            <Button
              type="submit"
              disabled={(!(creating ?? '').trim() && !chosen) || !sharingValid(sharing)}
            >
              {t('dashboards.create', 'Erstellen')}
            </Button>
          </Group>
        }
      >
        <Stack gap="md">
          <TextInput
            label={t('dashboards.name', 'Name')}
            placeholder={
              chosen
                ? t(...chosen.name)
                : t('dashboards.namePlaceholder', 'z. B. Vorstand, Training, Finanzen')
            }
            maxLength={100}
            data-autofocus
            value={creating ?? ''}
            onChange={(e) => setCreating(e.currentTarget.value)}
          />
          {templates.length > 0 && (
            <Radio.Group
              label={t('dashboards.template', 'Vorlage')}
              value={template}
              onChange={setTemplate}
              data-testid="dashboard-template"
            >
              <Stack gap="xs" mt={6}>
                <Radio value="" label={t('dashboards.tpl.empty', 'Leer')} />
                {templates.map((tpl) => (
                  <Radio
                    key={tpl.key}
                    value={tpl.key}
                    label={t(...tpl.name)}
                    description={t(...tpl.hint)}
                  />
                ))}
              </Stack>
            </Radio.Group>
          )}
          {canShare && <SharingField value={sharing} onChange={setSharing} />}
        </Stack>
      </Modal>
    </div>
  )
}
