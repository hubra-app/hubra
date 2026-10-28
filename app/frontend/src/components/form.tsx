import { Switch, SegmentedControl, Text } from '@mantine/core'
import type { ReactNode } from 'react'

export function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: ReactNode
}) {
  return (
    <div>
      <Text component="label" size="sm" fw={600} c="dimmed" mb={6}>
        {label}
      </Text>
      {children}
      {hint && (
        <Text size="xs" c="dimmed" mt={4}>
          {hint}
        </Text>
      )}
    </div>
  )
}

export function Toggle({
  checked,
  onChange,
  disabled,
}: {
  checked: boolean
  onChange: (v: boolean) => void
  disabled?: boolean
}) {
  return (
    <Switch
      checked={checked}
      onChange={(e) => onChange(e.currentTarget.checked)}
      disabled={disabled}
      size="md"
      color="acc.4"
    />
  )
}

export function Seg({
  options,
  value,
  onChange,
}: {
  options: { value: string; label: string }[]
  value: string
  onChange: (v: string) => void
}) {
  return (
    <SegmentedControl
      value={value}
      onChange={onChange}
      data={options.map((o) => ({ value: o.value, label: o.label }))}
      size="sm"
      radius="sm"
    />
  )
}
