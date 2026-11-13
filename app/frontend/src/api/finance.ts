import { apiFetch, apiFetchRaw } from '@hubra/api-client';
import type {
  Invoice,
  TransactionCategory,
  ExternalParty,
} from "@/types";
import { fetchPages } from "@/api/pages";

// ── Transaction Categories ─────────────────────────────────────────────────
// The categories, the transactions and the rest of the books are the
// Finances plugin's (hubra-app/hubra-plugin-finances); the invoice form
// lists the categories while it is on.

interface BackendTxCategory {
  id: number;
  name: string;
  color: string | null;
  is_default: boolean;
}

function adaptTxCat(b: BackendTxCategory): TransactionCategory {
  return {
    id: String(b.id),
    name: b.name,
    color: b.color ?? "#7441e0",
    isDefault: b.is_default,
  };
}

export async function listTxCategories(): Promise<TransactionCategory[]> {
  const data = await apiFetch<BackendTxCategory[]>(
    "/app/finance/transaction-categories",
  );
  return data.map(adaptTxCat);
}

// ── External Parties ───────────────────────────────────────────────────────

interface BackendExternalParty {
  id: number;
  name: string;
  email: string | null;
  address_street: string | null;
  address_house_no: string | null;
  address_postal_code: string | null;
  address_city: string | null;
  address_country: string;
  notes: string | null;
}

function adaptExtParty(b: BackendExternalParty): ExternalParty {
  return {
    id: String(b.id),
    name: b.name,
    email: b.email,
    addressStreet: b.address_street,
    addressHouseNo: b.address_house_no,
    addressPostalCode: b.address_postal_code,
    addressCity: b.address_city,
    addressCountry: b.address_country,
    notes: b.notes,
  };
}

export async function listExternalParties(
  search?: string,
): Promise<ExternalParty[]> {
  const qs = search ? `?search=${encodeURIComponent(search)}` : "";
  const data = await apiFetch<BackendExternalParty[]>(
    `/app/finance/external-parties${qs}`,
  );
  return data.map(adaptExtParty);
}

export async function createExternalParty(input: {
  name: string;
  email?: string | null;
  addressStreet?: string | null;
  addressHouseNo?: string | null;
  addressPostalCode?: string | null;
  addressCity?: string | null;
  addressCountry?: string;
  notes?: string | null;
}): Promise<ExternalParty> {
  const body: Record<string, unknown> = {
    name: input.name,
    address_country: input.addressCountry ?? 'CH',
  };
  if (input.email !== undefined) body.email = input.email;
  if (input.addressStreet !== undefined) body.address_street = input.addressStreet;
  if (input.addressHouseNo !== undefined) body.address_house_no = input.addressHouseNo;
  if (input.addressPostalCode !== undefined) body.address_postal_code = input.addressPostalCode;
  if (input.addressCity !== undefined) body.address_city = input.addressCity;
  if (input.notes !== undefined) body.notes = input.notes;
  const b = await apiFetch<BackendExternalParty>(
    "/app/finance/external-parties",
    { method: "POST", body: JSON.stringify(body) },
  );
  return adaptExtParty(b);
}

export async function updateExternalParty(
  id: string,
  input: Partial<{
    name: string;
    email: string | null;
    addressStreet: string | null;
    addressHouseNo: string | null;
    addressPostalCode: string | null;
    addressCity: string | null;
    addressCountry: string;
    notes: string | null;
  }>,
): Promise<ExternalParty> {
  const body: Record<string, unknown> = {};
  if (input.name !== undefined) body.name = input.name;
  if (input.email !== undefined) body.email = input.email;
  if (input.addressStreet !== undefined) body.address_street = input.addressStreet;
  if (input.addressHouseNo !== undefined) body.address_house_no = input.addressHouseNo;
  if (input.addressPostalCode !== undefined) body.address_postal_code = input.addressPostalCode;
  if (input.addressCity !== undefined) body.address_city = input.addressCity;
  if (input.addressCountry !== undefined) body.address_country = input.addressCountry;
  if (input.notes !== undefined) body.notes = input.notes;
  const b = await apiFetch<BackendExternalParty>(
    `/app/finance/external-parties/${id}`,
    { method: "PATCH", body: JSON.stringify(body) },
  );
  return adaptExtParty(b);
}

