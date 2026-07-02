import type { GraphNode } from '@/api/types'

export const LANES = [
  'Allergy',
  'Condition',
  'Medication',
  'LabResult',
  'Vital',
  'Family',
  'Lifestyle',
  'Other',
] as const

export const LANE_LABEL: Record<string, string> = {
  Allergy: 'Allergies',
  Condition: 'Conditions',
  Medication: 'Medications',
  LabResult: 'Labs',
  Vital: 'Vitals',
  Family: 'Family',
  Lifestyle: 'Lifestyle',
  Other: 'Other',
}

const LANE_INDEX: Record<string, number> = Object.fromEntries(LANES.map((l, i) => [l, i]))

/** Distinct calm color per category — shared by the canvas node fill and the legend. */
export const CATEGORY_COLOR: Record<string, string> = {
  Allergy: '#e11d48',
  Condition: '#6366f1',
  Medication: '#0e8c84',
  LabResult: '#d97706',
  Vital: '#0891b2',
  Family: '#7c3aed',
  Lifestyle: '#16a34a',
  Other: '#64748b',
}

export const colorOf = (category?: string): string =>
  CATEGORY_COLOR[category ?? 'Other'] ?? CATEGORY_COLOR.Other

export interface Positioned {
  id: string
  fx: number
  fy: number
  lane: number
}

/** Layout dimensions the canvas + background pass share. */
export interface LayoutBox {
  W: number
  H: number
  padX: number
  laneH: number
  min: number
  max: number
  span: number
}

/** X-position (in layout space) for a given time (ms). Shared by node layout +
 * the time axis + the rewind cursor so they stay aligned. */
export function timeToX(t: number, box: LayoutBox): number {
  return box.padX + ((t - box.min) / box.span) * (box.W - box.padX * 2)
}

/** Lane index for a node's category, defaulting unknowns to the Other lane. */
export function laneOf(node: GraphNode): number {
  return LANE_INDEX[node.category ?? 'Other'] ?? LANE_INDEX.Other
}

/** Compute x=time, y=lane positions in a normalized [0..W]x[0..H] space. Nodes in
 * the same lane + same date are nudged apart on x so labels never stack. */
export function layout(
  nodes: GraphNode[],
  W = 1000,
  H = 560,
): { positions: Map<string, Positioned>; box: LayoutBox } {
  const padX = 90
  const dates = nodes
    .map((n) => (n.valid_from ? Date.parse(n.valid_from) : NaN))
    .filter((d) => !Number.isNaN(d))
  const min = dates.length ? Math.min(...dates) : 0
  const max = dates.length ? Math.max(...dates) : 1
  const span = Math.max(1, max - min)
  const laneH = H / LANES.length
  const box: LayoutBox = { W, H, padX, laneH, min, max, span }

  const perDate = new Map<string, number>()
  const positions = new Map<string, Positioned>()
  for (const n of nodes) {
    const lane = laneOf(n)
    const t = n.valid_from ? Date.parse(n.valid_from) : min
    const baseX = timeToX(Number.isNaN(t) ? min : t, box)
    const key = `${lane}:${Math.round(baseX)}`
    const bump = perDate.get(key) ?? 0
    perDate.set(key, bump + 1)
    positions.set(n.id, { id: n.id, lane, fx: baseX + bump * 26, fy: laneH * (lane + 0.5) })
  }
  return { positions, box }
}
