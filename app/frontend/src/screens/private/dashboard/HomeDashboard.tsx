import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ActionIcon, Button, Group, Menu, Text } from '@mantine/core'
import { IconDots, IconPlus, IconRestore, IconLayoutDashboard } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useToast } from '@/context/AppContext'
import { EmptyState, Modal } from '@/components/ui'
import { qk } from '@/data/keys'
import {
  getHomePages,
  resetHomePage,
  saveHomePage,
  type DashboardWidget,
  type HomeKind,
  type HomePage,
} from '@/api/dashboards'
import { WidgetBoard } from './WidgetBoard'
import { CLUB_HOME, MY_HOME, useDefaultHome } from './widgets'
import { ClubActions } from './homeCards'

/**
 * A start page (Dashboard › Verein or › Persönlich) built from widgets.
 * It shows the built-in layout until it is changed: the club's by whoever
 * holds `dashboards.home.update`, the personal one by each member.
 */
export function HomeDashboard({ kind }: { kind: HomeKind }) {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: qk.dashboardHome, queryFn: getHomePages })
  const [editing, setEditing] = useState(false)
  const [picking, setPicking] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [busy, setBusy] = useState(false)
  const page = data?.[kind]
  const custom = page?.widgets != null
  const builtIn = useDefaultHome(kind === 'club' ? CLUB_HOME : MY_HOME)
  const widgets: DashboardWidget[] = page?.widgets ?? builtIn
  const canEdit = page?.canEdit ?? false

  const store = (next: Omit<HomePage, 'canEdit'>) =>
    queryClient.setQueryData(qk.dashboardHome, (old: Record<HomeKind, HomePage> | undefined) =>
      old ? { ...old, [kind]: { ...old[kind], ...next } } : old,
    )

  const run = async (action: () => Promise<Omit<HomePage, 'canEdit'>>, done?: string) => {
    setBusy(true)
    try {
      store(await action())
      if (done) notify('success', done)
    } catch (err) {
      notify('error', t('common.error'), err instanceof Error ? err.message : '')
    } finally {
      setBusy(false)
    }
  }

  if (isLoading) return null

  return (
    <div>
      <Group justify="space-between" mb="md" gap="xs" className="page-actions">
        <Text fz="xs" c="dimmed">
          {editing
            ? kind === 'club'
              ? t(
                  'dashboards.home.clubHint',
                  'Diese Startseite sehen alle Mitglieder, jedes nur mit den Widgets, die es sehen darf.',
                )
              : t('dashboards.home.meHint', 'Deine persönliche Startseite. Nur du siehst sie so.')
            : ''}
        </Text>
        <Group gap="xs">
          {kind === 'club' && !editing && <ClubActions />}
          {canEdit && editing && (
            <Button
              variant="default"
              leftSection={<IconPlus size={16} />}
              onClick={() => setPicking(true)}
            >
              {t('dashboards.addWidget', 'Widget hinzufügen')}
            </Button>
          )}
          {canEdit && (
            <Button
              variant={editing ? 'filled' : 'default'}
              leftSection={editing ? undefined : <IconLayoutDashboard size={16} />}
              onClick={() => setEditing((e) => !e)}
            >
              {editing
                ? t('dashboards.done', 'Fertig')
                : t('dashboards.home.customize', 'Anpassen')}
            </Button>
          )}
          {canEdit && custom && (
            <Menu position="bottom-end" withinPortal>
              <Menu.Target>
                <ActionIcon variant="default" size="lg" aria-label={t('common.more', 'Mehr')}>
                  <IconDots size={16} />
                </ActionIcon>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Item
                  leftSection={<IconRestore size={14} />}
                  onClick={() => setResetting(true)}
                >
                  {t('dashboards.home.reset', 'Standard wiederherstellen')}
                </Menu.Item>
              </Menu.Dropdown>
            </Menu>
          )}
        </Group>
      </Group>

      <WidgetBoard
        widgets={widgets}
        editing={editing}
        busy={busy}
        save={(next) => run(() => saveHomePage(kind, next))}
        picking={picking}
        setPicking={setPicking}
        empty={
          <EmptyState
            title={t('dashboards.empty', 'Noch keine Widgets')}
            action={
              canEdit
                ? {
                    label: t('dashboards.addWidget', 'Widget hinzufügen'),
                    onClick: () => {
                      setEditing(true)
                      setPicking(true)
                    },
                  }
                : undefined
            }
          />
        }
      />

      <Modal
        open={resetting}
        onClose={() => setResetting(false)}
        title={t('dashboards.home.reset', 'Standard wiederherstellen')}
        onSubmit={(e) => {
          e?.preventDefault()
          setResetting(false)
          setEditing(false)
          run(
            () => resetHomePage(kind),
            t('dashboards.home.resetDone', 'Standard wiederhergestellt'),
          )
        }}
        footer={
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setResetting(false)}>
              {t('common.cancel', 'Abbrechen')}
            </Button>
            <Button type="submit" leftSection={<IconRestore size={16} />}>
              {t('dashboards.home.reset', 'Standard wiederherstellen')}
            </Button>
          </Group>
        }
      >
        <Text fz="sm">
          {kind === 'club'
            ? t(
                'dashboards.home.resetClub',
                'Die Startseite des Vereins zeigt wieder die Standard-Widgets, für alle Mitglieder.',
              )
            : t('dashboards.home.resetMe', 'Deine Startseite zeigt wieder die Standard-Widgets.')}
        </Text>
      </Modal>
    </div>
  )
}