export async function deleteExternalParty(id: string): Promise<void> {
  await apiFetch(`/app/finance/external-parties/${id}`, { method: "DELETE" });
}

// ── Invoices ───────────────────────────────────────────────────────────────

interface BackendInvoice {
  id: number;
  /** A collected invoice's open items (detail only). */
  items?: { id: number; day: string; text: string; amount: number }[];
  member_id: number | null;
  member_name: string | null;
  external_party_id: number | null;
  external_party_name: string | null;
  recipient_type: "member" | "external" | "unknown";
  recipient_name: string | null;
  purpose: "membership" | "other";
  transaction_id: number | null;
  issued: string;
  due: string;
  amount: number;
  status: "Paid" | "Open" | "Overdue";
  description: string | null;
  period_start?: string | null;
  period_end?: string | null;
  created_at: string;
}

function adaptInvoice(b: BackendInvoice): Invoice {
  const recipientName =
    b.recipient_name ?? b.member_name ?? b.external_party_name ?? "";
  return {
    id: String(b.id),
    member: recipientName,
    memberId: b.member_id != null ? String(b.member_id) : null,
    externalPartyId:
      b.external_party_id != null ? String(b.external_party_id) : null,
    externalPartyName: b.external_party_name ?? null,
    recipientType:
      b.recipient_type === "external" ? "external" : "member",
    recipientName,
    purpose: b.purpose ?? "membership",
    issued: b.issued,
    due: b.due,
    amount: b.amount,
    status: b.status,
    description: b.description ?? null,
    periodStart: b.period_start ?? null,
    periodEnd: b.period_end ?? null,
    transactionId: b.transaction_id != null ? String(b.transaction_id) : null,
    createdAt: b.created_at ?? "",
    lines: (b.items ?? []).map((i) => ({ id: String(i.id), day: i.day, text: i.text, amount: i.amount })),
  };
}

export async function listInvoices(): Promise<Invoice[]> {
  const response = await fetchPages<BackendInvoice>(
    "/app/finance/invoices",
    new URLSearchParams(),
    1000,
  );
  return response.data.map(adaptInvoice);
}

/** One member's invoices, for their page in the member list. */
export async function listMemberInvoices(memberId: string): Promise<Invoice[]> {
  const response = await fetchPages<BackendInvoice>(
    "/app/finance/invoices",
    new URLSearchParams({ member_id: memberId }),
    1000,
  );
  return response.data.map(adaptInvoice);
}

export async function listMyInvoices(): Promise<Invoice[]> {
  const response = await fetchPages<BackendInvoice>(
    "/app/finance/invoices/mine",
    new URLSearchParams(),
    1000,
  );
  return response.data.map(adaptInvoice);
}

export interface InvoiceCreate {
  memberId?: string;
  externalPartyId?: string;
  issued: string;
  due: string;
  amount: number;
  purpose: "membership" | "other";
  categoryId?: string;
  description?: string;
}

export async function createInvoice(input: InvoiceCreate): Promise<Invoice> {
  const body: Record<string, unknown> = {
    issued: input.issued,
    due: input.due,
    amount: input.amount,
    purpose: input.purpose,
  };
  if (input.memberId) body.member_id = Number(input.memberId);
  if (input.externalPartyId)
    body.external_party_id = Number(input.externalPartyId);
  if (input.categoryId) body.category_id = Number(input.categoryId);
  if (input.description) body.description = input.description;
  const b = await apiFetch<BackendInvoice>("/app/finance/invoices", {
    method: "POST",
    body: JSON.stringify(body),
  });
  return adaptInvoice(b);
}

export async function createBulkInvoices(input: {
  due: string;
  tierId?: string;
  description?: string;
}): Promise<{ created: number; invoices: Invoice[] }> {
  const body: Record<string, unknown> = { due: input.due };
  if (input.tierId) body.tier_id = Number(input.tierId);
  if (input.description) body.description = input.description;
  const r = await apiFetch<{ created: number; invoices: BackendInvoice[] }>(
    "/app/finance/invoices/bulk",
    { method: "POST", body: JSON.stringify(body) },
  );
  return { created: r.created, invoices: r.invoices.map(adaptInvoice) };
}

export type FeeRunLine = {
  memberId: number;
  name: string;
  tier: string;
  amount: number;
  periodStart: string;
  periodEnd: string;
  prorated: boolean;
  ownCycle: string | null;
  noEmail: boolean;
};

