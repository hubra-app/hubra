import { apiFetch, apiFetchRaw } from '@hubra/api-client';
import type {
  Transaction,
  Invoice,
  TransactionCategory,
  ExternalParty,
} from "@/types";
import { fetchPages } from "@/api/pages";

// ── Transaction Categories ─────────────────────────────────────────────────

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
    "/finance/transaction-categories",
  );
  return data.map(adaptTxCat);
}

export async function createTxCategory(input: {
  name: string;
  color?: string;
}): Promise<TransactionCategory> {
  const b = await apiFetch<BackendTxCategory>(
    "/finance/transaction-categories",
    { method: "POST", body: JSON.stringify(input) },
  );
  return adaptTxCat(b);
}

export async function updateTxCategory(
  id: string,
  input: { name?: string; color?: string },
): Promise<TransactionCategory> {
  const b = await apiFetch<BackendTxCategory>(
    `/finance/transaction-categories/${id}`,
    { method: "PATCH", body: JSON.stringify(input) },
  );
  return adaptTxCat(b);
}

export async function deleteTxCategory(id: string): Promise<void> {
  await apiFetch(`/finance/transaction-categories/${id}`, { method: "DELETE" });
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
    `/finance/external-parties${qs}`,
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
    "/finance/external-parties",
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
    `/finance/external-parties/${id}`,
    { method: "PATCH", body: JSON.stringify(body) },
  );
  return adaptExtParty(b);
}

export async function deleteExternalParty(id: string): Promise<void> {
  await apiFetch(`/finance/external-parties/${id}`, { method: "DELETE" });
}

// ── Transactions ───────────────────────────────────────────────────────────

interface BackendTransaction {
  id: number;
  date: string;
  description: string;
  category_id: number | null;
  category_name: string | null;
  member_id: number | null;
  member_name: string | null;
  payee_name: string | null;
  amount: number;
  method: string;
  type: "income" | "expense";
  status: "Pending" | "Completed";
  invoice_id: number | null;
  created_at: string;
}

function adaptTx(b: BackendTransaction): Transaction {
  return {
    id: String(b.id),
    date: b.date,
    description: b.description,
    category: b.category_name ?? String(b.category_id ?? ""),
    member:
      b.payee_name ??
      b.member_name ??
      (b.member_id ? String(b.member_id) : "—"),
    amount: b.amount,
    method: b.method,
    type: b.type,
    status: b.status ?? "Completed",
    invoiceId: b.invoice_id != null ? String(b.invoice_id) : null,
    createdAt: b.created_at ?? "",
    categoryId: b.category_id != null ? String(b.category_id) : null,
    memberName: b.member_name,
    payeeName: b.payee_name,
  };
}

export async function listTransactions(params?: {
  pageSize?: number;
}): Promise<Transaction[]> {
  const response = await fetchPages<BackendTransaction>(
    "/finance/transactions",
    new URLSearchParams(),
    params?.pageSize ?? 1000,
  );
  return response.data.map(adaptTx);
}

export interface TransactionCreate {
  date: string;
  description: string;
  categoryId?: string;
  memberId?: string;
  payeeName?: string;
  amount: number;
  method: string;
  type: "income" | "expense";
}

export async function createTransaction(
  input: TransactionCreate,
): Promise<Transaction> {
  const body: Record<string, unknown> = {
    date: input.date,
    description: input.description,
    amount: input.amount,
    method: input.method,
    type: input.type,
  };
  if (input.categoryId) body.category_id = Number(input.categoryId);
  if (input.memberId) body.member_id = Number(input.memberId);
  if (input.payeeName) body.payee_name = input.payeeName;
  const b = await apiFetch<BackendTransaction>("/finance/transactions", {
    method: "POST",
    body: JSON.stringify(body),
  });
  return adaptTx(b);
}

export async function updateTransaction(
  id: string,
  input: Partial<TransactionCreate> & { status?: "Pending" | "Completed" },
): Promise<Transaction> {
  const body: Record<string, unknown> = {};
  if (input.status !== undefined) body.status = input.status;
  if (input.description !== undefined) body.description = input.description;
  if (input.date !== undefined) body.date = input.date;
  if (input.amount !== undefined) body.amount = input.amount;
  if (input.method !== undefined) body.method = input.method;
  if (input.type !== undefined) body.type = input.type;
  if (input.categoryId !== undefined)
    body.category_id = input.categoryId ? Number(input.categoryId) : null;
  if (input.memberId !== undefined) body.member_id = Number(input.memberId);
  if (input.payeeName !== undefined) body.payee_name = input.payeeName;
  const b = await apiFetch<BackendTransaction>(`/finance/transactions/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  return adaptTx(b);
}

export async function deleteTransaction(id: string): Promise<void> {
  await apiFetch(`/finance/transactions/${id}`, { method: "DELETE" });
}

// ── Invoices ───────────────────────────────────────────────────────────────

interface BackendInvoice {
  id: number;
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
    transactionId: b.transaction_id != null ? String(b.transaction_id) : null,
    createdAt: b.created_at ?? "",
  };
}

export async function listInvoices(): Promise<Invoice[]> {
  const response = await fetchPages<BackendInvoice>(
    "/finance/invoices",
    new URLSearchParams(),
    1000,
  );
  return response.data.map(adaptInvoice);
}

/** One member's invoices, for their page in the member list. */
export async function listMemberInvoices(memberId: string): Promise<Invoice[]> {
  const response = await fetchPages<BackendInvoice>(
    "/finance/invoices",
    new URLSearchParams({ member_id: memberId }),
    1000,
  );
  return response.data.map(adaptInvoice);
}

export async function listMyInvoices(): Promise<Invoice[]> {
  const response = await fetchPages<BackendInvoice>(
    "/finance/invoices/mine",
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
  const b = await apiFetch<BackendInvoice>("/finance/invoices", {
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
    "/finance/invoices/bulk",
    { method: "POST", body: JSON.stringify(body) },
  );
  return { created: r.created, invoices: r.invoices.map(adaptInvoice) };
}

export async function updateInvoice(
  id: string,
  input: { status?: string },
): Promise<Invoice> {
  const b = await apiFetch<BackendInvoice>(`/finance/invoices/${id}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
  return adaptInvoice(b);
}

export async function getInvoice(id: string): Promise<Invoice> {
  const b = await apiFetch<BackendInvoice>(`/finance/invoices/${id}`);
  return adaptInvoice(b);
}

export async function deleteInvoice(id: string): Promise<void> {
  await apiFetch(`/finance/invoices/${id}`, { method: "DELETE" });
}

export async function sendInvoiceReminder(
  id: string,
): Promise<{ ok: boolean; remindedAt?: string }> {
  return apiFetch(`/finance/invoices/${id}/remind`, { method: "POST" });
}

export async function downloadInvoicePdf(id: string): Promise<void> {
  const res = await apiFetchRaw(`/finance/invoices/${id}/qr-bill.pdf`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `invoice-${id}.pdf`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Finance Overview ───────────────────────────────────────────────────────

export interface FinanceOverview {
  balance: number;
  incomeMTD: number;
  expensesMTD: number;
  netMTD: number;
  months: { m: string; year?: number; month?: number; inc: number; exp: number }[];
  openInvoices: { count: number; amount: number };
}

export async function getFinanceOverview(): Promise<FinanceOverview> {
  return apiFetch<FinanceOverview>("/finance/overview");
}
