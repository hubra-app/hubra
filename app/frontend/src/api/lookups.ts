import { apiFetch } from '@hubra/api-client';

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

export function clearLookups(): void {
  // No-op — lookups are now cached by React Query (qk.lookups).
  // Invalidate via queryClient.invalidateQueries({ queryKey: qk.lookups })
  // after tier/role/group mutations.
}

export async function getLookups(): Promise<Lookups> {
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
