import type { ReactNode } from 'react'
import { Badge, Select } from '@mantine/core'
import { IconUsersGroup } from '@tabler/icons-react'
import { Field } from '@/components/form'
import { useT } from '@/locales/i18n'
import type { ContentGroupScope } from './contentGroups'

/** The "Gruppe" select for an event, post or poll form. */
export function GroupField({
  scope,
  value,
  onChange,
  error,
  hint,
}: {
  scope: ContentGroupScope
  value: string
  onChange: (value: string) => void
  error?: ReactNode
  hint?: string
}) {
  const { t } = useT()
  if (!scope.mayGroups) return null
  // Keep a group the item already has in the list, even if the editor does
  // not manage it (an admin's choice stays readable).
  const options = scope.ownGroups.map((g) => ({ value: g.id, label: g.name }))
  if (value && !options.some((o) => o.value === value)) {
    options.push({ value, label: scope.groupName(value) ?? value })
  }
  const data = scope.clubWide
    ? [{ value: '', label: t('events.noGroup', 'Für alle') }, ...options]
    : options
  return (
    <Field label={t('content.group', 'Gruppe') + (scope.clubWide ? ' (optional)' : '')} hint={hint}>
      <Select
        data={data}
        value={value}
        onChange={(v) => onChange(v ?? '')}
        error={error}
        searchable
        allowDeselect={false}
      />
    </Field>
  )
}

/** A small label naming the group a post or poll belongs to. */
export function GroupBadge({ name }: { name: string | null }) {
  if (!name) return null
  return (
    <Badge
      variant="light"
      color="gray"
      size="sm"
      leftSection={<IconUsersGroup size={12} />}
      style={{ textTransform: 'none' }}
    >
      {name}
    </Badge>
  )
}
