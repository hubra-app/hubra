import { useEffect, useState } from 'react'
import { Button } from '@mantine/core'
import { useNavigate } from 'react-router-dom'
import { IconCheck, IconCircleX, IconLoader2 } from '@tabler/icons-react'
import * as authApi from '@/api/auth'

type State = 'verifying' | 'success' | 'error'

export function VerifyEmail() {
  const navigate = useNavigate()
  const hashParams = new URLSearchParams(
    typeof window !== 'undefined' ? window.location.hash.replace(/^#/, '') : '',
  )
  const token = hashParams.get('token')

  const [state, setState] = useState<State>(token ? 'verifying' : 'error')
  const [message, setMessage] = useState(
    token ? '' : 'Verification token is missing.',
  )

  useEffect(() => {
    if (!token) return
    const ctrl = new AbortController()
    let cancelled = false
    authApi
      .verifyEmail(token, ctrl.signal)
      .then(() => {
        if (!cancelled) setState('success')
      })
      .catch((err) => {
        if (cancelled) return
        setState('error')
        const msg = err instanceof Error ? err.message : 'Verification failed.'
        setMessage(msg)
      })
    return () => {
      cancelled = true
      ctrl.abort()
    }
  }, [token])

  return (
    <div
      style={{
        minHeight: '100vh', display: 'flex', alignItems: 'center',
        justifyContent: 'center', background: '#f5f6f8', padding: 24,
      }}
    >
      <div
        style={{
          background: '#fff', borderRadius: 16, padding: '48px 40px',
          boxShadow: '0 4px 24px rgba(0,0,0,0.06)', textAlign: 'center',
          maxWidth: 420, width: '100%',
        }}
      >
        {state === 'verifying' && (
          <>
            <div
              style={{
                width: 56, height: 56, borderRadius: '50%', background: 'rgba(99,102,241,.12)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 20px',
              }}
            >
              <IconLoader2 size={28} color="#6366f1" className="spin" />
            </div>
            <h2 style={{ fontSize: 'var(--mantine-font-size-xl)', fontWeight: 700, color: '#181818', margin: '0 0 8px' }}>
              Verifying email…
            </h2>
            <p style={{ fontSize: 'var(--mantine-font-size-sm)', color: '#6b7480', margin: 0 }}>
              Please wait while we confirm your email address.
            </p>
          </>
        )}

        {state === 'success' && (
          <>
            <div
              style={{
                width: 56, height: 56, borderRadius: '50%', background: 'rgba(31,157,87,.12)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 20px',
              }}
            >
              <IconCheck size={28} color="#1f9d57" />
            </div>
            <h2 style={{ fontSize: 'var(--mantine-font-size-xl)', fontWeight: 700, color: '#181818', margin: '0 0 8px' }}>
              Email verified
            </h2>
            <p style={{ fontSize: 'var(--mantine-font-size-sm)', color: '#6b7480', margin: '0 0 28px' }}>
              Your email has been confirmed. You can now sign in.
            </p>
            <Button
              variant="filled"
              style={{ height: 44, fontSize: 'var(--mantine-font-size-md)', width: '100%' }}
              onClick={() => navigate('/login')}
            >
              Sign in →
            </Button>
          </>
        )}

        {state === 'error' && (
          <>
            <div
              style={{
                width: 56, height: 56, borderRadius: '50%', background: 'rgba(220,38,38,.12)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 20px',
              }}
            >
              <IconCircleX size={28} color="#dc2626" />
            </div>
            <h2 style={{ fontSize: 'var(--mantine-font-size-xl)', fontWeight: 700, color: '#181818', margin: '0 0 8px' }}>
              Verification failed
            </h2>
            <p style={{ fontSize: 'var(--mantine-font-size-sm)', color: '#6b7480', margin: '0 0 28px' }}>
              {message}
            </p>
            <Button
              variant="filled"
              style={{ height: 44, fontSize: 'var(--mantine-font-size-md)', width: '100%' }}
              onClick={() => navigate('/login')}
            >
              Back to login
            </Button>
          </>
        )}
      </div>
    </div>
  )
}
