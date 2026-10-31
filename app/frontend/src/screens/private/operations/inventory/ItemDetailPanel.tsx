import { useState, useMemo } from 'react'
import { Anchor, Button, Badge, ActionIcon, Group, SimpleGrid, Stack, Text } from '@mantine/core'
import { useT } from '@/locales/i18n'
import {
  IconPencil,
  IconX,
  IconEye,
  IconEyeOff,
  IconCircleCheck,
  IconExternalLink,
  IconUserCheck,
  IconInfoCircle,
} from '@tabler/icons-react'
import { useToast } from '@/context/AppContext'
import { SlideOver, PanelSection, PanelField } from '@/components/feedback'
import { MemberAddSearch, PanelMemberRow } from '@/components/display'
import type { InventoryItem } from '@/types'
import { addInstruction, removeInstruction, addSelfInstruction } from '@/api/inventory'
import { useMemberSearch } from '@/data/members'
import { PluginSlot } from '@/plugins'
import { CATEGORY_COLORS, CATEGORY_ICONS, STATUS_CONFIG } from './constants'

interface DetailPanelProps {
  item: InventoryItem
  onClose: () => void
  onEdit: () => void
  currentUserId: number | null
  currentUserName: string
  onInstructionChange: (updated: InventoryItem) => void
}

