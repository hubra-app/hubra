import type { MouseEvent } from 'react'
import { Link } from 'react-router-dom'
import { Badge, Box, Button, Group, Paper, SimpleGrid, Stack, Text } from '@mantine/core'
import { IconAdjustments, IconDots } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { PageHead } from '@/components/ui'
import { EmptyState } from '@/components/feedback'
import { useAuth, useData, useNav } from '@/context/AppContext'
import type { ModuleInfo } from '@/api/modules'
import { localizeModule } from '@/modules/labels'
import type { NavItem } from './nav'
import { setCustomizeSidebarOpen } from './customizeSidebarStore'
import { useSidebarNav } from './useSidebarNav'

type Status = { text: string; tone?: 'warn' }

// Built-in pages whose module has no description of its own for them.
const PAGE_INFO: Record<string, string> = {
  '/app/dashboard': 'dashboard',
  '/app/settings': 'settings',
  '/app/translations': 'translations',
}

/**
 * "Weitere": a card for every module and plugin page the person may open,
 * grouped by area like the sidebar. Each card leads straight to its page,
 * including the pages someone took out of the sidebar.
 */
export function MoreScreen() {
  const { t } = useT()
  const { currentUser, hasPermission } = useAuth()
  const { moduleList } = useData()
  const { cards, more } = useSidebarNav()
  const hidden = new Set(more.map((item) => item.path))
  const modules = new Map(moduleList.map((m) => [m.code, m]))
  // The first page of a module speaks for it; its other pages say whose they are.
  const firstOf = new Map<string, string>()
  for (const m of moduleList) if (m.nav[0]) firstOf.set(m.code, m.nav[0].path)

  const status = (item: NavItem): Status | null => {
    const raw = item.module ? modules.get(item.module) : undefined
    if (!raw) return null
    const m = localizeModule(raw)
    if (item.path === '/app/members' && item.count)
      return { text: t('shell.nav.activeMembersCount', { count: item.count }) }
    if (item.path === '/app/members/applications')
      return {
        text: item.count
          ? t('shell.more.openApplications', { count: item.count })
          : t('shell.more.noApplications'),
      }
    if (item.path === '/app/groups' && item.count)
      return { text: t('shell.more.groupCount', { count: item.count }) }
    if (needsSetup(m)) return { text: t('shell.more.needsSetup'), tone: 'warn' }
    if (PAGE_INFO[item.path]) return { text: t(`shell.more.about.${PAGE_INFO[item.path]}`) }
    if (firstOf.get(m.code) !== item.path) return { text: t('shell.more.partOf', { module: m.name }) }
    return m.description ? { text: m.description } : null
  }

  const total = cards.reduce((n, area) => n + area.items.length, 0)

  return (
    <div>
      <PageHead
        title={t('shell.nav.more')}
        desc={t('shell.more.desc')}
        actions={
          currentUser ? (
            <Button
              variant="default"
              leftSection={<IconAdjustments size={16} />}
              onClick={() => setCustomizeSidebarOpen(true)}
            >
              {t('shell.customize.title')}
            </Button>
          ) : undefined
        }
      />
      {total === 0 ? (
        <EmptyState
          icon={<IconDots size={24} />}
          title={t('shell.more.emptyTitle')}
          description={t('shell.more.emptyDesc')}
        />
      ) : (
        <Stack gap={28}>
          {cards.map((area) => (
            <Box component="section" key={area.section} aria-label={area.label}>
              <Text
                fz={13}
                fw={700}
                c="gray.6"
                tt="uppercase"
                mb={10}
                style={{ letterSpacing: '0.08em' }}
              >
                {area.label}
              </Text>
              <SimpleGrid cols={{ base: 1, xs: 2, lg: 3 }} spacing="md">
                {area.items.map((item) => {
                  const raw = item.module ? modules.get(item.module) : undefined
                  return (
                    <ModuleCard
                      key={item.path}
                      item={item}
                      status={status(item)}
                      plugin={!!raw?.plugin}
                      tabs={(item.tabs ?? [])
                        .filter((tab) => !tab.perms.length || tab.perms.some(hasPermission))
                        .map((tab) => tab.label)}
                      hidden={hidden.has(item.path)}
                    />
                  )
                })}
              </SimpleGrid>
            </Box>
          ))}
        </Stack>
      )}
    </div>
  )
}

/** A module asks for settings it has not been given yet. */
function needsSetup(m: ModuleInfo): boolean {
  return !m.configured && m.settings.some((f) => f.required)
}

function ModuleCard({
  item,
  status,
  plugin,
  hidden,
  tabs,
}: {
  item: NavItem
  status: Status | null
  plugin: boolean
  hidden: boolean
  /** The pages that sit on this one as tabs. */
  tabs: string[]
}) {
  const { t } = useT()
  const { go } = useNav()
  // A real link, so it opens in a new tab too; a plain click goes through `go`.
  const onClick = (e: MouseEvent) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return
    e.preventDefault()
    go(item.path)
  }
  return (
    <Paper
      component={Link}
      to={item.path}
      onClick={onClick}
      withBorder
      p="md"
      className="module-card"
      data-testid="module-card"
      style={{ display: 'block', color: 'inherit', textDecoration: 'none' }}
    >
      <Group gap={14} wrap="nowrap" align="flex-start">
        <Box
          aria-hidden
          style={{
            flexShrink: 0,
            width: 44,
            height: 44,
            borderRadius: 12,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'var(--mantine-color-acc-1)',
            color: 'var(--mantine-color-acc-text)',
          }}
        >
          {item.icon}
        </Box>
        <Box style={{ minWidth: 0, flex: 1 }}>
          <Group gap={6} wrap="nowrap" justify="space-between">
            <Text fw={700} fz="md" truncate>
              {item.label}
            </Text>
            {plugin && (
              <Badge size="xs" variant="light" color="gray" style={{ flexShrink: 0 }}>
                {t('shell.more.plugin')}
              </Badge>
            )}
          </Group>
          <Text
            fz="sm"
            c={status?.tone === 'warn' ? 'orange.7' : 'dimmed'}
            truncate
            title={status?.text}
          >
            {status?.text ?? ' '}
          </Text>
          {tabs.length > 0 && (
            <Text fz="xs" c="dimmed" mt={4} truncate>
              {t('shell.more.withTabs', { pages: tabs.join(' · ') })}
            </Text>
          )}
          {hidden && (
            <Text fz="xs" c="dimmed" mt={4}>
              {t('shell.more.notInSidebar')}
            </Text>
          )}
        </Box>
      </Group>
    </Paper>
  )
}
