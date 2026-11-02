import { useQuery } from '@tanstack/react-query'
import { listPlanChoices } from '@/api/tenants'
import { registerPlanNames } from '@/labels'

/** The plans a club can be on, with their names registered for planLabel. */
export function usePlanChoices(enabled = true) {
  return useQuery({
    queryKey: ['plan-choices'],
    queryFn: async () => {
      const data = await listPlanChoices()
      registerPlanNames(data.plans)
      return data
    },
    enabled,
    retry: false,
    staleTime: 60_000,
  })
}
