import { apiFetch } from '@hubra/api-client';
import { clearLookups } from "./lookups";
import type { MembershipTier } from "../types";

interface BackendTier {
  id: number;
  name: string;
  price_chf: number | null;
  color: string | null;
  billing_cycle: "monthly" | "yearly" | null;
  price_type: "fixed" | "percentage" | "formula";
  percentage_value: number | null;
  coefficient: number | null;
  round_to: number | null;
  deduct_tier_ids: number[];
}

function adapt(b: BackendTier): MembershipTier {
  return {
    id: String(b.id),
    name: b.name,
    color: b.color ?? "#7441e0",
    priceChf: b.price_chf,
    billingCycle: b.billing_cycle,
    priceType: b.price_type,
    percentageValue: b.percentage_value,
    coefficient: b.coefficient,
    roundTo: b.round_to,
    deductTierIds: b.deduct_tier_ids ?? [],
  };
}

export async function listTiers(): Promise<MembershipTier[]> {
  const data = await apiFetch<BackendTier[]>("/tiers");
  return data.map(adapt);
}

export async function createTier(input: {
  name: string;
  priceChf: number | null;
  color: string;
  billingCycle: "monthly" | "yearly" | null;
  priceType: "fixed" | "percentage" | "formula";
  percentageValue: number | null;
  coefficient: number | null;
  roundTo: number | null;
  deductTierIds: number[];
}): Promise<MembershipTier> {
  const b = await apiFetch<BackendTier>("/tiers/", {
    method: "POST",
    body: JSON.stringify({
      name: input.name,
      price_chf: input.priceChf,
      color: input.color,
      billing_cycle: input.billingCycle,
      price_type: input.priceType,
      percentage_value: input.percentageValue,
      coefficient: input.coefficient,
      round_to: input.roundTo,
      deduct_tier_ids: input.deductTierIds,
    }),
  });
  clearLookups();
  return adapt(b);
}

export async function updateTier(
  id: string,
  input: Partial<{
    name: string;
    priceChf: number | null;
    color: string;
    billingCycle: "monthly" | "yearly" | null;
    priceType: "fixed" | "percentage" | "formula";
    percentageValue: number | null;
    coefficient: number | null;
    roundTo: number | null;
    deductTierIds: number[];
  }>,
): Promise<MembershipTier> {
  const body: Record<string, unknown> = {};
  if (input.name !== undefined) body.name = input.name;
  if (input.priceChf !== undefined) body.price_chf = input.priceChf;
  if (input.color !== undefined) body.color = input.color;
  if (input.billingCycle !== undefined) body.billing_cycle = input.billingCycle;
  if (input.priceType !== undefined) body.price_type = input.priceType;
  if (input.percentageValue !== undefined)
    body.percentage_value = input.percentageValue;
  if (input.coefficient !== undefined) body.coefficient = input.coefficient;
  if (input.roundTo !== undefined) body.round_to = input.roundTo;
  if (input.deductTierIds !== undefined)
    body.deduct_tier_ids = input.deductTierIds;
  const b = await apiFetch<BackendTier>(`/tiers/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  clearLookups();
  return adapt(b);
}

export interface TierCostPreview {
  amount: number;
  amount_yearly: number;
  period: "monthly" | "yearly" | null;
  members: number;
  summary: string;
}

export async function calculateTierCost(config: {
  priceType: "fixed" | "percentage" | "formula";
  billingCycle: "monthly" | "yearly" | null;
  priceChf?: number | null;
  percentageValue?: number | null;
  coefficient?: number | null;
  roundTo?: number | null;
  deductTierIds?: number[];
  tierId?: number;
}): Promise<TierCostPreview> {
  return apiFetch<TierCostPreview>("/tiers/calculate-cost", {
    method: "POST",
    body: JSON.stringify({
      price_type: config.priceType,
      billing_cycle: config.billingCycle,
      price_chf: config.priceChf,
      percentage_value: config.percentageValue,
      coefficient: config.coefficient,
      round_to: config.roundTo,
      deduct_tier_ids: config.deductTierIds,
      tier_id: config.tierId,
    }),
  });
}

export async function deleteTier(id: string): Promise<void> {
  await apiFetch(`/tiers/${id}`, { method: "DELETE" });
  clearLookups();
}
