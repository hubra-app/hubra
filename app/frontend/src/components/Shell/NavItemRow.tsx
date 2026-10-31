import type { MouseEvent } from 'react'
import { Link } from 'react-router-dom'
import { UnstyledButton, Badge, Box } from '@mantine/core'
import type { NavItem } from './nav'

export function NavItemRow({
  item,
  activePath,
  go,
  collapsed,
}: {
  item: NavItem
  activePath: string
  go: (path: string) => void
  collapsed: boolean
}) {
  const active = activePath === item.path

  // A real link, so it can be opened in a new tab; a plain click navigates
  // through `go`, which also closes the open menus.
  const handleClick = (e: MouseEvent) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return
    e.preventDefault()
    go(item.path)
  }

  if (collapsed) {
    return (
      <UnstyledButton
        component={Link}
        to={item.path}
        onClick={handleClick}
        title={item.label}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: 44,
          height: 44,
          borderRadius: 10,
          color: active ? 'var(--mantine-color-acc-8)' : 'var(--hb-text-2)',
          background: active ? 'var(--mantine-color-acc-1)' : undefined,
        }}
        className="nav-item"
        data-active={active || undefined}
      >
        {item.icon}
      </UnstyledButton>
    )
  }

  return (
    <Box>
      <UnstyledButton
        component={Link}
        to={item.path}
        onClick={handleClick}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          borderRadius: 10,
          padding: '8px 12px',
          minHeight: 40,
          width: '100%',
          color: active ? 'var(--mantine-color-acc-8)' : 'var(--hb-text-2)',
          background: active ? 'var(--mantine-color-acc-1)' : undefined,
          fontSize: 'var(--mantine-font-size-sm)',
          fontWeight: active ? 700 : 500,
          transition: 'background .15s, color .15s',
        }}
        className="nav-item"
        data-active={active || undefined}
        aria-current={active ? 'page' : undefined}
      >
        <span
          style={{
            flexShrink: 0,
            display: 'flex',
            color: active ? 'var(--mantine-color-acc-text)' : 'var(--hb-text-2)',
          }}
        >
          {item.icon}
        </span>
        <span style={{ flex: 1, fontSize: 'var(--mantine-font-size-sm)' }}>
          {item.label}
        </span>
        {item.count !== undefined && (
          <Badge
            variant={active ? 'white' : 'light'}
            size="sm"
            color={active ? 'acc' : 'gray'}
            radius="xl"
            ff="'JetBrains Mono', monospace"
            title={item.countTitle}
            aria-label={item.countTitle}
          >
            {item.count}
          </Badge>
        )}
      </UnstyledButton>
    </Box>
  )
}
