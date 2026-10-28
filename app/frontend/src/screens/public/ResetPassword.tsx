import { useState } from 'react'
import { PasswordInput, Button, Alert, Text } from '@mantine/core'
import { useT } from '@/locales/i18n'
import { IconArrowLeft, IconCheck, IconKey } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import * as authApi from '@/api/auth'

export function ResetPassword() {
  const { t } = useT()
  const navigate = useNavigate()
  const hashParams = new URLSearchParams(
    typeof window !== 'undefined' ? window.location.hash.replace(/^#/, '') : '',
  )
  const token = hashParams.get('token') ?? ''

  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)

  const handleReset = async () => {
    setError('')
    if (password.length < 8) {
      setError(t('auth.passwordLength'))
      return
    }
    if (password !== confirm) {
      setError(t('auth.passwordMismatch'))
      return
    }
    setLoading(true)
    try {
      await authApi.resetPassword(token, password)
      setDone(true)
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : t('auth.reset.invalidToken'),
      )
    } finally {
      setLoading(false)
    }
  }

  if (!token) {
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
        <div style={{ maxWidth: 380, textAlign: 'center' }}>
          <p
            style={{
              color: '#b91c1c',
              fontSize: 'var(--mantine-font-size-sm)',
              marginBottom: 20,
            }}
          >
            {t('auth.reset.invalidToken')}
          </p>
          <Button
            variant="subtle"
            style={{ gap: 8 }}
            onClick={() => navigate('/forgot-password')}
          >
            <IconArrowLeft size={16} /> {t('auth.reset.requestNewLink')}
          </Button>
        </div>
      </div>
    )
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

        {!done ? (
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
              <IconKey size={22} color="#8a6a00" />
            </div>
            <h2
              style={{
                fontSize: 'var(--mantine-font-size-xl)',
                fontWeight: 700,
                color: '#181818',
                margin: '0 0 6px',
              }}
            >
              {t('auth.reset.title')}
            </h2>
            <p
              style={{
                fontSize: 'var(--mantine-font-size-sm)',
                color: '#6b7480',
                margin: '0 0 28px',
              }}
            >
              {t('auth.reset.chooseStrong')}
            </p>

            {error && (
              <Alert color="red" variant="light" mb={16}>
                {error}
              </Alert>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div>
                <Text component="label" size="sm" fw={600} c="dimmed">
                  {t('auth.newPassword')}
                </Text>
                <PasswordInput
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleReset()}
                  autoFocus
                />
              </div>
              <div>
                <Text component="label" size="sm" fw={600} c="dimmed">
                  {t('auth.confirmPassword')}
                </Text>
                <PasswordInput
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleReset()}
                />
              </div>
              <Button
                variant="filled"
                style={{ height: 44, fontSize: 'var(--mantine-font-size-md)' }}
                onClick={handleReset}
                disabled={loading || !password || !confirm}
              >
                {loading
                  ? t('auth.reset.updating')
                  : t('auth.reset.setNewPassword')}
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
              {t('auth.reset.done')}
            </h2>
            <p
              style={{
                fontSize: 'var(--mantine-font-size-sm)',
                color: '#6b7480',
                margin: '0 0 28px',
              }}
            >
              {t('auth.reset.canNowLogin')}
            </p>
            <Button
              variant="filled"
              style={{
                height: 44,
                fontSize: 'var(--mantine-font-size-md)',
                width: '100%',
              }}
              onClick={() => navigate('/login')}
            >
              {t('auth.reset.login')} {'\u2192'}
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
