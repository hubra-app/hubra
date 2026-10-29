import { apiFetch } from '@hubra/api-client';
import { queryClient } from "@/queryClient";
import { qk } from "@/data/keys";

interface BackendTier {
  id: number;
  name: string;
  price_chf: number | null;
  color: string | null;
}
interface BackendRole {
  id: number;
  name: string;
  is_default: boolean;
}
interface BackendGroup {
  id: number;
  name: string;
  color: string | null;
}

export interface Lookups {
  tiers: Map<number, { name: string; color: string; priceChf: number }>;
  tiersByName: Map<string, number>;
  roles: Map<number, string>;
  rolesByName: Map<string, number>;
  groups: Map<number, { name: string; color: string }>;
  groupsByName: Map<string, number>;
}

/** Tiers, roles and groups by id and by name, cached under ['lookups']. */
export const lookupsQuery = {
  queryKey: qk.lookups,
  queryFn: fetchLookups,
};

/** Mark the cached lookups stale after a tier, role or group changed. */
export function clearLookups(): void {
  void queryClient.invalidateQueries({
    queryKey: lookupsQuery.queryKey,
    refetchType: "none",
  });
}

/**
 * The cached lookups, fetched once for every caller that needs them within
 * the query client's stale time (the member list asks on each search).
 */
export function getLookups(): Promise<Lookups> {
  return queryClient.fetchQuery(lookupsQuery);
}

async function fetchLookups(): Promise<Lookups> {
  const results = await Promise.allSettled([
    apiFetch<BackendTier[]>("/tiers"),
    apiFetch<BackendRole[]>("/roles"),
    apiFetch<BackendGroup[]>("/groups"),
  ]);
  const tiers = results[0].status === "fulfilled" ? results[0].value : [];
  const roles = results[1].status === "fulfilled" ? results[1].value : [];
  const groups = results[2].status === "fulfilled" ? results[2].value : [];
  return {
    tiers: new Map(
      tiers.map((t) => [
        t.id,
        {
          name: t.name,
          color: t.color ?? "#7441e0",
          priceChf: t.price_chf ?? 0,
        },
      ]),
    ),
    tiersByName: new Map(tiers.map((t) => [t.name, t.id])),
    roles: new Map(roles.map((r) => [r.id, r.name])),
    rolesByName: new Map(roles.map((r) => [r.name, r.id])),
    groups: new Map(
      groups.map((g) => [g.id, { name: g.name, color: g.color ?? "#7441e0" }]),
    ),
    groupsByName: new Map(groups.map((g) => [g.name, g.id])),
  };
}
