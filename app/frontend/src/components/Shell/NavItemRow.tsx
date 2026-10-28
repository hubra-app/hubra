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
          color: isActiveParent ? '#4d27a0' : '#5e5873',
          background: isActiveParent ? '#ebe3ff' : undefined,
        }}
        className="nav-item"
        data-active={isActiveParent || undefined}
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
          borderRadius: 10,
          padding: '8px 12px',
          minHeight: 40,
          width: '100%',
          color: isActiveParent ? '#4d27a0' : '#4a4560',
          background: isActiveParent ? '#ebe3ff' : undefined,
          fontSize: 'var(--mantine-font-size-sm)',
          fontWeight: isActiveParent ? 700 : 500,
          transition: 'background .15s, color .15s',
        }}
        className="nav-item"
        data-active={isActiveParent || undefined}
        aria-current={isActiveParent ? 'page' : undefined}
      >
        <span
          style={{
            flexShrink: 0,
            display: 'flex',
            color: isActiveParent ? '#7441e0' : '#5e5873',
          }}
        >
          {item.icon}
        </span>
        <span style={{ flex: 1, fontSize: 'var(--mantine-font-size-sm)' }}>
          {item.label}
        </span>
        {item.count !== undefined && (
          <Badge
            variant={isActiveParent ? 'white' : 'light'}
            size="sm"
            color={isActiveParent ? 'acc' : 'gray'}
            radius="xl"
            ff="'JetBrains Mono', monospace"
          >
            {item.count}
          </Badge>
        )}
      </UnstyledButton>
    </Box>
  )
}
