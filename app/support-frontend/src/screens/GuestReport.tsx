import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Alert, Anchor, Box, Button, Paper, SegmentedControl, Stack, Text, TextInput, Textarea } from '@mantine/core'
import { IconCircleCheck } from '@tabler/icons-react'
import { currentDeviceInfo } from '@hubra/ui'
import { useAuth } from '@/auth'
import { useLang } from '@/lang'
import { sendGuestCase, type GuestReason } from '@/api/support'
import { pathOf } from '@/lib/labels'

/**
 * /melden and /kontakt without signing in: someone got a mail meant for
 * another person, wants no more mails, or has another problem and no
 * account (or can't sign in). They leave an address; the answer comes by
 * mail. Mail footers link here with ?mail=<which mail>.
 */
/** name@host.tld, without a regex (no backtracking on long input). */
function looksLikeEmail(value: string): boolean {
  const parts = value.split('@')
  if (parts.length !== 2 || /\s/.test(value)) return false
  const [local, domain] = parts
  const dot = domain.lastIndexOf('.')
  return local.length > 0 && dot > 0 && dot < domain.length - 1
}

export function GuestReportForm({ kind }: { kind: 'bug' | 'question' }) {
  const { tr } = useLang()
  const { signInUrl } = useAuth()
  const [params] = useSearchParams()
  const mail = params.get('mail') ?? ''
  const [reason, setReason] = useState<GuestReason>(mail ? 'wrong_recipient' : 'other')
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [website, setWebsite] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [sending, setSending] = useState(false)
  const [failed, setFailed] = useState('')
  const [sent, setSent] = useState(false)

  const defaultTitle: Record<GuestReason, string> = {
    wrong_recipient: tr('Mail an die falsche Person', 'Mail sent to the wrong person'),
    unwanted_mail: tr('Ich möchte keine Mails mehr', 'I want no more mails'),
    other: '',
  }

  const submit = async () => {
    const next: Record<string, string> = {}
    if (!looksLikeEmail(email.trim()))
      next.email = tr('Bitte gib deine Mail-Adresse ein, damit wir antworten können.', 'Please enter your email address so we can answer.')
    if (!description.trim()) next.description = tr('Bitte beschreibe kurz, was los ist.', "Please describe briefly what's going on.")
    if (reason === 'other' && !title.trim()) next.title = tr('Bitte gib einen kurzen Titel ein.', 'Please enter a short title.')
    setErrors(next)
    if (Object.keys(next).length) return
    setSending(true)
    setFailed('')
    try {
      await sendGuestCase({
        kind,
        email: email.trim(),
        name: name.trim() || undefined,
        reason,
        title: title.trim() || defaultTitle[reason],
        description: description.trim(),
        mail: mail || undefined,
        page: pathOf(params.get('where') ?? params.get('page') ?? ''),
        fingerprint: kind === 'bug' ? currentDeviceInfo() : undefined,
        website: website || undefined,
      })
      setSent(true)
    } catch (err) {
      setFailed((err as Error).message || tr('Senden fehlgeschlagen.', 'Sending failed.'))
    } finally {
      setSending(false)
    }
  }

  if (sent)
    return (
      <Alert color="green" icon={<IconCircleCheck size={20} />} title={tr('Danke, ist angekommen', 'Thank you, we got it')} data-testid="guest-sent">
        {tr(
          'Das Hubra-Team schaut es sich an und antwortet dir per Mail. Hat dich eine Mail für jemand anderen erreicht, lösche sie bitte.',
          'The Hubra team looks into it and answers you by mail. If a mail for someone else reached you, please delete it.',
        )}
      </Alert>
    )

  return (
    <Paper withBorder radius="lg" p={{ base: 'md', sm: 'xl' }} data-testid="guest-report">
      <form
        onSubmit={(e) => {
          e.preventDefault()
          void submit()
        }}
      >
        <Stack gap="md">
          <Text size="sm" c="dimmed">
            {tr('Kein Konto nötig.', 'No account needed.')}{' '}
            <Anchor href={signInUrl()} size="sm">
              {tr('Mit Konto anmelden', 'Sign in with an account')}
            </Anchor>{' '}
            {tr('und du siehst Antworten auch unter «Meine Meldungen».', 'and you also see answers under "My reports".')}
          </Text>
          <Stack gap={6}>
            <Text size="sm" fw={500}>
              {tr('Worum geht es?', 'What is it about?')}
            </Text>
            <SegmentedControl
              fullWidth
              orientation={window.innerWidth < 560 ? 'vertical' : 'horizontal'}
              value={reason}
              onChange={(v) => setReason(v as GuestReason)}
              data={[
                { value: 'wrong_recipient', label: tr('Mail nicht für mich', 'Mail not for me') },
                { value: 'unwanted_mail', label: tr('Keine Mails mehr', 'No more mails') },
                { value: 'other', label: tr('Etwas anderes', 'Something else') },
              ]}
            />
          </Stack>
          {mail && (
            <Text size="sm" c="dimmed">
              {tr('Gemeldet wird die Mail', 'Reporting the mail')} <code>{mail}</code>
            </Text>
          )}
          <TextInput
            label={tr('Deine Mail-Adresse', 'Your email address')}
            description={tr('Die Adresse, an die die Mail ging. Nur dafür, dir zu antworten.', 'The address the mail went to. Only used to answer you.')}
            type="email"
            value={email}
            onChange={(e) => setEmail(e.currentTarget.value)}
            error={errors.email}
            autoComplete="email"
            maxLength={254}
            required
          />
          <TextInput
            label={tr('Dein Name', 'Your name')}
            value={name}
            onChange={(e) => setName(e.currentTarget.value)}
            placeholder={tr('Optional', 'Optional')}
            autoComplete="name"
            maxLength={120}
          />
          {reason === 'other' && (
            <TextInput
              label={tr('Titel', 'Title')}
              value={title}
              onChange={(e) => setTitle(e.currentTarget.value)}
              error={errors.title}
              maxLength={200}
              required
            />
          )}
          <Textarea
            label={tr('Was ist los?', "What's going on?")}
            placeholder={
              reason === 'wrong_recipient'
                ? tr('Zum Beispiel: von welchem Verein, an wen sie eigentlich ging.', 'For example: from which club, who it was really meant for.')
                : reason === 'unwanted_mail'
                  ? tr('Von welchem Verein kommen die Mails?', 'Which club do the mails come from?')
                  : undefined
            }
            value={description}
            onChange={(e) => setDescription(e.currentTarget.value)}
            error={errors.description}
            autosize
            minRows={4}
            maxRows={12}
            maxLength={5000}
            required
          />
          {/* Honeypot: hidden from people and screen readers, bots fill it. */}
          <Box style={{ position: 'absolute', left: -10000, width: 1, height: 1, overflow: 'hidden' }} aria-hidden>
            <label>
              Website
              <input tabIndex={-1} autoComplete="off" value={website} onChange={(e) => setWebsite(e.currentTarget.value)} />
            </label>
          </Box>
          {failed && (
            <Alert color="red" title={tr('Senden fehlgeschlagen', 'Sending failed')}>
              {failed}
            </Alert>
          )}
          <Button type="submit" loading={sending} style={{ alignSelf: 'flex-end' }}>
            {tr('Senden', 'Send')}
          </Button>
        </Stack>
      </form>
    </Paper>
  )
}
