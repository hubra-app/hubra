import { Alert, Badge, Button, Group, Paper, Stack, Text } from '@mantine/core'
import { Modal } from '@/components/ui'
import { ROLE_TEMPLATES, type RoleTemplate } from '@/data/roleTemplates'
import { useT } from '@/locales/i18n'

export function TemplatesModal({
  open,
  onClose,
  onApply,
  applying,
}: {
  open: boolean
  onClose: () => void
  onApply: (template: RoleTemplate) => void
  applying: boolean
}) {
  const { t } = useT()
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t('roles.templatesTitle', 'Rollenvorlagen')}
      subtitle={t(
        'roles.templatesSubtitle',
        'Wende einen vorbereiteten Satz an Rollen und Berechtigungen an.',
      )}
      wide
    >
      <Stack gap={16}>
        <Alert color="blue" variant="light">
          {t(
            'roles.templateWarning',
            'Eine Vorlage legt fehlende Rollen an und setzt ihre Berechtigungen. Bei bestehenden Rollen mit gleichem Namen werden die Berechtigungen ersetzt.',
          )}
        </Alert>
        {ROLE_TEMPLATES.map((template) => (
          <Paper key={template.id} withBorder p="md" radius="md">
            <Group justify="space-between" align="flex-start">
              <Stack gap={4} style={{ flex: 1 }}>
                <Text fw={700}>{template.name}</Text>
                <Text size="sm" c="dimmed">
                  {template.description}
                </Text>
                <Group gap={6} mt={4}>
                  {template.roles.map((r) => (
                    <Badge
                      key={r.name}
                      size="sm"
                      color={r.is_admin ? 'indigo' : 'gray'}
                      variant={r.is_admin ? 'light' : 'outline'}
                    >
                      {r.name}
                      {r.is_admin ? ' (admin)' : ` (${r.permissions.length} perms)`}
                    </Badge>
                  ))}
                </Group>
              </Stack>
              <Button
                size="sm"
                variant="default"
                loading={applying}
                onClick={() => onApply(template)}
              >
                {t('roles.apply', 'Anwenden')}
              </Button>
            </Group>
          </Paper>
        ))}
      </Stack>
    </Modal>
  )
}
