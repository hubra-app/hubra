import { useState } from 'react'
import { PasswordInput, Button, Alert, Text } from '@mantine/core'
import { useForm } from '@mantine/form'
import { zodResolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { IconArrowLeft, IconCheck, IconKey } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import * as authApi from '@/api/auth'

const schema = z
  .object({
    password: z.string().min(8, 'Password must be at least 8 characters'),
    confirm: z.string(),
  })
  .refine((d) => d.password === d.confirm, {
    message: 'Passwords do not match',
    path: ['confirm'],
  })

type FormValues = z.infer<typeof schema>

export function ResetPassword() {
  const navigate = useNavigate()
  const hashParams = new URLSearchParams(
    typeof window !== 'undefined' ? window.location.hash.replace(/^#/, '') : '',
  )
  const token = hashParams.get('token') ?? ''

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)

  const form = useForm<FormValues>({
    validate: zodResolver(schema),
    initialValues: { password: '', confirm: '' },
  })

  const handleReset = async (values: FormValues) => {
    setError('')
    setLoading(true)
    try {
      await authApi.resetPassword(token, values.password)
      setDone(true)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Invalid or expired token.')
    } finally {
      setLoading(false)
    }
  }

  if (!token) {
    return (
      <div className="graph-bg" style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 32 }}>
        <div style={{ maxWidth: 380, textAlign: 'center' }}>
          <p style={{ color: '#b91c1c', fontSize: 'var(--mantine-font-size-sm)', marginBottom: 20 }}>
            Invalid or missing reset token.
          </p>
          <Button variant="subtle" style={{ gap: 8 }} onClick={() => navigate('/forgot-password')}>
            <IconArrowLeft size={16} /> Request a new link
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="graph-bg" style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 32 }}>
      <div style={{ width: '100%', maxWidth: 380 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 32 }}>
          <div className="logo-mark" />
          <div>
            <div className="wordmark" style={{ fontSize: 20, color: '#1a1625' }}>hubra</div>
            <div style={{ fontSize: 'var(--mantine-font-size-xs)', color: '#6131c4', fontFamily: '"JetBrains Mono"', letterSpacing: '0.06em' }}>
              Makerspace · Schwyz
            </div>
          </div>
        </div>

        {!done ? (
          <>
            <div
              style={{
                width: 48, height: 48, borderRadius: '50%', background: '#f5f1ff',
                border: '1.5px solid #7441e055', display: 'flex', alignItems: 'center',
                justifyContent: 'center', marginBottom: 20,
              }}
            >
              <IconKey size={22} color="#6131c4" />
            </div>
            <h2 style={{ fontSize: 'var(--mantine-font-size-xl)', fontWeight: 700, color: '#1a1625', margin: '0 0 6px' }}>
              Set a new password
            </h2>
            <p style={{ fontSize: 'var(--mantine-font-size-sm)', color: '#5e5873', margin: '0 0 28px' }}>
              Choose a strong password for your account.
            </p>

            {error && <Alert color="red" variant="light" mb={16}>{error}</Alert>}

            <form onSubmit={form.onSubmit(handleReset)}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div>
                  <Text component="label" size="sm" fw={600} c="dimmed">New password</Text>
                  <PasswordInput
                    {...form.getInputProps('password')}
                    autoFocus
                  />
                </div>
                <div>
                  <Text component="label" size="sm" fw={600} c="dimmed">Confirm password</Text>
                  <PasswordInput
                    {...form.getInputProps('confirm')}
                  />
                </div>
                <Button
                  type="submit"
                  variant="filled"
                  style={{ height: 44, fontSize: 'var(--mantine-font-size-md)' }}
                  loading={loading}
                  disabled={loading}
                >
                  {loading ? 'Updating…' : 'Set new password'}
                </Button>
              </div>
            </form>
          </>
        ) : (
          <div style={{ textAlign: 'center' }}>
            <div
              style={{
                width: 56, height: 56, borderRadius: '50%', background: 'rgba(31,157,87,.12)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 20px',
              }}
            >
              <IconCheck size={28} color="#1f9d57" />
            </div>
            <h2 style={{ fontSize: 'var(--mantine-font-size-xl)', fontWeight: 700, color: '#1a1625', margin: '0 0 8px' }}>
              Password updated
            </h2>
            <p style={{ fontSize: 'var(--mantine-font-size-sm)', color: '#5e5873', margin: '0 0 28px' }}>
              You can now sign in with your new password.
            </p>
            <Button
              variant="filled"
              style={{ height: 44, fontSize: 'var(--mantine-font-size-md)', width: '100%' }}
              onClick={() => navigate('/login')}
            >
              Sign in →
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
