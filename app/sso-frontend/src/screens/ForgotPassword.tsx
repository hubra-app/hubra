import { useState } from 'react'
import { TextInput, Button, Text } from '@mantine/core'
import { useForm } from '@mantine/form'
import { zodResolver } from 'mantine-form-zod-resolver'
import { z } from 'zod'
import { IconArrowLeft, IconCheck, IconMail } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import * as authApi from '@/api/auth'
import { tr, useLang } from '@/lang'

const makeSchema = () =>
  z.object({
    email: z.string().email(tr('Ungültige E-Mail-Adresse', 'Invalid email')),
  })

type FormValues = z.infer<ReturnType<typeof makeSchema>>

export function ForgotPassword() {
  useLang()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)

  const form = useForm<FormValues>({
    validate: zodResolver(makeSchema()),
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
            <div className="wordmark" style={{ fontSize: 20, color: '#1a1625' }}>hubra</div>
            <div style={{ fontSize: 'var(--mantine-font-size-xs)', color: '#6131c4', fontFamily: '"JetBrains Mono"', letterSpacing: '0.06em' }}>
              {tr('Vereinsverwaltung', 'Club management')}
            </div>
          </div>
        </div>

        {!sent ? (
          <>
            <div
              style={{
                width: 48, height: 48, borderRadius: '50%', background: '#f5f1ff',
                border: '1.5px solid #7441e055', display: 'flex', alignItems: 'center',
                justifyContent: 'center', marginBottom: 20,
              }}
            >
              <IconMail size={22} color="#6131c4" />
            </div>
            <h2 style={{ fontSize: 'var(--mantine-font-size-xl)', fontWeight: 700, color: '#1a1625', margin: '0 0 6px' }}>
              {tr('Passwort zurücksetzen', 'Reset your password')}
            </h2>
            <p style={{ fontSize: 'var(--mantine-font-size-sm)', color: '#5e5873', margin: '0 0 28px' }}>
              {tr(
                'Gib deine E-Mail-Adresse ein. Wir schicken dir einen Link für ein neues Passwort.',
                "Enter your email and we'll send you a reset link.",
              )}
            </p>

            <form onSubmit={form.onSubmit(handleSubmit)}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div>
                  <Text component="label" size="sm" fw={600} c="dimmed">{tr('E-Mail', 'Email')}</Text>
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
                  {loading ? tr('Wird gesendet …', 'Sending…') : tr('Link senden', 'Send reset link')}
                </Button>
                <Button variant="subtle" style={{ gap: 8 }} onClick={() => navigate('/login')}>
                  <IconArrowLeft size={16} /> {tr('Zurück zur Anmeldung', 'Back to login')}
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
              {tr('Schau in dein Postfach', 'Check your inbox')}
            </h2>
            <p style={{ fontSize: 'var(--mantine-font-size-sm)', color: '#5e5873', margin: '0 0 28px', lineHeight: 1.6 }}>
              {tr(
                `Falls es ein Konto für ${form.values.email} gibt, haben wir einen Link zum Zurücksetzen geschickt.`,
                `If an account exists for ${form.values.email}, a password reset link has been sent.`,
              )}
            </p>
            <Button variant="subtle" style={{ gap: 8 }} onClick={() => navigate('/login')}>
              <IconArrowLeft size={16} /> {tr('Zurück zur Anmeldung', 'Back to login')}
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
