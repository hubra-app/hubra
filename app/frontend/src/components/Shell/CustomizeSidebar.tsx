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
import { moveNavEntry, toggleNavMore } from './nav'
import {
  customizeSidebarOpen,
  setCustomizeSidebarOpen,
  subscribeCustomizeSidebar,
} from './customizeSidebarStore'

/**
 * Pin entries to the top of the sidebar, move them up and down (past the
 * end of a section into the next one), or put them under "Weitere" and back.
 * Changes are saved on the account at once. Arrow buttons rather than drag
 * and drop, so it works the same with a finger on a phone.
 */
export function CustomizeSidebarModal() {
  const { t } = useT()
  const opened = useSyncExternalStore(subscribeCustomizeSidebar, customizeSidebarOpen)
  const phone = useMediaQuery('(max-width: 47.99em)')
  const { groups, homes } = useSidebarNav()
  const { prefs, save } = useNavPrefs()
  const iconSize = phone ? 'lg' : 'md'

  const togglePin = (path: string) => {
    // A pinned entry is shown under Favoriten, so it leaves Weitere.
    const pinned = prefs.pinned.includes(path)
    save({
      ...prefs,
      pinned: pinned ? prefs.pinned.filter((p) => p !== path) : [...prefs.pinned, path],
      hidden: pinned ? prefs.hidden : prefs.hidden.filter((p) => p !== path),
    })
  }

  const toggleMore = (path: string, inMore: boolean) => {
    const next = toggleNavMore(prefs, homes, path, inMore)
    // Put under Weitere, an entry is no longer a favourite.
    save(inMore ? next : { ...next, pinned: next.pinned.filter((p) => p !== path) })
  }

  const touched =
    prefs.pinned.length +
      prefs.hidden.length +
      (prefs.order?.length ?? 0) +
      Object.keys(prefs.sections ?? {}).length >
    0

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
        {groups.map((group, g) => (
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
                const inMore = group.section === 'more'
                const pinLabel = t(pinned ? 'shell.customize.unpin' : 'shell.customize.pin')
                const moreLabel = t(inMore ? 'shell.customize.show' : 'shell.customize.hide')
                // Past the end of a section the arrows move into the next
                // one; favourites stay among themselves.
                const fav = group.section === 'favourites'
                const prev = groups[g - 1]
                const next = groups[g + 1]
                const canUp = index > 0 || (!fav && !!prev && prev.section !== 'favourites')
                const canDown = index < group.items.length - 1 || (!fav && !!next)
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
                      style={{ minWidth: 0, opacity: inMore ? 0.7 : 1 }}
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
                          disabled={!canUp}
                          style={{ visibility: canUp ? undefined : 'hidden' }}
                          onClick={() => save(moveNavEntry(prefs, groups, homes, item.path, -1))}
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
                          disabled={!canDown}
                          style={{ visibility: canDown ? undefined : 'hidden' }}
                          onClick={() => save(moveNavEntry(prefs, groups, homes, item.path, 1))}
                        >
                          <IconArrowDown size={18} />
                        </ActionIcon>
                      </Tooltip>
                      <Tooltip label={pinLabel} disabled={phone}>
                        <ActionIcon
                          variant="subtle"
                          color={pinned ? 'orange' : 'gray'}
                          size={iconSize}
                          aria-label={`${pinLabel}: ${item.label}`}
                          aria-pressed={pinned}
                          onClick={() => togglePin(item.path)}
                        >
                          {pinned ? <IconStarFilled size={18} /> : <IconStar size={18} />}
                        </ActionIcon>
                      </Tooltip>
                      <Tooltip label={moreLabel} disabled={phone}>
                        <ActionIcon
                          variant="subtle"
                          color="gray"
                          size={iconSize}
                          aria-label={`${moreLabel}: ${item.label}`}
                          aria-pressed={inMore}
                          onClick={() => toggleMore(item.path, inMore)}
                        >
                          {inMore ? <IconEyeOff size={18} /> : <IconEye size={18} />}
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
          onClick={() => save({ pinned: [], hidden: [], order: [], sections: {} })}
        >
          {t('shell.customize.reset')}
        </Button>
        <Button onClick={() => setCustomizeSidebarOpen(false)}>{t('shell.customize.done')}</Button>
      </Group>
    </Modal>
  )
}
