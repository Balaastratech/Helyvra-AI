/** Date helpers + client-side status computation (mirrors backend _status_at). */
import type { GraphNode } from '@/api/types'

export const DAY = 86_400_000

export const parseDate = (s: string) => new Date(`${s}T00:00:00`)

export const isoOf = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(
    d.getDate(),
  ).padStart(2, '0')}`

export const todayIso = () => isoOf(new Date())

/**
 * Display status of a fact at `asOf` (null = now). Mirrors the backend exactly:
 * active iff valid_from <= asOf < valid_to (or no valid_to); else replaced.
 * Computed in the browser so the Rewind slider morphs the graph with NO refetch.
 */
export type DisplayStatus = 'active' | 'replaced' | 'future'

export function statusAt(node: GraphNode, asOf: string | null): DisplayStatus {
  const at = parseDate(asOf ?? todayIso()).getTime()
  const from = parseDate(node.valid_from).getTime()
  const to = node.valid_to ? parseDate(node.valid_to).getTime() : null
  if (from > at) return 'future' // not yet known at this date
  if (to !== null && to <= at) return 'replaced'
  return 'active'
}

/** Is the fact "off" (greyed) at this date? future + replaced both read as off. */
export const isInactive = (s: DisplayStatus) => s !== 'active'
