import { Group, Text } from '@mantine/core'

/** Green (ok), red (failed) or amber (null: not checked / not set up). */
export function Dot({ ok }: { ok: boolean | null }) {
  const color = ok === null ? '#c2870f' : ok ? '#1f9d57' : '#c0392b'
  return (
    <span
      style={{ width: 10, height: 10, borderRadius: '50%', background: color, flexShrink: 0 }}
    />
  )
}

export function Row({
  ok,
  label,
  children,
}: {
  ok: boolean | null
  label: string
  children: React.ReactNode
}) {
  return (
    <Group gap={12} wrap="nowrap" py={8} style={{ borderBottom: '1px solid var(--hb-border)' }}>
      <Dot ok={ok} />
      <Text size="sm" c="dimmed" miw={160}>
        {label}
      </Text>
      <div style={{ minWidth: 0, flex: 1 }}>{children}</div>
    </Group>
  )
}
