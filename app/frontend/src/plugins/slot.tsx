import type { ComponentType } from 'react'
import { PluginBoundary } from './boundary'
import { useVisible } from './hooks'
import type { PluginSlotEntry, SlotProps } from './types'

/** Renders what plugins registered at `name`, in order. */
export function PluginSlot<K extends keyof SlotProps>({
  name,
  props,
}: {
  name: K
  props?: SlotProps[K]
}) {
  const entries = useVisible<PluginSlotEntry>((p) => p.slots).filter((s) => s.slot === name)
  return (
    <>
      {entries.map((e, i) => {
        const C = e.component as ComponentType<SlotProps[K]>
        return (
          <PluginBoundary key={`${e.plugin}-${i}`} plugin={e.plugin}>
            <C {...((props ?? {}) as SlotProps[K])} />
          </PluginBoundary>
        )
      })}
    </>
  )
}