export type FeeRunPreview = {
  on: string;
  count: number;
  total: number;
  dueOn: string;
  mailed: boolean;
  tiers: { tierId: number; tier: string; count: number; total: number }[];
  lines: FeeRunLine[];
  truncated: boolean;
  noEmail: number;
  ownCycle: number;
  prorated: number;
  skipped: Record<string, number>;
  lastTwelveMonths: { count: number; total: number };
};

/** What the daily invoice run would bill on `on` (YYYY-MM-DD). Writes nothing. */
export async function getFeeRunPreview(on?: string): Promise<FeeRunPreview> {
  const q = on ? `?on=${encodeURIComponent(on)}` : "";
  return apiFetch<FeeRunPreview>(`/app/finance/invoices/fee-run-preview${q}`);
}

export async function updateInvoice(
  id: string,
  input: {
    status?: string;
    amount?: number;
    due?: string;
    description?: string | null;
  },
): Promise<Invoice> {
  const b = await apiFetch<BackendInvoice>(`/app/finance/invoices/${id}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
  return adaptInvoice(b);
}

export async function getInvoice(id: string): Promise<Invoice> {
  const b = await apiFetch<BackendInvoice>(`/app/finance/invoices/${id}`);
  return adaptInvoice(b);
}

export async function deleteInvoice(id: string): Promise<void> {
  await apiFetch(`/app/finance/invoices/${id}`, { method: "DELETE" });
}

export async function sendInvoiceReminder(
  id: string,
): Promise<{ ok: boolean; remindedAt?: string }> {
  return apiFetch(`/app/finance/invoices/${id}/remind`, { method: "POST" });
}

export async function downloadInvoicePdf(id: string): Promise<void> {
  const res = await apiFetchRaw(`/app/finance/invoices/${id}/qr-bill.pdf`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `invoice-${id}.pdf`;
  a.click();
  URL.revokeObjectURL(url);
}

export type FeeBasisSource = 'manual' | 'recurring' | 'last_year' | 'budget'

export interface FeeBasisLine {
  categoryId: number | null
  name: string | null
  color: string | null
  amount: number
  share: number
  items: { id?: number; description: string; interval?: string; amount?: number; yearly?: number }[]
}

export interface FeeBasisTier {
  id: number
  name: string
  priceType: 'percentage' | 'formula'
  billingCycle: string | null
  members: number
  yearlyNow: number
  yearly: number
}

export interface FeeBasis {
  source: FeeBasisSource
  sources: FeeBasisSource[]
  total: number
  extra: number
  manual: number
  period: { from?: string; to?: string; year?: number } | null
  note: string | null
  lines: FeeBasisLine[]
  tiers: FeeBasisTier[]
}

export interface FeeBasisPreview {
  source?: FeeBasisSource
  extra?: number
  manual?: number
}

/** How the yearly expenses come together; *preview* tries a choice unsaved. */
export async function getFeeBasis(preview: FeeBasisPreview = {}): Promise<FeeBasis> {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(preview)) if (v !== undefined) qs.set(k, String(v))
  const b = await apiFetch<{
    source: FeeBasisSource
    sources: FeeBasisSource[]
    total: number
    extra: number
    manual: number
    period: FeeBasis['period']
    note: string | null
    lines: {
      category_id: number | null
      name: string | null
      color: string | null
      amount: number
      share: number
      items: FeeBasisLine['items']
    }[]
    tiers: {
      id: number
      name: string
      price_type: 'percentage' | 'formula'
      billing_cycle: string | null
      members: number
      yearly_now: number
      yearly: number
    }[]
  }>(`/app/finance/fee-basis${qs.size ? `?${qs}` : ''}`)
  return {
    source: b.source,
    sources: b.sources,
    total: b.total,
    extra: b.extra,
    manual: b.manual,
    period: b.period,
    note: b.note,
    lines: b.lines.map((l) => ({
      categoryId: l.category_id,
      name: l.name,
      color: l.color,
      amount: l.amount,
      share: l.share,
      items: l.items,
    })),
    tiers: b.tiers.map((t) => ({
      id: t.id,
      name: t.name,
      priceType: t.price_type,
      billingCycle: t.billing_cycle,
      members: t.members,
      yearlyNow: t.yearly_now,
      yearly: t.yearly,
    })),
  }
}
