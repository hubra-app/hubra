import { useSyncExternalStore } from 'react'
import { ActionIcon, Box, Button, Group, Modal, Stack, Text, Tooltip } from '@mantine/core'
import { useMediaQuery } from '@mantine/hooks'
import {
  IconArrowDown,
  IconArrowUp,
  IconEye,
  IconEyeOff,
  IconStar,
  IconStarFilled,
} from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useNavPrefs, useSidebarNav } from './useSidebarNav'
import { moveNavEntry } from './nav'
import {
  customizeSidebarOpen,
  setCustomizeSidebarOpen,
  subscribeCustomizeSidebar,
} from './customizeSidebarStore'

/**
 * Pin entries to the top of the sidebar, hide them, or move them up and down
 * within their section. Hidden entries stay one click away under "Weitere";
 * changes are saved on the account at once. Arrow buttons rather than drag
 * and drop, so it works the same with a finger on a phone.
 */
export function CustomizeSidebarModal() {
  const { t } = useT()
  const opened = useSyncExternalStore(subscribeCustomizeSidebar, customizeSidebarOpen)
  const phone = useMediaQuery('(max-width: 47.99em)')
  const { groups } = useSidebarNav()
  const { prefs, save } = useNavPrefs()
  const iconSize = phone ? 'lg' : 'md'

  const toggle = (path: string, key: 'pinned' | 'hidden') => {
    // An entry is either pinned or hidden, not both.
    const next = {
      ...prefs,
      pinned: prefs.pinned.filter((p) => p !== path),
      hidden: prefs.hidden.filter((p) => p !== path),
    }
    if (!prefs[key].includes(path)) next[key].push(path)
    save(next)
  }

  const touched = prefs.pinned.length + prefs.hidden.length + (prefs.order?.length ?? 0) > 0

  return (
    <Modal
      opened={opened}
      onClose={() => setCustomizeSidebarOpen(false)}
      title={t('shell.customize.title')}
      size="md"
      fullScreen={phone}
    >
      <Text size="sm" c="dimmed" mb="md">
        {t('shell.customize.intro')}
      </Text>
      <Stack gap="md">
        {groups.map((group) => (
          <Box key={group.section} data-testid="customize-group">
            <Text
              fz={11}
              fw={700}
              c="gray.6"
              tt="uppercase"
              px={8}
              mb={4}
              style={{ letterSpacing: '0.08em' }}
            >
              {group.label}
            </Text>
            <Stack gap={2}>
              {group.items.map((item, index) => {
                const pinned = prefs.pinned.includes(item.path)
                const hidden = prefs.hidden.includes(item.path)
                const pinLabel = t(pinned ? 'shell.customize.unpin' : 'shell.customize.pin')
                const hideLabel = t(hidden ? 'shell.customize.show' : 'shell.customize.hide')
                const upLabel = t('shell.customize.moveUp')
                const downLabel = t('shell.customize.moveDown')
                return (
                  <Group
                    key={item.path}
                    justify="space-between"
                    wrap="nowrap"
                    px={8}
                    py={4}
                    data-testid="customize-row"
                    style={{ borderRadius: 8 }}
                  >
                    <Group
                      gap={10}
                      wrap="nowrap"
                      style={{ minWidth: 0, opacity: hidden ? 0.55 : 1 }}
                    >
                      <span style={{ display: 'flex', color: 'var(--hb-text-2)' }}>
                        {item.icon}
                      </span>
                      <Text size="sm" truncate>
                        {item.label}
                      </Text>
                    </Group>
                    <Group gap={2} wrap="nowrap">
                      <Tooltip label={upLabel} disabled={phone}>
                        <ActionIcon
                          variant="subtle"
                          color="gray"
                          size={iconSize}
                          aria-label={`${upLabel}: ${item.label}`}
                          disabled={index === 0}
                          style={{ visibility: index === 0 ? 'hidden' : undefined }}
                          onClick={() => save(moveNavEntry(prefs, group, item.path, -1))}
                        >
                          <IconArrowUp size={18} />
                        </ActionIcon>
                      </Tooltip>
                      <Tooltip label={downLabel} disabled={phone}>
                        <ActionIcon
                          variant="subtle"
                          color="gray"
                          size={iconSize}
                          aria-label={`${downLabel}: ${item.label}`}
                          disabled={index === group.items.length - 1}
                          style={{
                            visibility: index === group.items.length - 1 ? 'hidden' : undefined,
                          }}
                          onClick={() => save(moveNavEntry(prefs, group, item.path, 1))}
                        >
                          <IconArrowDown size={18} />
                        </ActionIcon>
                      </Tooltip>
                      <Tooltip label={pinLabel} disabled={phone}>
                        <ActionIcon
                          variant="subtle"
                          color={pinned ? 'yellow' : 'gray'}
                          size={iconSize}
                          aria-label={`${pinLabel}: ${item.label}`}
                          aria-pressed={pinned}
                          onClick={() => toggle(item.path, 'pinned')}
                        >
                          {pinned ? <IconStarFilled size={18} /> : <IconStar size={18} />}
                        </ActionIcon>
                      </Tooltip>
                      <Tooltip label={hideLabel} disabled={phone}>
                        <ActionIcon
                          variant="subtle"
                          color="gray"
                          size={iconSize}
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
          </Box>
        ))}
      </Stack>
      <Group justify="space-between" mt="lg">
        <Button
          variant="subtle"
          color="gray"
          disabled={!touched}
          onClick={() => save({ pinned: [], hidden: [], order: [] })}
        >
          {t('shell.customize.reset')}
        </Button>
        <Button onClick={() => setCustomizeSidebarOpen(false)}>{t('shell.customize.done')}</Button>
      </Group>
    </Modal>
  )
}
