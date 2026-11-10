import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ActionIcon, Button, Group, Menu, Text, TextInput } from '@mantine/core'
import { IconChevronDown, IconTemplate, IconTrash } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { Modal } from '@/components/ui'
import { useToast } from '@/context/AppContext'
import { qk } from '@/data/keys'
import {
  deleteEventTemplate,
  listEventTemplates,
  saveEventTemplate,
  type EventTemplate,
} from '@/api/events'
import type { ClubEvent } from '@/types'

/** "Aus Vorlage": the saved templates, newest name order; picking one opens
 * the new-event form filled with it. */
export function TemplateMenu({ onPick }: { onPick: (template: EventTemplate) => void }) {
  const { t } = useT()
  const { notify } = useToast()
  const client = useQueryClient()
  const { data: templates = [] } = useQuery({
    queryKey: qk.eventTemplates,
    queryFn: listEventTemplates,
  })
  const remove = useMutation({
    mutationFn: (id: number) => deleteEventTemplate(id),
    onSuccess: () => client.invalidateQueries({ queryKey: qk.eventTemplates }),
    onError: () => notify('error', t('events.templates.deleteFailed', 'Vorlage nicht gelöscht')),
  })
  if (templates.length === 0) return null
  return (
    <Menu position="bottom-end" withinPortal>
      <Menu.Target>
        <Button variant="default" rightSection={<IconChevronDown size={14} />} data-testid="event-templates">
          <IconTemplate size={16} />
          {t('events.templates.fromTemplate', 'Aus Vorlage')}
        </Button>
      </Menu.Target>
      <Menu.Dropdown miw={260}>
        {templates.map((tpl) => (
          <Menu.Item
            key={tpl.id}
            onClick={() => onPick(tpl)}
            rightSection={
              <ActionIcon
                variant="subtle"
                color="red"
                size="sm"
                aria-label={t('events.templates.delete', 'Vorlage löschen')}
                onClick={(e) => {
                  e.stopPropagation()
                  remove.mutate(tpl.id)
                }}
              >
                <IconTrash size={14} />
              </ActionIcon>
            }
          >
            <Text size="sm">{tpl.name}</Text>
            {(tpl.data.time || tpl.data.location) && (
              <Text size="xs" c="dimmed">
                {[tpl.data.time, tpl.data.location].filter(Boolean).join(' · ')}
              </Text>
            )}
          </Menu.Item>
        ))}
      </Menu.Dropdown>
    </Menu>
  )
}

/** "Als Vorlage speichern": name the template (the title by default). */
export function SaveTemplateModal({ event, onClose }: { event: ClubEvent | null; onClose: () => void }) {
  const { t } = useT()
  const { notify } = useToast()
  const client = useQueryClient()
  const [name, setName] = useState<string | null>(null)
  const value = name ?? event?.title ?? ''
  const close = () => {
    setName(null)
    onClose()
  }
  const save = useMutation({
    mutationFn: ({ id, n }: { id: string; n: string }) => saveEventTemplate(id, n),
    onSuccess: (tpl) => {
      void client.invalidateQueries({ queryKey: qk.eventTemplates })
      notify(
        'success',
        t('events.templates.saved', 'Vorlage gespeichert'),
        t('events.templates.savedMsg', '«{{name}}» steht unter «Aus Vorlage» bereit.', { name: tpl.name }),
      )
      close()
    },
    onError: () => notify('error', t('events.templates.saveFailed', 'Vorlage nicht gespeichert')),
  })
  return (
    <Modal
      open={event !== null}
      onClose={close}
      title={t('events.templates.saveTitle', 'Als Vorlage speichern')}
      subtitle={t(
        'events.templates.saveSubtitle',
        'Ort, Zeit, Plätze, Einstellungen und Beschreibung werden gespeichert, das Datum nicht.',
      )}
      footer={
        <Group gap="xs">
          <Button variant="default" onClick={close}>
            {t('common.cancel')}
          </Button>
          <Button
            disabled={!value.trim()}
            loading={save.isPending}
            onClick={() => event && save.mutate({ id: event.id, n: value.trim() })}
            data-testid="confirm-save-template"
          >
            {t('common.save', 'Speichern')}
          </Button>
        </Group>
      }
    >
      <TextInput
        label={t('events.templates.name', 'Name der Vorlage')}
        value={value}
        onChange={(e) => setName(e.currentTarget.value)}
        maxLength={255}
        data-autofocus
      />
    </Modal>
  )
}
