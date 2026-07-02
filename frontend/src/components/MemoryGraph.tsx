import { useMemo, useRef, useState } from 'react'
import { ForceCanvas, type FCLink, type FCNode, type FgRef } from './ForceCanvas'
import { GraphLegend } from './GraphLegend'
import { useTimeline } from '@/api/hooks'
import { useUi } from '@/store'
import { statusAt } from '@/lib/time'
import { LANES, colorOf, layout, timeToX } from '@/lib/graphLayout'
import type { GraphNode } from '@/api/types'

const SUPERSEDE = '#d7263d'
const FAMILY = '#7c3aed'
const RISK = '#d97706'
const SAME_SUBJECT = 'rgba(90,107,123,0.28)'

/**
 * The memory graph: a temporal category-lane layout (x = time, y = category)
 * with hover detail, category filtering, highlight-on-select, semantic-zoom
 * labels and a Rewind time cursor. Status is recomputed from the Rewind date on
 * the client (statusAt) so dragging the slider morphs the graph with no refetch.
 */
export function MemoryGraph() {
  const { patientId, asOf, openWhy } = useUi()
  const { data } = useTimeline(patientId)
  const [hidden, setHidden] = useState<Set<string>>(new Set())
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const fgRef = useRef<FgRef['current']>(undefined)

  const allNodes = data?.nodes ?? []

  // Categories present, ordered by the lane order (drives the legend chips).
  const categories = useMemo(() => {
    const present = new Set(allNodes.map((n) => n.category ?? 'Other'))
    return LANES.filter((l) => present.has(l))
  }, [allNodes])

  const visibleNodes = useMemo(
    () => allNodes.filter((n) => !hidden.has(n.category ?? 'Other')),
    [allNodes, hidden],
  )

  const { positions, box } = useMemo(() => layout(visibleNodes), [visibleNodes])

  const nodes: FCNode[] = useMemo(() => {
    return visibleNodes.map((n: GraphNode) => {
      const p = positions.get(n.id)
      const st = statusAt(n, asOf)
      const active = st === 'active'
      return {
        id: n.id,
        label: n.label,
        color: colorOf(n.category),
        dim: !active,
        marker: st === 'replaced' ? '⊘' : null,
        kind: n.kind ?? 'fact',
        active,
        fx: p?.fx,
        fy: p?.fy,
        category: n.category,
        date: n.valid_from,
        validTo: n.valid_to,
        status: st,
        source: n.source,
        confidence: n.confidence,
        ontologyValid: n.ontology_valid,
      }
    })
  }, [visibleNodes, positions, asOf])

  const links: FCLink[] = useMemo(() => {
    const present = new Set(visibleNodes.map((n) => n.id))
    return (data?.edges ?? [])
      .filter((e) => present.has(e.source) && present.has(e.target))
      .map((e) => {
        switch (e.type) {
          case 'SUPERSEDED_BY':
            return { source: e.source, target: e.target, color: SUPERSEDE, dashed: true, arrow: true }
          case 'RELATED_TO':
            return { source: e.source, target: e.target, color: FAMILY }
          case 'RISK':
            return { source: e.source, target: e.target, color: RISK, dashed: true }
          default:
            return { source: e.source, target: e.target, color: SAME_SUBJECT }
        }
      })
  }, [data, visibleNodes])

  // Rewind cursor: only show a moving "as-of" line while actively scrubbing.
  const asOfX = useMemo(() => {
    if (!asOf) return null
    return timeToX(new Date(`${asOf}T00:00:00`).getTime(), box)
  }, [asOf, box])

  const toggle = (cat: string) =>
    setHidden((prev) => {
      const next = new Set(prev)
      next.has(cat) ? next.delete(cat) : next.add(cat)
      return next
    })

  return (
    <div className="relative h-full w-full">
      <ForceCanvas
        nodes={nodes}
        links={links}
        box={box}
        asOfX={asOfX}
        onNodeClick={openWhy}
        selectedId={selectedId}
        onSelect={setSelectedId}
        fgRef={fgRef}
      />
      {categories.length > 0 && (
        <GraphLegend categories={categories} hidden={hidden} onToggle={toggle} fgRef={fgRef} />
      )}
    </div>
  )
}
