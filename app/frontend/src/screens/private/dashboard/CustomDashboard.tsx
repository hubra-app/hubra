import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { ActionIcon, Badge, Button, Group, Menu, Text, TextInput } from '@mantine/core'
import { IconDots, IconPencil, IconPlus, IconTrash, IconUsers } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useNav, useToast } from '@/context/AppContext'
import { ConfirmModal, EmptyState, Modal } from '@/components/ui'
import { qk } from '@/data/keys'
import {
  deleteDashboard,
  shareDashboard,
  updateDashboard,
  type Dashboard,
  type DashboardWidget,
} from '@/api/dashboards'
import { WidgetBoard } from './WidgetBoard'

/**
 * A member's own dashboard: widgets in a grid. Its owner edits it (add,
 * order, size, settings, remove) and, with the right to, shares it with
 * the club; everyone sees only the widgets they may.
 */
export function CustomDashboard({
  dashboard,
  canShare,
  startEditing = false,
}: {
  dashboard: Dashboard
  canShare: boolean
  startEditing?: boolean
}) {
  const { t } = useT()
  const { go } = useNav()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(startEditing && dashboard.canEdit)
  // A new, empty dashboard opens with the widget list.
  const [picking, setPicking] = useState(
    startEditing && dashboard.canEdit && dashboard.widgets.length === 0,
  )
  const [renaming, setRenaming] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [busy, setBusy] = useState(false)
  const widgets = dashboard.widgets

  const refresh = (d: Dashboard) =>
    queryClient.setQueryData(qk.dashboards, (old: { items: Dashboard[] } | undefined) =>
      old ? { ...old, items: old.items.map((x) => (x.id === d.id ? d : x)) } : old,
    )

  const run = async (action: () => Promise<Dashboard | void>, done?: string) => {
    setBusy(true)
    try {
      const d = await action()
      if (d) refresh(d)
      else await queryClient.invalidateQueries({ queryKey: qk.dashboards })
      if (done) notify('success', done)
    } catch (err) {
      notify('error', t('common.error'), err instanceof Error ? err.message : '')
    } finally {
      setBusy(false)
    }
  }

  const save = (next: DashboardWidget[]) =>
    run(() => updateDashboard(dashboard.id, { widgets: next }))

  return (
    <div>
      <Group justify="space-between" mb="md" gap="xs" className="page-actions">
        <Group gap={8}>
          <Badge
            variant="light"
            color={dashboard.shared ? 'blue' : 'gray'}
            leftSection={dashboard.shared ? <IconUsers size={12} /> : undefined}
          >
            {dashboard.shared
              ? t('dashboards.shared', 'Mit dem Verein geteilt')
              : t('dashboards.private', 'Privat')}
          </Badge>
          {!dashboard.mine && dashboard.owner.name && (
            <Text fz="xs" c="dimmed">
              {t('dashboards.by', 'von {{name}}', { name: dashboard.owner.name })}
            </Text>
          )}
        </Group>
        {dashboard.canEdit && (
          <Group gap="xs">
            {editing && (
              <Button
                variant="default"
                leftSection={<IconPlus size={16} />}
                onClick={() => setPicking(true)}
              >
                {t('dashboards.addWidget', 'Widget hinzufügen')}
              </Button>
            )}
            <Button
              variant={editing ? 'filled' : 'default'}
              leftSection={editing ? undefined : <IconPencil size={16} />}
              onClick={() => setEditing((e) => !e)}
            >
              {editing ? t('dashboards.done', 'Fertig') : t('dashboards.edit', 'Bearbeiten')}
            </Button>
            <Menu position="bottom-end" withinPortal>
              <Menu.Target>
                <ActionIcon variant="default" size="lg" aria-label={t('common.more', 'Mehr')}>
                  <IconDots size={16} />
                </ActionIcon>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Item onClick={() => setRenaming(dashboard.name)}>
                  {t('dashboards.rename', 'Umbenennen')}
                </Menu.Item>
                {((canShare && dashboard.mine) || dashboard.shared) && (
                  <Menu.Item
                    leftSection={<IconUsers size={14} />}
                    onClick={() =>
                      run(
                        () => shareDashboard(dashboard.id, !dashboard.shared),
                        dashboard.shared
                          ? t('dashboards.unsharedDone', 'Nicht mehr geteilt')
                          : t('dashboards.sharedDone', 'Mit dem Verein geteilt'),
                      )
                    }
                  >
                    {dashboard.shared
                      ? t('dashboards.unshare', 'Nicht mehr teilen')
                      : t('dashboards.share', 'Mit dem Verein teilen')}
                  </Menu.Item>
                )}
                <Menu.Item
                  color="red"
                  leftSection={<IconTrash size={14} />}
                  onClick={() => setDeleting(true)}
                >
                  {t('dashboards.delete', 'Dashboard löschen')}
                </Menu.Item>
              </Menu.Dropdown>
            </Menu>
          </Group>
        )}
      </Group>

      <WidgetBoard
        widgets={widgets}
        editing={editing}
        busy={busy}
        save={save}
        picking={picking}
        setPicking={setPicking}
        empty={
          <EmptyState
            title={t('dashboards.empty', 'Noch keine Widgets')}
            description={
              dashboard.canEdit
                ? t(
                    'dashboards.emptyHint',
                    'Füge Widgets hinzu: Anlässe, Beiträge, Zahlen, Notizen und mehr.',
                  )
                : undefined
            }
            action={
              dashboard.canEdit
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
        open={renaming !== null}
        onClose={() => setRenaming(null)}
        title={t('dashboards.rename', 'Umbenennen')}
        onSubmit={(e) => {
          e?.preventDefault()
          const name = (renaming ?? '').trim()
          setRenaming(null)
          if (name) run(() => updateDashboard(dashboard.id, { name }))
        }}
        footer={
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setRenaming(null)}>
              {t('common.cancel', 'Abbrechen')}
            </Button>
            <Button type="submit">{t('common.save', 'Speichern')}</Button>
          </Group>
        }
      >
        <TextInput
          label={t('dashboards.name', 'Name')}
          maxLength={100}
          data-autofocus
          value={renaming ?? ''}
          onChange={(e) => setRenaming(e.currentTarget.value)}
        />
      </Modal>

      <ConfirmModal
        open={deleting}
        title={t('dashboards.deleteTitle', 'Dashboard löschen')}
        body={t('dashboards.deleteBody', '«{{name}}» und seine Widgets werden gelöscht.', {
          name: dashboard.name,
        })}
        onConfirm={() => {
          setDeleting(false)
          run(() => deleteDashboard(dashboard.id)).then(() => go('/app/dashboard'))
        }}
        onClose={() => setDeleting(false)}
      />
    </div>
  )
}