export function ItemDetailPanel({
  item,
  onClose,
  onEdit,
  currentUserId,
  currentUserName,
  onInstructionChange,
}: DetailPanelProps) {
  const { t } = useT()
  const { notify } = useToast()
  const [addSearch, setAddSearch] = useState('')
  const { data: searchData } = useMemberSearch(addSearch, { enabled: addSearch.trim().length >= 2 })
  const addResults = useMemo(() => {
    if (addSearch.trim().length < 2 || !searchData) return []
    const instructed = new Set(item.instructedMemberIds.map(String))
    return searchData.members.filter((m) => !instructed.has(m.id)).slice(0, 6)
  }, [addSearch, searchData, item.instructedMemberIds])
  const [loading, setLoading] = useState(false)

  const isSelfInstructed =
    currentUserId !== null && item.instructedMemberIds.includes(currentUserId)

  // Bug fix: update both instructedMemberIds AND instructedMemberNames on every change
  const handleAddInstruction = async (memberId: number, memberName: string) => {
    setLoading(true)
    try {
      await addInstruction(item.id, memberId)
      onInstructionChange({
        ...item,
        instructedMemberIds: [...item.instructedMemberIds, memberId],
        instructedMemberNames: [...item.instructedMemberNames, memberName],
      })
      setAddSearch('')
      notify(
        'success',
        t('inventory.instruction.recorded', 'Einweisung erfasst'),
        t(
          'inventory.memberMarkedInstructed',
          '{{member}} ist als eingewiesen markiert.',
          { member: memberName },
        ),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('common.error', 'Fehler'),
        err instanceof Error ? err.message : t('common.unknownError', 'Unbekannter Fehler'),
      )
    } finally {
      setLoading(false)
    }
  }

  const handleRemoveInstruction = async (memberId: number, idx: number) => {
    setLoading(true)
    try {
      await removeInstruction(item.id, memberId)
      onInstructionChange({
        ...item,
        instructedMemberIds: item.instructedMemberIds.filter(
          (_, i) => i !== idx,
        ),
        instructedMemberNames: item.instructedMemberNames.filter(
          (_, i) => i !== idx,
        ),
      })
      notify(
        'info',
        t('inventory.instruction.removed', 'Einweisung entfernt'),
        t('inventory.recordCleared', 'Eintrag entfernt.'),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('inventory.failed', 'Fehler'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekannter Fehler'),
      )
    } finally {
      setLoading(false)
    }
  }

  const handleSelfInstruct = async () => {
    setLoading(true)
    try {
      await addSelfInstruction(item.id)
      if (currentUserId !== null) {
        onInstructionChange({
          ...item,
          instructedMemberIds: [...item.instructedMemberIds, currentUserId],
          instructedMemberNames: [
            ...item.instructedMemberNames,
            currentUserName,
          ],
        })
      }
      notify(
        'success',
        t('inventory.recorded', 'Erfasst'),
        t(
          'inventory.selfInstructedMsg',
          'Du bist jetzt für diesen Gegenstand als eingewiesen markiert.',
        ),
      )
    } catch (err: unknown) {
      notify(
        'error',
        t('inventory.failed', 'Fehler'),
        err instanceof Error
          ? err.message
          : t('common.unknownError', 'Unbekannter Fehler'),
      )
    } finally {
      setLoading(false)
    }
  }

  const sc = STATUS_CONFIG[item.status]
  const cc = CATEGORY_COLORS[item.category]
  const categoryLabel =
    item.category === 'Tool'
      ? t('inventory.tool', 'Werkzeug')
      : item.category === 'Item'
        ? t('inventory.itemLabel', 'Gegenstand')
        : t('inventory.material', 'Material')

  return (
    <SlideOver
      title={item.name}
      width={440}
      padded={false}
      onClose={onClose}
      icon={
        <div
          style={{
            width: 40,
            height: 40,
            borderRadius: 10,
            background: cc + '22',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: cc,
          }}
        >
          {CATEGORY_ICONS[item.category]}
        </div>
      }
      subtitle={
        <Group gap={6} mt={4}>
          <Badge variant="light" style={{ color: cc, background: cc + '18' }}>
            {categoryLabel}
          </Badge>
          <Badge
            variant="light"
            leftSection={sc.icon}
            style={{ color: sc.color, background: sc.color + '18' }}
          >
            {t(`inventory.status_${item.status}`, sc.label)}
          </Badge>
        </Group>
      }
      actions={
        <ActionIcon variant="subtle" onClick={onEdit} aria-label={t('common.edit', 'Bearbeiten')}>
          <IconPencil size={18} />
        </ActionIcon>
      }
    >
      <PanelSection>
        {item.description && (
          <Text fz="sm" lh={1.6} mb="md" style={{ color: 'var(--hb-text)', whiteSpace: 'pre-line' }}>
            {item.description}
          </Text>
        )}
        <SimpleGrid cols={2} spacing="md" verticalSpacing="sm">
          {item.ownerName && (
            <PanelField label={t('inventory.owner', 'Eigentümer:in')}>{item.ownerName}</PanelField>
          )}
          {item.responsibleName && (
            <PanelField label={t('inventory.responsible', 'Verantwortlich')}>
              {item.responsibleName}
            </PanelField>
          )}
          {item.cost && (
            <PanelField label={t('inventory.cost', 'Kosten')}>
              <span className="num">CHF {item.cost}</span>
            </PanelField>
          )}
          <PanelField label={t('inventory.visibility', 'Sichtbarkeit')}>
            {item.visibility === 'private' ? <IconEyeOff size={16} /> : <IconEye size={16} />}
            {item.visibility === 'private'
              ? t('inventory.private', 'Privat')
              : t('inventory.shared', 'Geteilt')}
          </PanelField>
        </SimpleGrid>
      </PanelSection>

      {item.links.length > 0 && (
        <PanelSection label={t('inventory.links', 'Links')}>
          <Stack gap={6}>
            {item.links.map((link, i) => (
              <Anchor
                key={link.url + i}
                href={link.url}
                target="_blank"
                rel="noopener noreferrer"
                fz="sm"
                style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}
              >
                <IconExternalLink size={16} style={{ flexShrink: 0 }} />
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {link.label || link.url}
                </span>
              </Anchor>
            ))}
          </Stack>
        </PanelSection>
      )}

      {item.instructionRequired ? (
        <PanelSection
          label={t('inventory.instructionRequired', 'Einweisung nötig')}
          right={
            <Text fz="xs" className="num" style={{ color: 'var(--hb-text-3)' }}>
              {item.instructedMemberIds.length}
            </Text>
          }
        >
          {!isSelfInstructed && currentUserId !== null && (
            <Button
              fullWidth
              mb="md"
              leftSection={<IconUserCheck size={16} />}
              onClick={handleSelfInstruct}
              disabled={loading}
            >
              {t('inventory.markMyselfInstructed', 'Mich als eingewiesen markieren')}
            </Button>
          )}
          {isSelfInstructed && (
            <Group
              gap={8}
              mb="md"
              px={12}
              py={8}
              style={{
                fontSize: 'var(--mantine-font-size-sm)',
                color: 'var(--mantine-color-green-7)',
                background: 'var(--mantine-color-green-light)',
                borderRadius: 8,
              }}
            >
              <IconCircleCheck size={16} />
              {t('inventory.youAreInstructed', 'Du bist für diesen Gegenstand eingewiesen')}
            </Group>
          )}

          <MemberAddSearch
            value={addSearch}
            onChange={setAddSearch}
            placeholder={t('inventory.searchMembersPlaceholder', 'Mitglieder suchen …')}
            results={addResults}
            onPick={(m) => handleAddInstruction(Number(m.id), m.name)}
            disabled={loading}
          />

          {item.instructedMemberIds.length === 0 ? (
            <Text fz="sm" ta="center" py="lg" style={{ color: 'var(--hb-text-3)' }}>
              {t('inventory.noMembersInstructed', 'Noch niemand eingewiesen.')}
            </Text>
          ) : (
            <div style={{ marginTop: 8 }}>
              {item.instructedMemberNames.map((name, i) => (
                <PanelMemberRow
                  key={item.instructedMemberIds[i]}
                  name={name}
                  detail={t('inventory.instructed', 'Eingewiesen')}
                  right={
                    <ActionIcon
                      variant="subtle"
                      color="red"
                      onClick={() => handleRemoveInstruction(item.instructedMemberIds[i], i)}
                      disabled={loading}
                      aria-label={t('common.remove', 'Entfernen')}
                    >
                      <IconX size={16} />
                    </ActionIcon>
                  }
                />
              ))}
            </div>
          )}
        </PanelSection>
      ) : (
        <PanelSection>
          <Group gap={8} wrap="nowrap" style={{ fontSize: 'var(--mantine-font-size-sm)', color: 'var(--hb-text-3)' }}>
            <IconInfoCircle size={16} style={{ flexShrink: 0 }} />
            {t('inventory.noInstructionRequired', 'Für diesen Gegenstand ist keine Einweisung nötig.')}
          </Group>
        </PanelSection>
      )}
      <PluginSlot name="inventory.item" props={{ itemId: Number(item.id) }} />
    </SlideOver>
  )
}
