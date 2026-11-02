import { useEffect, useRef } from 'react'
import { Box, Text, UnstyledButton } from '@mantine/core'
import { IconDotsVertical } from '@tabler/icons-react'
import { useAuth } from '@/context/AppContext'
import { roleLabels } from '@/roles'
import { UserMenu } from './UserMenu'
import { initials, contrastColor } from './nav'

/**
 * The user card at the foot of the sidebar and of the phone menu: who is
 * signed in, always in view. A tap opens the account menu above it; a tap
 * anywhere else or Escape closes it again.
 */
export function UserCard({
  opened,
  onChange,
}: {
  opened: boolean
  onChange: (opened: boolean) => void
}) {
  const { currentUser } = useAuth()
  const ref = useRef<HTMLDivElement>(null)
  const userName = currentUser?.name ?? ''
  const userRole = roleLabels(currentUser?.roles)
  const userBg = currentUser?.avatarColor ?? '#ebe8f2'

  useEffect(() => {
    if (!opened) return
    const onPointer = (e: PointerEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onChange(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onChange(false)
    }
    document.addEventListener('pointerdown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [opened, onChange])

  return (
    <Box ref={ref} style={{ position: 'relative' }}>
      {opened && <UserMenu onClose={() => onChange(false)} />}
      <UnstyledButton
        data-testid="user-card"
        onClick={() => onChange(!opened)}
        aria-expanded={opened}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          height: 52,
          padding: '0 10px',
          borderRadius: 12,
          border: '1px solid var(--hb-border)',
          background: 'var(--hb-surface)',
        }}
      >
        <Box
          style={{
            width: 34,
            height: 34,
            borderRadius: '50%',
            background: userBg,
            fontSize: 'var(--mantine-font-size-xs)',
            fontWeight: 700,
            color: contrastColor(userBg),
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          {initials(userName)}
        </Box>
        <Box style={{ flex: 1, textAlign: 'left', minWidth: 0 }}>
          <Text fz="sm" fw={600} lh={1.2} truncate>
            {userName}
          </Text>
          <Text fz="xs" c="dimmed" truncate>
            {userRole}
          </Text>
        </Box>
        <IconDotsVertical
          size={16}
          style={{ color: 'var(--mantine-color-dimmed)', flexShrink: 0 }}
        />
      </UnstyledButton>
    </Box>
  )
}
