import { Suspense } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Center, Loader, Paper, Stack, Text } from '@mantine/core'
import { IconAlertTriangle } from '@tabler/icons-react'
import { PageHead, Tabs } from '@/components/ui'
import { useAdmin } from '@/context/AdminContext'
import { useLang } from '@/lang'
import { visibleTabs, type NavPage, type PageTab } from '@/nav'

export function AccessDenied() {
  const { tr } = useLang()
  return (
    <Center py={80}>
      <Paper shadow="lg" p="xl" maw={400}>
        <Stack gap="sm" align="center" ta="center">
          <IconAlertTriangle size={40} color="var(--mantine-color-red-text)" />
          <Text fw={700} c="red">
            {tr('Kein Zugriff', 'Access denied')}
          </Text>
          <Text size="sm" c="dimmed">
            {tr(
              'Du hast keine Berechtigung für diese Seite.',
              'You do not have permission to access this page.',
            )}
          </Text>
          <Button component="a" href="/app/my-tenants" variant="light" mt="xs">
            {tr('Zu meinen Vereinen', 'To my clubs')}
          </Button>
        </Stack>
      </Paper>
    </Center>
  )
}

/** While a tab's screen loads (screens load on first open, see nav.tsx). */
function TabLoading() {
  return (
    <Center py={80}>
      <Loader />
    </Center>
  )
}

/** One sidebar page: its heading, the tabs this person may open, the open tab. */
export function TabbedPage({ page, tab }: { page: NavPage; tab: PageTab }) {
  const { hasGlobalPermission } = useAdmin()
  const navigate = useNavigate()
  const tabs = visibleTabs(page, hasGlobalPermission)
  if (!tabs.some((t) => t.id === tab.id)) return <AccessDenied />
  if (page.ownHead) return <Suspense fallback={<TabLoading />}>{tab.render()}</Suspense>
  return (
    <div>
      <Suspense fallback={null}>
        <PageHead title={page.title ?? page.label} desc={tab.desc ?? page.desc} />
      </Suspense>
      {tabs.length > 1 && (
        <Tabs
          tabs={tabs.map((t) => ({ id: t.id, label: t.label }))}
          activeTab={tab.id}
          onTabChange={(id) => {
            const next = tabs.find((t) => t.id === id)
            if (next) navigate(next.path)
          }}
        />
      )}
      {/* key: a fresh screen per tab, like separate pages before. */}
      <div key={tab.id}>
        <Suspense fallback={<TabLoading />}>{tab.render()}</Suspense>
      </div>
    </div>
  )
}
