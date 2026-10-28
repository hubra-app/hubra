import { useEffect, useState } from 'react'
import { Button } from '@mantine/core'
import { useNavigate } from 'react-router-dom'
import { useT } from '@/locales/i18n'
import { IconCheck, IconCircleX, IconLoader2 } from '@tabler/icons-react'
import * as authApi from '@/api/auth'

type State = 'verifying' | 'success' | 'error'

export function VerifyEmail() {
  const { t } = useT()
  const navigate = useNavigate()
  const hashParams = new URLSearchParams(
    typeof window !== 'undefined' ? window.location.hash.replace(/^#/, '') : '',
  )
  const token = hashParams.get('token')

  const [state, setState] = useState<State>(token ? 'verifying' : 'error')
  const [message, setMessage] = useState(
    token ? '' : t('verify.missingToken', 'Verifikations-Token fehlt.'),
  )

  useEffect(() => {
    if (!token) return
    let cancelled = false
    authApi
      .verifyEmail(token)
      .then(() => {
        if (!cancelled) setState('success')
      })
      .catch((err) => {
        if (cancelled) return
        setState('error')
        setMessage(
          err.message ??
            t('verify.verification.failed', 'Verifikation fehlgeschlage.'),
        )
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#f5f6f8',
        padding: 24,
      }}
    >
      <div
        style={{
          background: '#fff',
          borderRadius: 16,
          padding: '48px 40px',
          boxShadow: '0 4px 24px rgba(0,0,0,0.06)',
          textAlign: 'center',
          maxWidth: 420,
          width: '100%',
        }}
      >
        {state === 'verifying' && (
          <>
            <div
              style={{
                width: 56,
                height: 56,
                borderRadius: '50%',
                background: 'rgba(99,102,241,.12)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 20px',
              }}
            >
              <IconLoader2 size={28} color="#6366f1" className="spin" />
            </div>
            <h2
              style={{
                fontSize: 'var(--mantine-font-size-xl)',
                fontWeight: 700,
                color: '#181818',
                margin: '0 0 8px',
              }}
            >
              {t('verify.verifyingEmail', 'E-Mail wird verifiziert')}
            </h2>
            <p
              style={{
                fontSize: 'var(--mantine-font-size-sm)',
                color: '#6b7480',
                margin: 0,
              }}
            >
              {t(
                'verify.pleaseWait',
                'Bitte warte, währed mir dini E-Mail-Adresse bestätiged…',
              )}
            </p>
          </>
        )}

        {state === 'success' && (
          <>
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
              {t('verify.email.verified', 'E-Mail verifiziert')}
            </h2>
            <p
              style={{
                fontSize: 'var(--mantine-font-size-sm)',
                color: '#6b7480',
                margin: '0 0 28px',
              }}
            >
              {t(
                'verify.email.confirmedMsg',
                'Dini private E-Mail isch bestätigt worde. Du chasch jetzt Mail-Witergleiti aktiviere.',
              )}
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
              {t('verify.login', 'Aamälde')} →
            </Button>
          </>
        )}

        {state === 'error' && (
          <>
            <div
              style={{
                width: 56,
                height: 56,
                borderRadius: '50%',
                background: 'rgba(220,38,38,.12)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 20px',
              }}
            >
              <IconCircleX size={28} color="#dc2626" />
            </div>
            <h2
              style={{
                fontSize: 'var(--mantine-font-size-xl)',
                fontWeight: 700,
                color: '#181818',
                margin: '0 0 8px',
              }}
            >
              {t(
                'verify.verification.failedTitle',
                'Verifikation fehlgeschlage',
              )}
            </h2>
            <p
              style={{
                fontSize: 'var(--mantine-font-size-sm)',
                color: '#6b7480',
                margin: '0 0 28px',
              }}
            >
              {message}
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
              {t('common.backToLogin', 'Zrugg zue Aamäldig')}
            </Button>
          </>
        )}
      </div>
    </div>
  )
}
