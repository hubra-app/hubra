import { useState } from 'react'
import { TextInput, Button, Text } from '@mantine/core'
import { useT } from '@/locales/i18n'
import { IconArrowLeft, IconCheck, IconMail } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import * as authApi from '@/api/auth'

export function ForgotPassword() {
  const { t } = useT()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)

  const handleSubmit = async () => {
    if (!email.trim()) return
    setLoading(true)
    try {
      await authApi.forgotPassword(email.trim().toLowerCase())
      setSent(true)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="graph-bg"
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 32,
      }}
    >
      <div style={{ width: '100%', maxWidth: 380 }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            marginBottom: 32,
          }}
        >
          <div className="logo-mark" />
          <div>
            <div
              style={{
                fontSize: 'var(--mantine-font-size-md)',
                fontWeight: 700,
                color: '#181818',
              }}
            >
              VollBuild
            </div>
            <div
              style={{
                fontSize: 'var(--mantine-font-size-xs)',
                color: '#8a6a00',
                fontFamily: '"JetBrains Mono"',
                letterSpacing: '0.06em',
              }}
            >
              Makerspace �? Schwyz
            </div>
          </div>
        </div>

        {!sent ? (
          <>
            <div
              style={{
                width: 48,
                height: 48,
                borderRadius: '50%',
                background: '#fffbea',
                border: '1.5px solid #fece2b55',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: 20,
              }}
            >
              <IconMail size={22} color="#8a6a00" />
            </div>
            <h2
              style={{
                fontSize: 'var(--mantine-font-size-xl)',
                fontWeight: 700,
                color: '#181818',
                margin: '0 0 6px',
              }}
            >
              {t('auth.forgot.title')}
            </h2>
            <p
              style={{
                fontSize: 'var(--mantine-font-size-sm)',
                color: '#6b7480',
                margin: '0 0 28px',
              }}
            >
              {t('auth.forgot.enterEmail')}
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div>
                <Text component="label" size="sm" fw={600} c="dimmed">
                  {t('common.email')}
                </Text>
                <TextInput
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
                  autoFocus
                />
              </div>
              <Button
                variant="filled"
                style={{ height: 44, fontSize: 'var(--mantine-font-size-md)' }}
                onClick={handleSubmit}
                disabled={loading || !email.trim()}
              >
                {loading ? t('auth.sending') : t('auth.forgot.sendResetLink')}
              </Button>
              <Button
                variant="subtle"
                style={{ gap: 8 }}
                onClick={() => navigate('/login')}
              >
                <IconArrowLeft size={16} /> {t('auth.backToLogin')}
              </Button>
            </div>
          </>
        ) : (
          <div style={{ textAlign: 'center' }}>
            <div
              style={{
                width: 56,
                height: 56,
                borderRadius: '50%',
                background: 'rgba(31,157,87,.12)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 20px',
              }}
            >
              <IconCheck size={28} color="#1f9d57" />
            </div>
            <h2
              style={{
                fontSize: 'var(--mantine-font-size-xl)',
                fontWeight: 700,
                color: '#181818',
                margin: '0 0 8px',
              }}
            >
              {t('auth.forgot.checkInbox')}
            </h2>
            <p
              style={{
                fontSize: 'var(--mantine-font-size-sm)',
                color: '#6b7480',
                margin: '0 0 28px',
                lineHeight: 1.6,
              }}
            >
              {t('auth.forgot.ifEmailRegistered', { email })}
            </p>
            <Button
              variant="subtle"
              style={{ gap: 8 }}
              onClick={() => navigate('/login')}
            >
              <IconArrowLeft size={16} /> {t('auth.backToLogin')}
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
