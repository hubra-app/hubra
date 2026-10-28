import { apiFetch } from '@vollbuild/api-client';
import type {
  InventoryItem,
  InventoryCategory,
  InventoryStatus,
  InventoryVisibility,
  InventoryLink,
} from "@/types";

interface BackendInventoryItem {
  id: number;
  name: string;
  category: string;
  description: string | null;
  owner_id: number | null;
  owner_name: string | null;
  responsible_id: number | null;
  responsible_name: string | null;
  visibility: string;
  status: string;
  cost: string | null;
  links: { label: string; url: string }[];
  instruction_required: boolean;
  instructed_member_ids: number[];
  instructed_member_names: string[];
  created_at: string;
  updated_at: string;
  purchase_date: string | null;
  purchase_cost: string | null;
  current_value: string | null;
  location: string | null;
  serial_number: string | null;
  barcode_id: string | null;
  documents: { name: string; url: string; type?: string }[] | null;
  image_url: string | null;
  notes: string | null;
}

function adapt(b: BackendInventoryItem): InventoryItem {
  return {
    id: String(b.id),
    name: b.name,
    category: b.category as InventoryCategory,
    description: b.description ?? "",
    ownerId: b.owner_id,
    ownerName: b.owner_name,
    responsibleId: b.responsible_id,
    responsibleName: b.responsible_name,
    visibility: b.visibility as InventoryVisibility,
    status: b.status as InventoryStatus,
    cost: b.cost,
    links: b.links ?? [],
    instructionRequired: b.instruction_required,
    instructedMemberIds: b.instructed_member_ids ?? [],
    instructedMemberNames: b.instructed_member_names ?? [],
    createdAt: b.created_at,
    updatedAt: b.updated_at,
    purchaseDate: b.purchase_date ?? "",
    purchaseCost: b.purchase_cost ?? null,
    currentValue: b.current_value ?? null,
    location: b.location ?? "",
    serialNumber: b.serial_number ?? "",
    barcodeId: b.barcode_id ?? "",
    documents: b.documents ?? [],
    imageUrl: b.image_url ?? null,
    notes: b.notes ?? "",
  };
}

export interface ListInventoryParams {
  category?: InventoryCategory;
  status?: InventoryStatus;
  visibility?: InventoryVisibility;
}

export async function listInventory(
  params: ListInventoryParams = {},
): Promise<InventoryItem[]> {
  const qs = new URLSearchParams();
  if (params.category) qs.set("category", params.category);
  if (params.status) qs.set("status", params.status);
  if (params.visibility) qs.set("visibility", params.visibility);
  const suffix = qs.toString() ? `?${qs}` : "";
  const data = await apiFetch<BackendInventoryItem[]>(`/inventory/${suffix}`);
  return data.map(adapt);
}

export async function getInventoryItem(id: string): Promise<InventoryItem> {
  const b = await apiFetch<BackendInventoryItem>(`/inventory/${id}`);
  return adapt(b);
}

export interface InventoryItemCreate {
  name: string;
  category: InventoryCategory;
  description?: string;
  ownerId?: number | null;
  responsibleId?: number | null;
  visibility?: InventoryVisibility;
  status?: InventoryStatus;
  cost?: string | null;
  links?: InventoryLink[];
  instructionRequired?: boolean;
}

export async function createInventoryItem(
  input: InventoryItemCreate,
): Promise<InventoryItem> {
  const body: Record<string, unknown> = {
    name: input.name,
    category: input.category,
  };
  if (input.description !== undefined) body.description = input.description;
  if (input.ownerId !== undefined) body.owner_id = input.ownerId;
  if (input.responsibleId !== undefined)
    body.responsible_id = input.responsibleId;
  if (input.visibility) body.visibility = input.visibility;
  if (input.status) body.status = input.status;
  if (input.cost !== undefined) body.cost = input.cost;
  if (input.links !== undefined) body.links = input.links;
  if (input.instructionRequired !== undefined)
    body.instruction_required = input.instructionRequired;

  const b = await apiFetch<BackendInventoryItem>("/inventory/", {
    method: "POST",
    body: JSON.stringify(body),
  });
  return adapt(b);
}

