import { UnstyledButton, Badge, Box } from '@mantine/core'
import type { NavItem } from './nav'
import { getParentPath } from './nav'

export function NavItemRow({
  item,
  pathname,
  go,
  collapsed,
}: {
  item: NavItem
  pathname: string
  go: (path: string) => void
  collapsed: boolean
}) {
  const parent = getParentPath(pathname)
  const isActiveParent = parent === item.path

  const handleClick = () => {
    go(item.path)
  }

  if (collapsed) {
    return (
      <UnstyledButton
        onClick={handleClick}
        title={item.label}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: 44,
          height: 44,
          borderRadius: 10,
          color: isActiveParent ? '#6131c4' : 'var(--mantine-color-dimmed)',
          background: isActiveParent ? 'rgba(116,65,224,.2)' : undefined,
        }}
      >
        {item.icon}
      </UnstyledButton>
    )
  }

  return (
    <Box>
      <UnstyledButton
        onClick={handleClick}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          borderRadius: 9,
          padding: '9px 11px',
          width: '100%',
          color: isActiveParent ? '#6131c4' : 'var(--mantine-color-dimmed)',
          background: isActiveParent ? 'rgba(116,65,224,.2)' : undefined,
          fontSize: 'var(--mantine-font-size-sm)',
          fontWeight: 500,
          transition: 'background .15s, color .15s',
        }}
      >
        <span style={{ flexShrink: 0 }}>{item.icon}</span>
        <span style={{ flex: 1, fontSize: 'var(--mantine-font-size-sm)' }}>
          {item.label}
        </span>
        {item.count !== undefined && (
          <Badge
            variant="light"
            size="xs"
            color="gray"
            ff="'JetBrains Mono', monospace"
          >
            {item.count}
          </Badge>
        )}
      </UnstyledButton>
    </Box>
  )
}
