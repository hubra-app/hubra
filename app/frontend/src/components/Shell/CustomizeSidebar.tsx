import { useState, useSyncExternalStore } from 'react'
import { ActionIcon, Box, Button, Group, Modal, Stack, Text, TextInput, Tooltip } from '@mantine/core'
import { useMediaQuery } from '@mantine/hooks'
import {
  IconArrowDown,
  IconArrowUp,
  IconEye,
  IconEyeOff,
  IconPencil,
  IconPlus,
  IconStar,
  IconStarFilled,
  IconTrash,
} from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useNavPrefs, useSidebarNav } from './useSidebarNav'
import {
  addNavCategory,
  moveNavEntry,
  NO_PREFS,
  removeNavCategory,
  renameNavSection,
  toggleNavMore,
  type NavGroup,
} from './nav'
import {
  customizeSidebarOpen,
  setCustomizeSidebarOpen,
  subscribeCustomizeSidebar,
} from './customizeSidebarStore'

/**
 * Pin entries to the top of the sidebar, move them up and down (past the
 * end of a section into the next one), or put them under "Weitere" and back.
 * Headings can be renamed, and the person can add categories of their own.
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
  // The heading being renamed, and the name typed so far.
  const [editing, setEditing] = useState<{ section: string; label: string } | null>(null)

  const finishRename = () => {
    if (editing) save(renameNavSection(prefs, editing.section, editing.label))
    setEditing(null)
  }

  const addCategory = () => {
    const label = t('shell.customize.newCategory')
    const next = addNavCategory(prefs, label)
    save(next)
    const added = next.categories![next.categories!.length - 1]
    setEditing({ section: added.id, label })
  }

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
      Object.keys(prefs.sections ?? {}).length +
      (prefs.categories?.length ?? 0) +
      Object.keys(prefs.labels ?? {}).length >
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
            <GroupHeading
              group={group}
              editing={editing?.section === group.section ? editing.label : null}
              iconSize={iconSize}
              phone={!!phone}
              onEdit={() => setEditing({ section: group.section, label: group.label })}
              onChange={(label) => setEditing({ section: group.section, label })}
              onDone={finishRename}
              onCancel={() => setEditing(null)}
              onRemove={() => save(removeNavCategory(prefs, group.section))}
            />
            {group.items.length === 0 && (
              <Text size="sm" c="dimmed" px={8} py={4}>
                {t('shell.customize.emptyCategory')}
              </Text>
            )}
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
      <Button
        variant="default"
        leftSection={<IconPlus size={16} />}
        mt="md"
        onClick={addCategory}
      >
        {t('shell.customize.addCategory')}
      </Button>
      <Group justify="space-between" mt="lg">
        <Button
          variant="subtle"
          color="gray"
          disabled={!touched}
          onClick={() => {
            setEditing(null)
            save(NO_PREFS)
          }}
        >
          {t('shell.customize.reset')}
        </Button>
        <Button onClick={() => setCustomizeSidebarOpen(false)}>{t('shell.customize.done')}</Button>
      </Group>
    </Modal>
  )
}

/** A section heading, with rename (and remove for the person's own categories). */
function GroupHeading({
  group,
  editing,
  iconSize,
  phone,
  onEdit,
  onChange,
  onDone,
  onCancel,
  onRemove,
}: {
  group: NavGroup
  /** The name typed so far while renaming, else null. */
  editing: string | null
  iconSize: 'md' | 'lg'
  phone: boolean
  onEdit: () => void
  onChange: (label: string) => void
  onDone: () => void
  onCancel: () => void
  onRemove: () => void
}) {
  const { t } = useT()
  if (editing !== null) {
    return (
      <TextInput
        size="xs"
        px={8}
        mb={4}
        autoFocus
        maxLength={40}
        value={editing}
        aria-label={t('shell.customize.categoryName')}
        onChange={(e) => onChange(e.currentTarget.value)}
        onBlur={onDone}
        onKeyDown={(e) => {
          if (e.key === 'Enter') onDone()
          if (e.key === 'Escape') {
            e.stopPropagation()
            onCancel()
          }
        }}
      />
    )
  }
  const renameLabel = t('shell.customize.rename')
  const removeLabel = t('shell.customize.removeCategory')
  return (
    <Group justify="space-between" wrap="nowrap" px={8} mb={4} gap={4}>
      <Text
        fz={13}
        fw={700}
        c="gray.6"
        tt="uppercase"
        truncate
        style={{ letterSpacing: '0.08em' }}
      >
        {group.label}
      </Text>
      <Group gap={2} wrap="nowrap">
        {group.renamable && (
          <Tooltip label={renameLabel} disabled={phone}>
            <ActionIcon
              variant="subtle"
              color="gray"
              size={iconSize}
              aria-label={`${renameLabel}: ${group.label}`}
              onClick={onEdit}
            >
              <IconPencil size={16} />
            </ActionIcon>
          </Tooltip>
        )}
        {group.custom && (
          <Tooltip label={removeLabel} disabled={phone}>
            <ActionIcon
              variant="subtle"
              color="gray"
              size={iconSize}
              aria-label={`${removeLabel}: ${group.label}`}
              onClick={onRemove}
            >
              <IconTrash size={16} />
            </ActionIcon>
          </Tooltip>
        )}
      </Group>
    </Group>
  )
}
