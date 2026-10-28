interface ComingSoonProps {
  title?: string
  description?: string
}

export function ComingSoon({
  title = 'Coming Soon',
  description,
}: ComingSoonProps) {
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#fffbea',
        zIndex: 10,
        pointerEvents: 'all',
      }}
    >
      <span style={{ fontSize: 48, marginBottom: 20 }}>🚧</span>
      <div
        style={{
          fontSize: 'var(--mantine-font-size-xl)',
          fontWeight: 700,
          color: '#8a6a00',
          marginBottom: description ? 12 : 0,
        }}
      >
        {title}
      </div>
      {description && (
        <p
          style={{
            margin: 0,
            fontSize: 'var(--mantine-font-size-sm)',
            color: '#8a6a00',
            lineHeight: 1.6,
            textAlign: 'center',
            maxWidth: 400,
          }}
        >
          {description}
        </p>
      )}
    </div>
  )
}
