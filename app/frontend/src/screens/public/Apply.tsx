import { useState, useEffect, useMemo } from 'react'
import { TextInput, Textarea, Button, Alert, Text } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { useT } from '@/locales/i18n'
import { IconCheck, IconArrowLeft } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import { submitApplication } from '@/api/applications'
import { getLookups } from '@/api/lookups'

const TIER_DESCRIPTIONS: Record<string, string> = {
  Maker: 'Voller Zuegriff uf alli Wärchzeug un Rüüm.',
  Pro: 'Unlimitierte Zuegriff + Prioritäts-Buchig.',
  Student: 'Reduzierti Rate für Studierende.',
  Workshop: 'Eidögige Workshop-Zuegriff.',
}

export function ApplyScreen() {
  const { t } = useT()
  const navigate = useNavigate()
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [email, setEmail] = useState('')
  const [tier, setTier] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)

  const { data: lookupsData } = useQuery({
    queryKey: ['lookups'],
    queryFn: () => getLookups(),
  })

  const tiers = useMemo(
    () =>
      lookupsData
        ? [...lookupsData.tiersByName.entries()].map(([name, id]) => ({
            id,
            name,
          }))
        : [],
    [lookupsData],
  )

  useEffect(() => {
    if (tiers.length && !tier) {
      queueMicrotask(() => setTier(tiers[0].name))
    }
  }, [tiers, tier])

  const valid = firstName.trim() && lastName.trim() && email.includes('@')

  const handleSubmit = async () => {
    if (!valid) return
    setError('')
    setLoading(true)
    try {
      const selectedTier = tiers.find((t) => t.name === tier)
      await submitApplication({
        firstName: firstName.trim(),
        lastName: lastName.trim(),
        email: email.trim().toLowerCase(),
        wantsTierId: selectedTier?.id,
        message: message.trim(),
      })
      setDone(true)
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : t(
              'apply.submissionFailed',
              'Ingab fehlgeschlage. Bitte nöchstmol versueche.',
            ),
      )
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
      <div style={{ width: '100%', maxWidth: 460 }}>
        {/* Brand */}
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
                color: '#1a1625',
              }}
            >
              VollBuild
            </div>
            <div
              style={{
                fontSize: 'var(--mantine-font-size-xs)',
                color: '#6131c4',
                fontFamily: '"JetBrains Mono"',
                letterSpacing: '0.06em',
              }}
            >
              Makerspace ? Schwyz
            </div>
          </div>
        </div>

        {!done ? (
          <>
            <h2
              style={{
                fontSize: 'var(--mantine-font-size-xl)',
                fontWeight: 700,
                color: '#1a1625',
                margin: '0 0 6px',
              }}
            >
              {t('apply.applyForMembership', 'Für Mitgliedschaft bewärbe')}
            </h2>
            <p
              style={{
                fontSize: 'var(--mantine-font-size-sm)',
                color: '#5e5873',
                margin: '0 0 28px',
              }}
            >
              {t(
                'apply.fillInDetails',
                'Füll dini Date i ond mir überprüfed di Bewerbig.',
              )}
            </p>

            {error && (
              <Alert color="red" variant="light" mb={16}>
                {error}
              </Alert>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div
                className="grid-2"
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr',
                  gap: 12,
                }}
              >
                <div>
                  <Text component="label" size="sm" fw={600} c="dimmed">
                    {t('common.firstName', 'Vorname')}
                  </Text>
                  <TextInput
                    value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
                    placeholder={t('apply.firstNamePlaceholder', 'Anna')}
                    autoFocus
                  />
                </div>
                <div>
                  <Text component="label" size="sm" fw={600} c="dimmed">
                    {t('common.lastName', 'Nachname')}
                  </Text>
                  <TextInput
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                    placeholder={t('apply.lastNamePlaceholder', 'Zimmermann')}
                  />
                </div>
              </div>

              <div>
                <Text component="label" size="sm" fw={600} c="dimmed">
                  {t('common.email', 'E-Mail')}
                </Text>
                <TextInput
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder={t('apply.emailPlaceholder', 'anna@beispiel.ch')}
                />
              </div>

              {tiers.length > 0 && (
                <div>
                  <Text component="label" size="sm" fw={600} c="dimmed">
                    {t('apply.membershipTier', 'Mitgliedschaft-Stuf')}
                  </Text>
                  <div
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 8,
                      marginTop: 8,
                    }}
                  >
                    {tiers.map((t) => (
                      <label
                        key={t.name}
                        onClick={() => setTier(t.name)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 12,
                          padding: '10px 14px',
                          border: `1.5px solid ${
                            tier === t.name ? '#7441e0' : '#d6d2e3'
                          }`,
                          borderRadius: 9,
                          cursor: 'pointer',
                          background:
                            tier === t.name
                              ? 'rgba(116,65,224,.08)'
                              : 'transparent',
                          transition: 'all .12s',
                        }}
                      >
                        <div
                          style={{
                            width: 16,
                            height: 16,
                            borderRadius: '50%',
                            flexShrink: 0,
                            border: `2px solid ${
                              tier === t.name ? '#7441e0' : '#d6d2e3'
                            }`,
                            background:
                              tier === t.name ? '#7441e0' : 'transparent',
                          }}
                        />
                        <div>
                          <div
                            style={{
                              fontSize: 'var(--mantine-font-size-sm)',
                              fontWeight: 600,
                              color: '#1a1625',
                            }}
                          >
                            {t.name}
                          </div>
                          <div
                            style={{
                              fontSize: 'var(--mantine-font-size-xs)',
                              color: '#5e5873',
                            }}
                          >
                            {TIER_DESCRIPTIONS[t.name] ?? ''}
                          </div>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>
              )}

              <div>
                <Text component="label" size="sm" fw={600} c="dimmed">
                  {t('apply.message', 'Nachricht')}{' '}
                  <span style={{ color: '#8c86a0', fontWeight: 400 }}>
                    ({t('common.optional', 'optional')})
                  </span>
                </Text>
                <Textarea
                  rows={3}
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder={t(
                    'apply.messagePlaceholder',
                    'Erzähl e bitzeli über di selber ond was du gärn mached…',
                  )}
                />
              </div>

              <Button
                variant="filled"
                style={{
                  height: 44,
                  fontSize: 'var(--mantine-font-size-md)',
                  marginTop: 4,
                }}
                onClick={handleSubmit}
                disabled={loading || !valid}
              >
                {loading
                  ? t('apply.submitting', 'Wird iglah…')
                  : t('apply.submitApplication', 'Bewerbig iireiche')}
              </Button>

              <Button
                variant="subtle"
                style={{ gap: 8 }}
                onClick={() => navigate('/login')}
              >
                <IconArrowLeft size={16} />{' '}
                {t('common.backToLogin', 'Zrugg zue Aamäldig')}
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
                color: '#1a1625',
                margin: '0 0 8px',
              }}
            >
              {t('apply.applicationReceived', 'Bewerbig erhalte!')}
            </h2>
            <p
              style={{
                fontSize: 'var(--mantine-font-size-sm)',
                color: '#5e5873',
                margin: '0 0 6px',
                lineHeight: 1.6,
              }}
            >
              {t('apply.thanksMsg', 'Danke, ')}{' '}
              <strong>
                {firstName} {lastName}
              </strong>
              . Mir überprüfed di Bewerbig ond melded us bi{' '}
              <strong>{email}</strong>.
            </p>
            <p
              style={{
                fontSize: 'var(--mantine-font-size-sm)',
                color: '#8c86a0',
                margin: '0 0 28px',
              }}
            >
              {t(
                'apply.usuallyTakesTime',
                'Das daueret normalerwis 1–3 Werchtäg.',
              )}
            </p>
            <Button
              variant="subtle"
              style={{ gap: 8 }}
              onClick={() => navigate('/login')}
            >
              <IconArrowLeft size={16} />{' '}
              {t('common.backToLogin', 'Zrugg zue Aamäldig')}
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