export type InventoryItemUpdate = Partial<InventoryItemCreate>;

export async function updateInventoryItem(
  id: string,
  input: InventoryItemUpdate,
): Promise<InventoryItem> {
  const body: Record<string, unknown> = {};
  if (input.name !== undefined) body.name = input.name;
  if (input.category !== undefined) body.category = input.category;
  if (input.description !== undefined) body.description = input.description;
  if ("ownerId" in input) body.owner_id = input.ownerId;
  if ("responsibleId" in input) body.responsible_id = input.responsibleId;
  if (input.visibility !== undefined) body.visibility = input.visibility;
  if (input.status !== undefined) body.status = input.status;
  if ("cost" in input) body.cost = input.cost;
  if (input.links !== undefined) body.links = input.links;
  if (input.instructionRequired !== undefined)
    body.instruction_required = input.instructionRequired;

  const b = await apiFetch<BackendInventoryItem>(`/inventory/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  return adapt(b);
}

export async function deleteInventoryItem(id: string): Promise<void> {
  await apiFetch(`/inventory/${id}`, { method: "DELETE" });
}

export async function addInstruction(
  itemId: string,
  memberId: number,
): Promise<void> {
  await apiFetch(`/inventory/${itemId}/instructions/${memberId}`, {
    method: "POST",
  });
}

export async function removeInstruction(
  itemId: string,
  memberId: number,
): Promise<void> {
  await apiFetch(`/inventory/${itemId}/instructions/${memberId}`, {
    method: "DELETE",
  });
}

export async function addSelfInstruction(itemId: string): Promise<void> {
  await apiFetch(`/inventory/${itemId}/instructions/self`, { method: "POST" });
}

export interface InventoryCheckout {
  id: number;
  itemId: number;
  memberId: number;
  memberName: string | null;
  checkedOutAt: string;
  expectedReturnAt: string | null;
  returnedAt: string | null;
  conditionNotes: string | null;
}

export async function checkoutItem(
  itemId: string,
  memberId: number,
  options?: { expectedReturnAt?: string; conditionNotes?: string },
): Promise<InventoryCheckout> {
  const body: Record<string, unknown> = { member_id: memberId };
  if (options?.expectedReturnAt !== undefined)
    body.expected_return_at = options.expectedReturnAt;
  if (options?.conditionNotes !== undefined)
    body.condition_notes = options.conditionNotes;
  const b = await apiFetch<BackendCheckout>(`/inventory/${itemId}/checkout`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  return adaptCheckout(b);
}

export async function checkinItem(
  itemId: string,
  conditionNotes?: string,
): Promise<InventoryCheckout> {
  const body: Record<string, unknown> = {};
  if (conditionNotes !== undefined) body.condition_notes = conditionNotes;
  const b = await apiFetch<BackendCheckout>(`/inventory/${itemId}/checkin`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  return adaptCheckout(b);
}

export async function listOverdueItems(): Promise<InventoryCheckout[]> {
  const data = await apiFetch<BackendCheckout[]>("/inventory/overdue");
  return data.map(adaptCheckout);
}

interface BackendCheckout {
  id: number;
  item_id: number;
  member_id: number;
  member_name: string | null;
  checked_out_at: string;
  expected_return_at: string | null;
  returned_at: string | null;
  condition_notes: string | null;
}

function adaptCheckout(b: BackendCheckout): InventoryCheckout {
  return {
    id: b.id,
    itemId: b.item_id,
    memberId: b.member_id,
    memberName: b.member_name,
    checkedOutAt: b.checked_out_at,
    expectedReturnAt: b.expected_return_at,
    returnedAt: b.returned_at,
    conditionNotes: b.condition_notes,
  };
}
