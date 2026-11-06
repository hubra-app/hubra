import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Alert,
  Anchor,
  Button,
  Checkbox,
  Group,
  List,
  Paper,
  PasswordInput,
  Stack,
  Text,
  ThemeIcon,
} from '@mantine/core'
import { IconAlertTriangle, IconDownload, IconTrash } from '@tabler/icons-react'
import { Modal, useLegalLinks } from '@hubra/ui'
import { Page } from '@/components/Layout'
import { SignInNeeded } from '@/components/SignInNeeded'
import { useAuth } from '@/auth'
import { APP_URL } from '@/urls'
import { useLang } from '@/lang'
import { deleteAccount, deletionCheck, downloadExport } from '@/api/support'

/**
 * /datenschutz: the person's own data requests. Download everything the
 * account holds, and delete the account once it is in no club any more.
 * What a club keeps about its members is the club's: ask the club.
 */
export function PrivacyScreen() {
  const { tr } = useLang()
  const { status } = useAuth()
  const privacyUrl = useLegalLinks()?.privacyUrl ?? 'https://hubra.club/datenschutz/'
  return (
    <Page
      narrow
      title={tr('Meine Daten', 'My data')}
      intro={tr(
        'Lade herunter, was dein Hubra-Konto über dich speichert, oder lösche dein Konto. Was ein Verein über seine Mitglieder aufbewahrt, gehört dem Verein: dafür wendest du dich an den Verein.',
        'Download what your Hubra account stores about you, or delete your account. What a club keeps about its members belongs to the club: ask the club for that.',
      )}
    >
      {status === 'authed' ? (
        <Stack gap="lg">
          <ExportCard />
          <DeleteCard />
          <Text size="sm" c="dimmed">
            {tr('Mehr dazu in der', 'More in the')}{' '}
            <Anchor href={privacyUrl} size="sm">
              {tr('Datenschutzerklärung', 'privacy policy')}
            </Anchor>
            . {tr('Fragen?', 'Questions?')}{' '}
            <Anchor component={Link} to="/kontakt?area=account" size="sm">
              {tr('Schreib uns', 'Write to us')}
            </Anchor>
            .
          </Text>
        </Stack>
      ) : (
        <SignInNeeded
          why={tr(
            'Nur du selbst kannst deine Daten herunterladen oder dein Konto löschen.',
            'Only you can download your data or delete your account.',
          )}
        />
      )}
    </Page>
  )
}

function ExportCard() {
  const { tr } = useLang()
  const { notify } = useAuth()
  const [busy, setBusy] = useState(false)
  return (
    <Paper withBorder radius="lg" p="lg">
      <Group align="flex-start" wrap="nowrap" gap="md">
        <ThemeIcon size={40} radius="md" variant="light">
          <IconDownload size={20} />
        </ThemeIcon>
        <Stack gap={6} style={{ flex: 1 }}>
          <Text fw={700}>{tr('Daten herunterladen', 'Download your data')}</Text>
          <Text size="sm" c="dimmed">
            {tr(
              'Eine JSON-Datei mit deinem Profil, deinen Vereinen, Anmeldungen und Geräten, Passkeys, verknüpften Konten, API-Tokens und deinen Meldungen samt Antworten. Passwörter und Geheimnisse sind nicht dabei.',
              'A JSON file with your profile, your clubs, sign-ins and devices, passkeys, linked accounts, API tokens and your reports with their answers. Passwords and secrets are not included.',
            )}
          </Text>
          <Group mt={4}>
            <Button
              variant="light"
              loading={busy}
              leftSection={<IconDownload size={16} />}
              onClick={async () => {
                setBusy(true)
                try {
                  await downloadExport()
                } catch (err) {
                  notify('error', tr('Herunterladen fehlgeschlagen', 'Download failed'), (err as Error).message)
                } finally {
                  setBusy(false)
                }
              }}
            >
              {tr('Herunterladen', 'Download')}
            </Button>
          </Group>
        </Stack>
      </Group>
    </Paper>
  )
}

