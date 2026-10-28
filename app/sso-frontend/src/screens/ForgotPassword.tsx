import { useState } from 'react'
import { TextInput, Button, Text } from '@mantine/core'
import { useForm } from '@mantine/form'
import { zodResolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { IconArrowLeft, IconCheck, IconMail } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import * as authApi from '@/api/auth'

const schema = z.object({
  email: z.string().email('Invalid email'),
})

type FormValues = z.infer<typeof schema>

export function ForgotPassword() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)

  const form = useForm<FormValues>({
    validate: zodResolver(schema),
    initialValues: { email: '' },
  })

  const handleSubmit = async (values: FormValues) => {
    setLoading(true)
    try {
      await authApi.forgotPassword(values.email.trim().toLowerCase())
      setSent(true)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="graph-bg"
      style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 32 }}
    >
      <div style={{ width: '100%', maxWidth: 380 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 32 }}>
          <div className="logo-mark" />
          <div>
            <div style={{ fontSize: 'var(--mantine-font-size-md)', fontWeight: 700, color: '#181818' }}>Hubra</div>
            <div style={{ fontSize: 'var(--mantine-font-size-xs)', color: '#8a6a00', fontFamily: '"JetBrains Mono"', letterSpacing: '0.06em' }}>
              Makerspace · Schwyz
            </div>
          </div>
        </div>

        {!sent ? (
          <>
            <div
              style={{
                width: 48, height: 48, borderRadius: '50%', background: '#fffbea',
                border: '1.5px solid #fece2b55', display: 'flex', alignItems: 'center',
                justifyContent: 'center', marginBottom: 20,
              }}
            >
              <IconMail size={22} color="#8a6a00" />
            </div>
            <h2 style={{ fontSize: 'var(--mantine-font-size-xl)', fontWeight: 700, color: '#181818', margin: '0 0 6px' }}>
              Reset your password
            </h2>
            <p style={{ fontSize: 'var(--mantine-font-size-sm)', color: '#6b7480', margin: '0 0 28px' }}>
              Enter your email and we'll send you a reset link.
            </p>

            <form onSubmit={form.onSubmit(handleSubmit)}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div>
                  <Text component="label" size="sm" fw={600} c="dimmed">Email</Text>
                  <TextInput
                    type="email"
                    {...form.getInputProps('email')}
                    autoFocus
                  />
                </div>
                <Button
                  type="submit"
                  variant="filled"
                  style={{ height: 44, fontSize: 'var(--mantine-font-size-md)' }}
                  loading={loading}
                  disabled={loading}
                >
                  {loading ? 'Sending…' : 'Send reset link'}
                </Button>
                <Button variant="subtle" style={{ gap: 8 }} onClick={() => navigate('/login')}>
                  <IconArrowLeft size={16} /> Back to login
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
            <h2 style={{ fontSize: 'var(--mantine-font-size-xl)', fontWeight: 700, color: '#181818', margin: '0 0 8px' }}>
              Check your inbox
            </h2>
            <p style={{ fontSize: 'var(--mantine-font-size-sm)', color: '#6b7480', margin: '0 0 28px', lineHeight: 1.6 }}>
              If an account exists for {form.values.email}, a password reset link has been sent.
            </p>
            <Button variant="subtle" style={{ gap: 8 }} onClick={() => navigate('/login')}>
              <IconArrowLeft size={16} /> Back to login
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
