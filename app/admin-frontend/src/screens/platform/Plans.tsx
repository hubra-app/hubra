import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ActionIcon,
  Anchor,
  Badge,
  Button,
  Code,
  Group,
  Modal,
  NumberInput,
  Paper,
  Select,
  SimpleGrid,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  Textarea,
  Title,
} from '@mantine/core'
import {
  IconArrowDown,
  IconArrowUp,
  IconPencil,
  IconPlus,
  IconTrash,
  IconWorld,
} from '@tabler/icons-react'
import { useAdmin } from '@/context/AdminContext'
import { tr } from '@/lang'
import { priceUnitOptions, priceUnitSuffix } from '@/labels'
import {
  createPlan,
  deletePlan,
  getPlans,
  setAddon,
  updatePlan,
  type Addon,
  type Plan,
  type PlanFeature,
  type PlanInput,
  type PlanModuleInput,
  type PriceUnit,
} from '@/api/platform'
import { BASE } from '@hubra/api-client'

const chf = (v: string | null) =>
  v == null
    ? tr('auf Anfrage', 'on request')
    : `CHF ${Number(v).toLocaleString('de-CH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

const limit = (n: number | null, unit = '') =>
  n == null ? tr('unbegrenzt', 'unlimited') : `${n.toLocaleString('de-CH')}${unit}`

const errorText = (err: unknown) => (err instanceof Error ? err.message : undefined)

/**
 * Plans with their prices, features and limits, and the add-on list prices
 * (Einstellungen › Tarife & Preise). Public plans and add-ons are what the
 * website reads from /api/v1/global/public/pricing.
 */
export function PlatformPlans() {
  const { notify } = useAdmin()
  const queryClient = useQueryClient()
  const { data } = useQuery({ queryKey: ['platform-plans'], queryFn: getPlans })
  const [editing, setEditing] = useState<Plan | 'new' | null>(null)
  const [addon, setAddonEditing] = useState<Addon | null>(null)
  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ['platform-plans'] })
    await queryClient.invalidateQueries({ queryKey: ['plan-choices'] })
  }
  const run = async (fn: () => Promise<unknown>, ok: string) => {
    try {
      await fn()
      notify('success', ok)
      await refresh()
    } catch (err) {
      notify('error', tr('Hat nicht geklappt', 'That did not work'), errorText(err))
    }
  }

  if (!data)
    return (
      <Text size="sm" c="dimmed">
        {tr('Wird geladen …', 'Loading…')}
      </Text>
    )

  const plans = data.plans
  const planName = (key: string) => {
    const p = plans.find((x) => x.key === key)
    return p ? tr(p.name_de, p.name_en) : key
  }
  const move = (i: number, dir: -1 | 1) => {
    const a = plans[i]
    const b = plans[i + dir]
    if (!a || !b) return
    void run(
      async () => {
        await updatePlan(a.key, { sort: b.sort })
        await updatePlan(b.key, { sort: a.sort === b.sort ? a.sort + dir : a.sort })
      },
      tr('Reihenfolge gespeichert', 'Order saved'),
    )
  }
  const apiRoot = new URL(BASE, window.location.origin).href.replace(/\/$/, '')
  const publicUrl = `${apiRoot}/global/public/pricing`

  return (
    <Stack gap={20} maw={960}>
      <Paper withBorder p="lg">
        <Group justify="space-between" mb={4}>
          <Title order={3}>{tr('Tarife', 'Plans')}</Title>
          <Button size="xs" leftSection={<IconPlus size={16} />} onClick={() => setEditing('new')}>
            {tr('Tarif erstellen', 'Create a plan')}
          </Button>
        </Group>
        <Text size="xs" c="dimmed" mb={12}>
          {tr(
            'Öffentliche Tarife zeigt die Website (über die öffentliche API). Nicht öffentliche Tarife kann ein Verein trotzdem bekommen, etwa für eine Sonderabmachung. Eigener Preis, Rabatt und Sponsoring stehen beim Verein. Es wird noch nichts verrechnet.',
            'The website shows public plans (through the public API). A club can still be put on a plan that is not public, for a special deal. Own price, discount and sponsor are set on the club. Nothing is charged yet.',
          )}
        </Text>
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="md">
          {plans.map((p, i) => (
            <Paper
              key={p.key}
              withBorder
              p="md"
              style={p.hidden ? { opacity: 0.6 } : undefined}
            >
              <Group justify="space-between" align="flex-start" wrap="nowrap" mb={4}>
                <Stack gap={2}>
                  <Text fw={700}>{tr(p.name_de, p.name_en)}</Text>
                  <Code fz="xs">{p.key}</Code>
                </Stack>
                <Group gap={2} wrap="nowrap">
                  <ActionIcon
                    variant="subtle"
                    aria-label={tr('Nach vorne', 'Move up')}
                    disabled={i === 0}
                    onClick={() => move(i, -1)}
                  >
                    <IconArrowUp size={16} />
                  </ActionIcon>
                  <ActionIcon
                    variant="subtle"
                    aria-label={tr('Nach hinten', 'Move down')}
                    disabled={i === plans.length - 1}
                    onClick={() => move(i, 1)}
                  >
                    <IconArrowDown size={16} />
                  </ActionIcon>
                  <ActionIcon
                    variant="subtle"
                    aria-label={tr('Bearbeiten', 'Edit')}
                    onClick={() => setEditing(p)}
                  >
                    <IconPencil size={16} />
                  </ActionIcon>
                </Group>
              </Group>
              <Group gap={6} mb={8}>
                {p.public ? (
                  <Badge
                    size="sm"
                    variant="light"
                    color="green"
                    leftSection={<IconWorld size={12} />}
                  >
                    {tr('Öffentlich', 'Public')}
                  </Badge>
                ) : (
                  <Badge size="sm" variant="light" color="gray">
                    {tr('Nicht öffentlich', 'Not public')}
                  </Badge>
                )}
                {p.highlighted && (
                  <Badge size="sm" variant="light" color="acc">
                    {tr('Hervorgehoben', 'Highlighted')}
                  </Badge>
                )}
                {p.hidden && (
                  <Badge size="sm" variant="outline" color="gray">
                    {tr('Ausgeblendet', 'Hidden')}
                  </Badge>
                )}
              </Group>
              <Text fw={700} size="lg">
                {chf(p.price_month_chf)}
                {p.price_month_chf != null && (
                  <Text span size="sm" c="dimmed" fw={400}>
                    {' '}
                    {tr('/ Monat', '/ month')}
                  </Text>
                )}
              </Text>
              {p.price_year_chf != null && (
                <Text size="sm" c="dimmed">
                  {chf(p.price_year_chf)} {tr('/ Jahr', '/ year')}
                </Text>
              )}
              <Text size="xs" c="dimmed" mt={6}>
                {tr(
                  `${limit(p.limits.members)} Mitglieder · ${limit(p.limits.mail_month)} Mails/Monat · ${limit(p.limits.storage_mb, ' MB')} Speicher`,
                  `${limit(p.limits.members)} members · ${limit(p.limits.mail_month)} mails/month · ${limit(p.limits.storage_mb, ' MB')} storage`,
                )}
              </Text>
              {p.features.length > 0 && (
                <Stack gap={2} mt={6}>
                  {p.features.map((f, j) => (
                    <Text key={j} size="xs">
                      ✓ {tr(f.de, f.en || f.de)}
                    </Text>
                  ))}
                </Stack>
              )}
              {p.modules.length > 0 && (
                <Stack gap={2} mt={8}>
                  <Text size="xs" fw={600}>
                    {tr('Enthaltene Module', 'Included modules')}
                  </Text>
                  {p.modules.map((m) => (
                    <Group key={m.code} gap={6} wrap="nowrap" justify="space-between">
                      <Text size="xs">{tr(m.name_de, m.name_en)}</Text>
                      <Text size="xs" c="dimmed" ta="right">
                        {m.price_chf == null
                          ? tr('inklusive', 'included')
                          : `${chf(m.price_chf)}${priceUnitSuffix(m.unit, tr)}`}
                      </Text>
                    </Group>
                  ))}
                </Stack>
              )}
              <Text size="xs" c="dimmed" mt={8}>
                {p.clubs === 1
                  ? tr('1 Verein', '1 club')
                  : tr(`${p.clubs} Vereine`, `${p.clubs} clubs`)}
              </Text>
            </Paper>
          ))}
        </SimpleGrid>
      </Paper>

      <Paper withBorder p="lg">
        <Title order={3} mb={4}>
          {tr('Zusatzmodule', 'Add-ons')}
        </Title>
        <Text size="xs" c="dimmed" mb={12}>
          {tr(
            'Listenpreis pro Monat für Module und Plugins zusätzlich zum Tarif: pauschal, pro Mitglied oder pro Lizenz. Beim Verein lässt sich jeder Preis anpassen. Welche Module ein Tarif enthält, steht beim Tarif. Öffentliche Zusatzmodule erscheinen in der öffentlichen Preisliste.',
            'List price per month for modules and plugins on top of the plan: flat, per member or per licence. Each price can be changed on a club. Which modules a plan includes is set on the plan. Public add-ons appear in the public price list.',
          )}
        </Text>
        <Table.ScrollContainer minWidth={560}>
          <Table verticalSpacing={6}>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{tr('Modul', 'Module')}</Table.Th>
                <Table.Th>{tr('Preis pro Monat', 'Price per month')}</Table.Th>
                <Table.Th>{tr('In Tarifen', 'In plans')}</Table.Th>
                <Table.Th>{tr('Öffentlich', 'Public')}</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.addons.map((a) => (
                <Table.Tr key={a.code}>
                  <Table.Td>
                    <Text size="sm" fw={600}>
                      {tr(a.label_de || a.name, a.label_en || a.name)}
                    </Text>
                    <Text size="xs" c="dimmed">
                      {a.plugin
                        ? tr(`Plugin ${a.plugin}`, `Plugin ${a.plugin}`)
                        : tr('Eingebaut', 'Built in')}{' '}
                      · {a.code}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm">
                      {a.price_month_chf == null
                        ? '–'
                        : `${chf(a.price_month_chf)}${priceUnitSuffix(a.price_unit, tr)}`}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    {a.included_in.length === 0 ? (
                      <Text size="sm" c="dimmed">
                        –
                      </Text>
                    ) : (
                      <Group gap={4}>
                        {a.included_in.map((k) => (
                          <Badge key={k} size="sm" variant="light" color="violet">
                            {planName(k)}
                          </Badge>
                        ))}
                      </Group>
                    )}
                  </Table.Td>
                  <Table.Td>
                    <Switch
                      aria-label={tr('Öffentlich', 'Public')}
                      checked={a.public}
                      onChange={(e) => {
                        const checked = e.currentTarget.checked
                        void run(
                          () => setAddon(a.code, { public: checked }),
                          checked
                            ? tr('Jetzt öffentlich', 'Now public')
                            : tr('Nicht mehr öffentlich', 'No longer public'),
                        )
                      }}
                    />
                  </Table.Td>
                  <Table.Td w={40}>
                    <ActionIcon
                      variant="subtle"
                      aria-label={tr('Bearbeiten', 'Edit')}
                      onClick={() => setAddonEditing(a)}
                    >
                      <IconPencil size={16} />
                    </ActionIcon>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      </Paper>

      <Paper withBorder p="lg">
        <Title order={3} mb={4}>
          {tr('Öffentliche API', 'Public API')}
        </Title>
        <Text size="xs" c="dimmed" mb={8}>
          {tr(
            'Ohne Anmeldung, von jeder Website lesbar (ohne Cookies), fünf Minuten zwischengespeichert. hubra.club liest die Preise und die Plugin-Liste von hier.',
            'No sign-in, readable from any website (without cookies), cached for five minutes. hubra.club reads the prices and the plugin list from here.',
          )}
        </Text>
        <Stack gap={4}>
          <Anchor href={publicUrl} target="_blank" size="sm">
            GET /api/v1/global/public/pricing
          </Anchor>
          <Anchor href={`${apiRoot}/global/public/plugins`} target="_blank" size="sm">
            GET /api/v1/global/public/plugins
          </Anchor>
        </Stack>
      </Paper>

      {editing && (
        <PlanModal
          plan={editing === 'new' ? null : editing}
          addons={data.addons}
          onClose={() => setEditing(null)}
          onSave={async (body) => {
            try {
              if (editing === 'new') await createPlan(body)
              else await updatePlan(editing.key, body)
              notify('success', tr('Tarif gespeichert', 'Plan saved'))
              setEditing(null)
              await refresh()
            } catch (err) {
              notify('error', tr('Speichern fehlgeschlagen', 'Could not save'), errorText(err))
            }
          }}
          onDelete={
            editing !== 'new' && editing.clubs === 0
              ? async () => {
                  try {
                    await deletePlan(editing.key)
                    notify('success', tr('Tarif gelöscht', 'Plan deleted'))
                    setEditing(null)
                    await refresh()
                  } catch (err) {
                    notify(
                      'error',
                      tr('Löschen fehlgeschlagen', 'Could not delete'),
                      errorText(err),
                    )
                  }
                }
              : undefined
          }
        />
      )}
      {addon && (
        <AddonModal
          addon={addon}
          onClose={() => setAddonEditing(null)}
          onSave={async (body) => {
            try {
              await setAddon(addon.code, body)
              notify('success', tr('Gespeichert', 'Saved'))
              setAddonEditing(null)
              await refresh()
            } catch (err) {
              notify('error', tr('Speichern fehlgeschlagen', 'Could not save'), errorText(err))
            }
          }}
        />
      )}
    </Stack>
  )
}

const money = (v: string | number) => (v === '' ? null : String(v))
const count = (v: string | number) => (v === '' ? null : Number(v))

function PlanModal({
  plan,
  addons,
  onClose,
  onSave,
  onDelete,
}: {
  plan: Plan | null
  addons: Addon[]
  onClose: () => void
  onSave: (body: PlanInput) => Promise<void>
  onDelete?: () => Promise<void>
}) {
  const [key, setKey] = useState('')
  const [v, setV] = useState(() => ({
    name_de: plan?.name_de ?? '',
    name_en: plan?.name_en ?? '',
    description_de: plan?.description_de ?? '',
    description_en: plan?.description_en ?? '',
    price_month_chf: plan?.price_month_chf ?? '',
    price_year_chf: plan?.price_year_chf ?? '',
    limit_members: plan?.limits.members ?? '',
    limit_mail_month: plan?.limits.mail_month ?? '',
    limit_storage_mb: plan?.limits.storage_mb ?? '',
    public: plan?.public ?? false,
    highlighted: plan?.highlighted ?? false,
    hidden: plan?.hidden ?? false,
  }))
  const [features, setFeatures] = useState<PlanFeature[]>(plan?.features ?? [])
  const [modules, setModules] = useState<PlanModuleInput[]>(
    () => plan?.modules.map(({ code, price_chf, unit }) => ({ code, price_chf, unit })) ?? [],
  )
  const [pick, setPick] = useState<string | null>(null)
  const addonName = (code: string) => {
    const a = addons.find((x) => x.code === code)
    const own = plan?.modules.find((m) => m.code === code)
    if (a) return tr(a.label_de || a.name, a.label_en || a.name)
    return own ? tr(own.name_de, own.name_en) : code
  }
  const setModule = (i: number, patch: Partial<PlanModuleInput>) =>
    setModules((ms) => ms.map((m, j) => (j === i ? { ...m, ...patch } : m)))
  const [saving, setSaving] = useState(false)
  const set = <K extends keyof typeof v>(k: K, value: (typeof v)[K]) =>
    setV((cur) => ({ ...cur, [k]: value }))
  const keyOk = plan != null || /^[a-z][a-z0-9-]{1,39}$/.test(key)

  return (
    <Modal
      opened
      onClose={onClose}
      size="xl"
      title={
        plan
          ? tr(`Tarif ${plan.name_de} bearbeiten`, `Edit plan ${plan.name_en}`)
          : tr('Tarif erstellen', 'Create a plan')
      }
    >
      <Stack gap="md">
        {!plan && (
          <TextInput
            label={tr('Schlüssel', 'Key')}
            description={tr(
              'Steht beim Verein als Tarif; nachher nicht mehr änderbar. Kleinbuchstaben, Ziffern, Bindestriche.',
              'Stored on the club as its plan; cannot be changed later. Lower-case letters, digits, dashes.',
            )}
            placeholder="verein-plus"
            value={key}
            error={
              key && !keyOk
                ? tr('2–40 Zeichen, mit einem Buchstaben vorne', '2–40 characters, a letter first')
                : undefined
            }
            onChange={(e) => setKey(e.currentTarget.value.trim())}
          />
        )}
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <TextInput
            label={tr('Name (Deutsch)', 'Name (German)')}
            required
            maxLength={80}
            value={v.name_de}
            onChange={(e) => set('name_de', e.currentTarget.value)}
          />
          <TextInput
            label={tr('Name (Englisch)', 'Name (English)')}
            maxLength={80}
            value={v.name_en}
            onChange={(e) => set('name_en', e.currentTarget.value)}
          />
          <Textarea
            label={tr('Beschreibung (Deutsch)', 'Description (German)')}
            autosize
            minRows={2}
            maxLength={1000}
            value={v.description_de}
            onChange={(e) => set('description_de', e.currentTarget.value)}
          />
          <Textarea
            label={tr('Beschreibung (Englisch)', 'Description (English)')}
            autosize
            minRows={2}
            maxLength={1000}
            value={v.description_en}
            onChange={(e) => set('description_en', e.currentTarget.value)}
          />
          <NumberInput
            label={tr('Preis pro Monat (CHF)', 'Price per month (CHF)')}
            description={tr('Leer: auf Anfrage', 'Empty: on request')}
            min={0}
            decimalScale={2}
            allowNegative={false}
            thousandSeparator="'"
            value={v.price_month_chf}
            onChange={(x) => set('price_month_chf', x === '' ? '' : String(x))}
          />
          <NumberInput
            label={tr('Preis pro Jahr (CHF)', 'Price per year (CHF)')}
            description={tr('Leer: kein Jahrespreis', 'Empty: no yearly price')}
            min={0}
            decimalScale={2}
            allowNegative={false}
            thousandSeparator="'"
            value={v.price_year_chf}
            onChange={(x) => set('price_year_chf', x === '' ? '' : String(x))}
          />
        </SimpleGrid>
        <Text size="sm" fw={600}>
          {tr('Limits (leer: unbegrenzt)', 'Limits (empty: unlimited)')}
        </Text>
        <SimpleGrid cols={{ base: 1, sm: 3 }}>
          <NumberInput
            label={tr('Mitglieder', 'Members')}
            min={0}
            allowDecimal={false}
            allowNegative={false}
            value={v.limit_members}
            onChange={(x) => set('limit_members', x === '' ? '' : Number(x))}
          />
          <NumberInput
            label={tr('Mails pro Monat', 'Mails per month')}
            min={0}
            allowDecimal={false}
            allowNegative={false}
            value={v.limit_mail_month}
            onChange={(x) => set('limit_mail_month', x === '' ? '' : Number(x))}
          />
          <NumberInput
            label={tr('Speicher (MB)', 'Storage (MB)')}
            min={0}
            allowDecimal={false}
            allowNegative={false}
            value={v.limit_storage_mb}
            onChange={(x) => set('limit_storage_mb', x === '' ? '' : Number(x))}
          />
        </SimpleGrid>
        <Stack gap={6}>
          <Text size="sm" fw={600}>
            {tr('Leistungen (für die Website)', 'Features (for the website)')}
          </Text>
          {features.map((f, i) => (
            <Group key={i} gap={8} wrap="nowrap">
              <TextInput
                style={{ flex: 1 }}
                aria-label={tr('Deutsch', 'German')}
                placeholder={tr('Deutsch', 'German')}
                maxLength={200}
                value={f.de}
                onChange={(e) => {
                  const value = e.currentTarget.value
                  setFeatures((fs) => fs.map((x, j) => (j === i ? { ...x, de: value } : x)))
                }}
              />
              <TextInput
                style={{ flex: 1 }}
                aria-label={tr('Englisch', 'English')}
                placeholder={tr('Englisch', 'English')}
                maxLength={200}
                value={f.en}
                onChange={(e) => {
                  const value = e.currentTarget.value
                  setFeatures((fs) => fs.map((x, j) => (j === i ? { ...x, en: value } : x)))
                }}
              />
              <ActionIcon
                variant="subtle"
                color="red"
                aria-label={tr('Entfernen', 'Remove')}
                onClick={() => setFeatures((fs) => fs.filter((_, j) => j !== i))}
              >
                <IconTrash size={16} />
              </ActionIcon>
            </Group>
          ))}
          <Group>
            <Button
              size="xs"
              variant="light"
              leftSection={<IconPlus size={14} />}
              onClick={() => setFeatures((fs) => [...fs, { de: '', en: '' }])}
            >
              {tr('Leistung hinzufügen', 'Add a feature')}
            </Button>
          </Group>
        </Stack>
        <Stack gap={6}>
          <Text size="sm" fw={600}>
            {tr('Enthaltene Module', 'Included modules')}
          </Text>
          <Text size="xs" c="dimmed">
            {tr(
              'Module und Plugins, die zum Tarif gehören. Ohne Preis sind sie inklusive; mit Preis kosten sie im Tarif so viel, pauschal, pro Mitglied oder pro Lizenz (pro Monat).',
              'Modules and plugins that come with the plan. Without a price they are included; with a price they cost that much in this plan, flat, per member or per licence (per month).',
            )}
          </Text>
          {modules.map((m, i) => (
            <Group key={m.code} gap={8} wrap="nowrap" align="flex-end">
              <Group gap={8} wrap="wrap" align="flex-end" style={{ flex: 1 }}>
                <Text size="sm" fw={600} style={{ flex: '1 1 160px' }}>
                  {addonName(m.code)}
                </Text>
                <NumberInput
                  w={{ base: 120, sm: 150 }}
                  aria-label={tr('Preis (CHF)', 'Price (CHF)')}
                  placeholder={tr('inklusive', 'included')}
                  min={0}
                  decimalScale={2}
                  allowNegative={false}
                  prefix="CHF "
                  value={m.price_chf ?? ''}
                  onChange={(x) => setModule(i, { price_chf: x === '' ? null : String(x) })}
                />
                <Select
                  w={{ base: 130, sm: 150 }}
                  aria-label={tr('Preis gilt', 'Price applies')}
                  allowDeselect={false}
                  disabled={m.price_chf == null}
                  data={priceUnitOptions(tr)}
                  value={m.unit}
                  onChange={(x) => x && setModule(i, { unit: x as PriceUnit })}
                />
              </Group>
              <ActionIcon
                variant="subtle"
                color="red"
                mb={6}
                aria-label={tr('Entfernen', 'Remove')}
                onClick={() => setModules((ms) => ms.filter((_, j) => j !== i))}
              >
                <IconTrash size={16} />
              </ActionIcon>
            </Group>
          ))}
          <Group gap={8} align="flex-end">
            <Select
              style={{ flex: 1 }}
              aria-label={tr('Modul oder Plugin', 'Module or plugin')}
              placeholder={tr('Modul oder Plugin wählen', 'Choose a module or plugin')}
              searchable
              data={addons
                .filter((a) => !modules.some((m) => m.code === a.code))
                .map((a) => ({
                  value: a.code,
                  label: a.plugin
                    ? `${tr(a.label_de || a.name, a.label_en || a.name)} (Plugin)`
                    : tr(a.label_de || a.name, a.label_en || a.name),
                }))}
              value={pick}
              onChange={setPick}
            />
            <Button
              size="sm"
              variant="light"
              leftSection={<IconPlus size={14} />}
              disabled={!pick}
              onClick={() => {
                if (!pick) return
                setModules((ms) => [...ms, { code: pick, price_chf: null, unit: 'flat' }])
                setPick(null)
              }}
            >
              {tr('Modul hinzufügen', 'Add a module')}
            </Button>
          </Group>
        </Stack>
        <SimpleGrid cols={{ base: 1, sm: 3 }}>
          <Switch
            label={tr('Öffentlich', 'Public')}
            description={tr(
              'Auf der Website und in der öffentlichen API',
              'On the website and in the public API',
            )}
            checked={v.public}
            onChange={(e) => set('public', e.currentTarget.checked)}
          />
          <Switch
            label={tr('Hervorgehoben', 'Highlighted')}
            description={tr(
              'Die Website zeigt ihn als Empfehlung',
              'The website shows it as the recommended one',
            )}
            checked={v.highlighted}
            onChange={(e) => set('highlighted', e.currentTarget.checked)}
          />
          <Switch
            label={tr('Ausgeblendet', 'Hidden')}
            description={tr(
              'Kein neuer Verein bekommt ihn; bestehende behalten ihn',
              'No new club gets it; clubs on it keep it',
            )}
            checked={v.hidden}
            onChange={(e) => set('hidden', e.currentTarget.checked)}
          />
        </SimpleGrid>
        <Group justify="space-between">
          {onDelete ? (
            <Button
              variant="subtle"
              color="red"
              leftSection={<IconTrash size={16} />}
              onClick={() => void onDelete()}
            >
              {tr('Löschen', 'Delete')}
            </Button>
          ) : (
            <span />
          )}
          <Group>
            <Button variant="default" onClick={onClose}>
              {tr('Abbrechen', 'Cancel')}
            </Button>
            <Button
              loading={saving}
              disabled={!v.name_de.trim() || !keyOk}
              onClick={async () => {
                setSaving(true)
                try {
                  await onSave({
                    ...(plan ? {} : { key }),
                    name_de: v.name_de,
                    name_en: v.name_en,
                    description_de: v.description_de,
                    description_en: v.description_en,
                    price_month_chf: money(v.price_month_chf),
                    price_year_chf: money(v.price_year_chf),
                    limit_members: count(v.limit_members),
                    limit_mail_month: count(v.limit_mail_month),
                    limit_storage_mb: count(v.limit_storage_mb),
                    features: features.filter((f) => f.de.trim() || f.en.trim()),
                    modules: modules.map((m) =>
                      m.price_chf == null ? { ...m, unit: 'flat' as const } : m,
                    ),
                    public: v.public,
                    highlighted: v.highlighted,
                    hidden: v.hidden,
                  })
                } finally {
                  setSaving(false)
                }
              }}
            >
              {tr('Speichern', 'Save')}
            </Button>
          </Group>
        </Group>
      </Stack>
    </Modal>
  )
}

function AddonModal({
  addon,
  onClose,
  onSave,
}: {
  addon: Addon
  onClose: () => void
  onSave: (body: Partial<Addon>) => Promise<void>
}) {
  const [price, setPrice] = useState<string | number>(addon.price_month_chf ?? '')
  const [unit, setUnit] = useState<PriceUnit>(addon.price_unit ?? 'flat')
  const [v, setV] = useState({
    label_de: addon.label_de,
    label_en: addon.label_en,
    note_de: addon.note_de,
    note_en: addon.note_en,
    public: addon.public,
  })
  const set = <K extends keyof typeof v>(k: K, value: (typeof v)[K]) =>
    setV((cur) => ({ ...cur, [k]: value }))
  return (
    <Modal opened onClose={onClose} size="lg" title={addon.name}>
      <Stack gap="md">
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <NumberInput
            label={tr('Listenpreis pro Monat (CHF)', 'List price per month (CHF)')}
            description={tr('Leer: kein Preis', 'Empty: no price')}
            min={0}
            decimalScale={2}
            allowNegative={false}
            value={price}
            onChange={setPrice}
          />
          <Select
            label={tr('Preis gilt', 'Price applies')}
            description={tr(
              'Pro Mitglied: Mitglieder, die nicht archiviert sind',
              'Per member: members that are not archived',
            )}
            allowDeselect={false}
            data={priceUnitOptions(tr)}
            value={unit}
            onChange={(x) => x && setUnit(x as PriceUnit)}
          />
        </SimpleGrid>
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <TextInput
            label={tr('Name auf der Website (Deutsch)', 'Name on the website (German)')}
            placeholder={addon.name}
            maxLength={120}
            value={v.label_de}
            onChange={(e) => set('label_de', e.currentTarget.value)}
          />
          <TextInput
            label={tr('Name auf der Website (Englisch)', 'Name on the website (English)')}
            placeholder={addon.name}
            maxLength={120}
            value={v.label_en}
            onChange={(e) => set('label_en', e.currentTarget.value)}
          />
          <Textarea
            label={tr('Text (Deutsch)', 'Text (German)')}
            placeholder={addon.description}
            autosize
            minRows={2}
            maxLength={1000}
            value={v.note_de}
            onChange={(e) => set('note_de', e.currentTarget.value)}
          />
          <Textarea
            label={tr('Text (Englisch)', 'Text (English)')}
            placeholder={addon.description}
            autosize
            minRows={2}
            maxLength={1000}
            value={v.note_en}
            onChange={(e) => set('note_en', e.currentTarget.value)}
          />
        </SimpleGrid>
        <Switch
          label={tr('Öffentlich', 'Public')}
          checked={v.public}
          onChange={(e) => set('public', e.currentTarget.checked)}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            {tr('Abbrechen', 'Cancel')}
          </Button>
          <Button
            onClick={() =>
              void onSave({
                ...v,
                price_month_chf: price === '' ? null : String(price),
                price_unit: unit,
              })
            }
          >
            {tr('Speichern', 'Save')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}
