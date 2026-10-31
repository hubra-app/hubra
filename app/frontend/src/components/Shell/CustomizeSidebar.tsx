import { useSyncExternalStore } from 'react'
import { ActionIcon, Button, Group, Modal, Stack, Text, Tooltip } from '@mantine/core'
import { IconEye, IconEyeOff, IconStar, IconStarFilled } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useNavPrefs, useSidebarNav } from './useSidebarNav'
import {
  customizeSidebarOpen,
  setCustomizeSidebarOpen,
  subscribeCustomizeSidebar,
} from './customizeSidebarStore'

/**
 * Pin entries to the top of the sidebar or hide them. Hidden entries stay one
 * click away under "Weitere"; changes are saved on the account at once.
 */
export function CustomizeSidebarModal() {
  const { t } = useT()
  const opened = useSyncExternalStore(subscribeCustomizeSidebar, customizeSidebarOpen)
  const { customizable } = useSidebarNav()
  const { prefs, save } = useNavPrefs()

  const toggle = (path: string, key: 'pinned' | 'hidden') => {
    // An entry is either pinned or hidden, not both.
    const next = {
      pinned: prefs.pinned.filter((p) => p !== path),
      hidden: prefs.hidden.filter((p) => p !== path),
    }
    if (!prefs[key].includes(path)) next[key].push(path)
    save(next)
  }

  return (
    <Modal
      opened={opened}
      onClose={() => setCustomizeSidebarOpen(false)}
      title={t('shell.customize.title')}
      size="md"
    >
      <Text size="sm" c="dimmed" mb="md">
        {t('shell.customize.intro')}
      </Text>
      <Stack gap={2}>
        {customizable.map((item) => {
          const pinned = prefs.pinned.includes(item.path)
          const hidden = prefs.hidden.includes(item.path)
          const pinLabel = t(pinned ? 'shell.customize.unpin' : 'shell.customize.pin')
          const hideLabel = t(hidden ? 'shell.customize.show' : 'shell.customize.hide')
          return (
            <Group
              key={item.path}
              justify="space-between"
              wrap="nowrap"
              px={8}
              py={4}
              data-testid="customize-row"
              style={{ borderRadius: 8, opacity: hidden ? 0.55 : 1 }}
            >
              <Group gap={10} wrap="nowrap">
                <span style={{ display: 'flex', color: 'var(--hb-text-2)' }}>{item.icon}</span>
                <Text size="sm">{item.label}</Text>
              </Group>
              <Group gap={4} wrap="nowrap">
                <Tooltip label={pinLabel}>
                  <ActionIcon
                    variant="subtle"
                    color={pinned ? 'yellow' : 'gray'}
                    aria-label={`${pinLabel}: ${item.label}`}
                    aria-pressed={pinned}
                    onClick={() => toggle(item.path, 'pinned')}
                  >
                    {pinned ? <IconStarFilled size={18} /> : <IconStar size={18} />}
                  </ActionIcon>
                </Tooltip>
                <Tooltip label={hideLabel}>
                  <ActionIcon
                    variant="subtle"
                    color="gray"
                    aria-label={`${hideLabel}: ${item.label}`}
                    aria-pressed={hidden}
                    onClick={() => toggle(item.path, 'hidden')}
                  >
                    {hidden ? <IconEyeOff size={18} /> : <IconEye size={18} />}
                  </ActionIcon>
                </Tooltip>
              </Group>
            </Group>
          )
        })}
      </Stack>
      <Group justify="space-between" mt="lg">
        <Button
          variant="subtle"
          color="gray"
          disabled={prefs.pinned.length + prefs.hidden.length === 0}
          onClick={() => save({ pinned: [], hidden: [] })}
        >
          {t('shell.customize.reset')}
        </Button>
        <Button onClick={() => setCustomizeSidebarOpen(false)}>{t('shell.customize.done')}</Button>
      </Group>
    </Modal>
  )
}
