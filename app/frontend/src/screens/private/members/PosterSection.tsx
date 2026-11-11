import { useState } from 'react'
import { createPortal } from 'react-dom'
import { useQuery } from '@tanstack/react-query'
import { useDebouncedValue } from '@mantine/hooks'
import { Button, Group, Paper, SegmentedControl, SimpleGrid, Stack, Table, Text, TextInput } from '@mantine/core'
import { IconPrinter, IconQrcode } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useAuth } from '@/context/AppContext'
import { Modal } from '@/components/ui'
import { qk } from '@/data/keys'
import { getPoster, listSignupSources, type PosterKind, type PosterLink } from '@/api/applications'

type Size = 'a4' | 'a6'

/** Members › Applications: printable join and trial posters with a QR code
 * that carries a source tag, and how many came from each tag. */
export function PosterSection() {
  const { t } = useT()
  const { hasPermission } = useAuth()
  const canRead = hasPermission('applications.applications.read')
  const [open, setOpen] = useState(false)
  const { data: sources = [] } = useQuery({
    queryKey: qk.signupSources,
    queryFn: listSignupSources,
    enabled: canRead,
  })
  if (!canRead) return null

  return (
    <Paper withBorder mt="lg" p="lg">
      <Group justify="space-between" align="flex-start" wrap="wrap" gap="sm">
        <div style={{ flex: 1, minWidth: 240 }}>
          <Text fw={700} fz="md">
            {t('members.poster.title', 'Plakate und Flyer')}
          </Text>
          <Text size="sm" c="dimmed">
            {t(
              'members.poster.intro',
              'Ein Plakat mit QR-Code zur Beitritts- oder Probetrainings-Seite. Gib jedem Aushang einen eigenen Namen, dann siehst du hier, welcher Anfragen bringt.',
            )}
          </Text>
        </div>
        <Button leftSection={<IconQrcode size={16} />} onClick={() => setOpen(true)} data-testid="open-poster">
          {t('members.poster.create', 'Plakat erstellen')}
        </Button>
      </Group>
      {sources.length > 0 && (
        <Table mt="md" data-testid="poster-sources">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>{t('members.poster.source', 'Plakat')}</Table.Th>
              <Table.Th ta="right">{t('members.poster.joins', 'Beitrittsanfragen')}</Table.Th>
              <Table.Th ta="right">{t('members.poster.trials', 'Probetrainings')}</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {sources.map((row) => (
              <Table.Tr key={row.source}>
                <Table.Td>{row.source}</Table.Td>
                <Table.Td ta="right" className="num">
                  {row.join}
                </Table.Td>
                <Table.Td ta="right" className="num">
                  {row.trial}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
      <PosterModal open={open} onClose={() => setOpen(false)} />
    </Paper>
  )
}

function PosterModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useT()
  const [kind, setKind] = useState<PosterKind>('join')
  const [size, setSize] = useState<Size>('a4')
  const [source, setSource] = useState('plakat-1')
  const [headline, setHeadline] = useState<string | null>(null)
  const [tag] = useDebouncedValue(source, 400)
  const { data } = useQuery({
    queryKey: qk.poster(kind, tag),
    queryFn: () => getPoster(kind, tag),
    enabled: open,
  })
  const defaultHeadline =
    kind === 'join'
      ? t('members.poster.headlineJoin', 'Werde Mitglied!')
      : t('members.poster.headlineTrial', 'Komm ins Probetraining!')
  const shown = headline ?? defaultHeadline
  const qrAlt = t('members.poster.qrAlt', 'QR-Code zur Seite des Vereins')
  const call =
    kind === 'join'
      ? t('members.poster.callJoin', 'QR-Code scannen und Beitritt anfragen')
      : t('members.poster.callTrial', 'QR-Code scannen und gratis Probetraining buchen')

  return (
    <Modal
      open={open}
      onClose={onClose}
      wide
      title={t('members.poster.create', 'Plakat erstellen')}
      footer={
        <>
          <Button variant="default" onClick={onClose}>
            {t('common.close', 'Schliessen')}
          </Button>
          <Button leftSection={<IconPrinter size={16} />} onClick={() => window.print()} disabled={!data}>
            {t('members.poster.print', 'Drucken')}
          </Button>
        </>
      }
    >
      {/* The page size for printing; everything but the poster is hidden (index.css). */}
      <style>{`@page { size: ${size === 'a4' ? 'A4' : 'A6'} portrait; margin: 0; }`}</style>
      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="lg">
        <Stack gap="sm">
          <SegmentedControl
            value={kind}
            onChange={(v) => {
              setKind(v as PosterKind)
              setHeadline(null)
            }}
            data={[
              { value: 'join', label: t('members.poster.kindJoin', 'Mitglied werden') },
              { value: 'trial', label: t('members.poster.kindTrial', 'Probetraining') },
            ]}
          />
          <SegmentedControl
            value={size}
            onChange={(v) => setSize(v as Size)}
            data={[
              { value: 'a4', label: t('members.poster.a4', 'A4 Plakat') },
              { value: 'a6', label: t('members.poster.a6', 'A6 Flyer') },
            ]}
          />
          <TextInput
            label={t('members.poster.headline', 'Überschrift')}
            value={shown}
            onChange={(e) => setHeadline(e.currentTarget.value)}
            maxLength={60}
          />
          <TextInput
            label={t('members.poster.tag', 'Name des Aushangs')}
            description={t(
              'members.poster.tagHint',
              'Zum Beispiel «bahnhof» oder «flyer-schule». Wer über diesen Code kommt, wird so gezählt.',
            )}
            value={source}
            onChange={(e) => setSource(e.currentTarget.value)}
            maxLength={40}
            data-testid="poster-tag"
          />
          {data && (
            <Text size="xs" c="dimmed" style={{ wordBreak: 'break-all' }}>
              {data.url}
            </Text>
          )}
        </Stack>
        <div
          data-testid="poster-preview"
          style={{
            aspectRatio: size === 'a4' ? '210 / 297' : '105 / 148',
            width: '100%',
            maxWidth: 380,
            margin: '0 auto',
            border: '1px solid var(--hb-border)',
          }}
        >
          <PosterArt data={data} headline={shown} call={call} qrAlt={qrAlt} />
        </div>
      </SimpleGrid>
      {/* The copy that prints: straight in <body>, so no dialog clips or
          moves it; hidden on screen (index.css). */}
      {open &&
        createPortal(
          <div className="hb-poster-print">
            <PosterArt data={data} headline={shown} call={call} qrAlt={qrAlt} />
          </div>,
          document.body,
        )}
    </Modal>
  )
}

/** The poster itself; it fills its box and scales with its width. */
function PosterArt({
  data,
  headline,
  call,
  qrAlt,
}: {
  data: PosterLink | undefined
  headline: string
  call: string
  qrAlt: string
}) {
  return (
    <div style={{ containerType: 'inline-size', width: '100%', height: '100%', background: '#fff' }}>
      <div
        style={{
          height: '100%',
          color: '#111',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'space-between',
          textAlign: 'center',
          padding: '8cqw 7cqw',
          boxSizing: 'border-box',
          borderTop: '3cqw solid var(--mantine-primary-color-filled)',
        }}
      >
        <div style={{ fontSize: '5.5cqw', fontWeight: 600, letterSpacing: '0.04em' }}>{data?.club.name}</div>
        <div style={{ fontSize: '10cqw', fontWeight: 800, lineHeight: 1.1 }}>{headline}</div>
        {data && (
          <img
            src={`data:image/svg+xml;utf8,${encodeURIComponent(data.qrSvg)}`}
            alt={qrAlt}
            style={{ width: '58cqw', height: '58cqw' }}
          />
        )}
        <div style={{ fontSize: '4.4cqw', fontWeight: 600 }}>{call}</div>
        <div style={{ fontSize: '2.8cqw', color: '#555', wordBreak: 'break-all' }}>{data?.url}</div>
      </div>
    </div>
  )
}