function DeleteCard() {
  const { tr } = useLang()
  const { notify, signOut } = useAuth()
  const check = useQuery({ queryKey: ['deletion-check'], queryFn: deletionCheck })
  const [open, setOpen] = useState(false)
  const [password, setPassword] = useState('')
  const [sure, setSure] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [deleted, setDeleted] = useState(false)

  if (deleted)
    return (
      <Alert color="green" variant="light" title={tr('Konto gelöscht', 'Account deleted')}>
        {tr(
          'Dein Konto ist gelöscht und du bist abgemeldet. Eine Bestätigung ist an deine bisherige Adresse unterwegs.',
          'Your account is deleted and you are signed out. A confirmation is on its way to your old address.',
        )}
      </Alert>
    )

  const blockers = check.data?.blockers ?? []
  const submit = async () => {
    setError(null)
    setBusy(true)
    try {
      await deleteAccount(password)
      setOpen(false)
      setDeleted(true)
      signOut()
    } catch (err) {
      const code = (err as { code?: string }).code
      setError(
        code === 'INVALID_PASSWORD'
          ? tr('Das Passwort stimmt nicht.', 'The password is not correct.')
          : (err as Error).message,
      )
      if (code !== 'INVALID_PASSWORD') notify('error', tr('Löschen fehlgeschlagen', 'Deleting failed'), (err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Paper withBorder radius="lg" p="lg">
      <Group align="flex-start" wrap="nowrap" gap="md">
        <ThemeIcon size={40} radius="md" variant="light" color="red">
          <IconTrash size={20} />
        </ThemeIcon>
        <Stack gap={6} style={{ flex: 1 }}>
          <Text fw={700}>{tr('Konto löschen', 'Delete your account')}</Text>
          <Text size="sm" c="dimmed">
            {tr(
              'Name, Adresse, Telefon, Bild, Anmeldungen, Geräte, Passkeys, Zwei-Faktor, verknüpfte Konten und API-Tokens werden gelöscht. Deine Meldungen bleiben ohne deinen Namen erhalten. Das lässt sich nicht rückgängig machen.',
              'Name, address, phone, picture, sign-ins, devices, passkeys, two-factor, linked accounts and API tokens are deleted. Your reports stay, without your name. This cannot be undone.',
            )}
          </Text>
          {blockers.length > 0 && (
            <Alert color="orange" variant="light" icon={<IconAlertTriangle size={18} />} mt={4}>
              <Text size="sm" fw={600} mb={4}>
                {tr('Zuerst noch:', 'First:')}
              </Text>
              <List size="sm" spacing={2}>
                {blockers.map((b) => (
                  <List.Item key={`${b.kind}-${b.slug ?? ''}`}>
                    {b.kind === 'platform' ? (
                      tr(
                        'Du hast Rechte auf der Hubra-Plattform. Lass sie von einem anderen Plattform-Admin entfernen.',
                        'You have rights on the Hubra platform. Ask another platform admin to remove them.',
                      )
                    ) : (
                      <>
                        {b.kind === 'club_owner'
                          ? tr(`${b.name}: gib die Inhaberschaft ab und verlasse den Verein.`, `${b.name}: hand over ownership and leave the club.`)
                          : tr(`${b.name}: verlasse den Verein.`, `${b.name}: leave the club.`)}{' '}
                        {b.slug && (
                          <Anchor
                            href={`${APP_URL}/${encodeURIComponent(b.slug)}/app/account/settings/membership`}
                            size="sm"
                          >
                            {tr('Öffnen', 'Open')}
                          </Anchor>
                        )}
                      </>
                    )}
                  </List.Item>
                ))}
              </List>
            </Alert>
          )}
          <Group mt={4}>
            <Button
              color="red"
              variant="light"
              leftSection={<IconTrash size={16} />}
              disabled={!check.data?.canDelete}
              loading={check.isLoading}
              onClick={() => {
                setPassword('')
                setSure(false)
                setError(null)
                setOpen(true)
              }}
            >
              {tr('Konto löschen …', 'Delete account …')}
            </Button>
          </Group>
        </Stack>
      </Group>
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={tr('Konto endgültig löschen', 'Delete account for good')}
        onSubmit={(e) => {
          e?.preventDefault()
          void submit()
        }}
        footer={
          <>
            <Button variant="default" onClick={() => setOpen(false)}>
              {tr('Abbrechen', 'Cancel')}
            </Button>
            <Button type="submit" color="red" loading={busy} disabled={!sure || !password}>
              {tr('Endgültig löschen', 'Delete for good')}
            </Button>
          </>
        }
      >
        <Text size="sm">
          {tr(
            'Lade vorher deine Daten herunter, wenn du sie behalten willst. Danach kannst du dich nicht mehr anmelden.',
            'Download your data first if you want to keep it. Afterwards you can no longer sign in.',
          )}
        </Text>
        <PasswordInput
          label={tr('Aktuelles Passwort', 'Current password')}
          value={password}
          onChange={(e) => setPassword(e.currentTarget.value)}
          error={error}
          autoComplete="current-password"
          data-autofocus
        />
        <Checkbox
          checked={sure}
          onChange={(e) => setSure(e.currentTarget.checked)}
          label={tr('Ja, ich will mein Konto löschen.', 'Yes, I want to delete my account.')}
        />
      </Modal>
    </Paper>
  )
}
