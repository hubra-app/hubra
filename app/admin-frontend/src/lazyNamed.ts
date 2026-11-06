import { lazy, type ComponentType } from 'react'

/** React.lazy for a named export, keeping its props:
 * `lazyNamed(() => import('./X'), 'X')`. */
export function lazyNamed<M, K extends keyof M>(load: () => Promise<M>, name: K) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return lazy(async () => ({ default: (await load())[name] as M[K] & ComponentType<any> }))
}
