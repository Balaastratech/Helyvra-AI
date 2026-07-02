import { useEffect, useMemo, useRef, useState, type MutableRefObject } from 'react'
import ForceGraph2D, { type ForceGraphMethods } from 'react-force-graph-2d'
import { useContainerSize } from '@/hooks/useContainerSize'
import { LANES, LANE_LABEL, timeToX, type LayoutBox } from '@/lib/graphLayout'

export interface FCNode {
  id: string
  label: string
  color: string
  /** greyed/inactive (replaced or not-yet-known) */
  dim?: boolean
  marker?: '⊘' | null
  kind?: 'fact' | 'relative' | 'risk'
  active?: boolean
  fx?: number
  fy?: number
  // tooltip payload
  category?: string
  date?: string
  validTo?: string | null
  status?: string
  source?: string
  confidence?: number
  ontologyValid?: boolean | null
}
export interface FCLink {
  source: string
  target: string
  color: string
  dashed?: boolean
  arrow?: boolean
}

export type FgRef = MutableRefObject<
  ForceGraphMethods<FCNode & { x?: number; y?: number }, FCLink> | undefined
>

interface ForceCanvasProps {
  nodes: FCNode[]
  links: FCLink[]
  box: LayoutBox
  /** x-position (layout space) of the Rewind "as-of" cursor, or null to hide. */
  asOfX?: number | null
  onNodeClick?: (id: string) => void
  selectedId?: string | null
  onSelect?: (id: string | null) => void
  fgRef?: FgRef
  background?: string
  labelColor?: string
}

const LANE_TINT = ['rgba(14,140,132,0.04)', 'rgba(99,102,241,0.04)']

/**
 * Structured temporal-lane canvas: node positions are FIXED (x = time, y =
 * category lane) so the graph is a deterministic, legible grid rather than a
 * force blob. Draws lane bands + a time axis behind the nodes, a Rewind cursor,
 * a hover tooltip, highlight-on-select, and semantic-zoom labels.
 */
export function ForceCanvas({
  nodes,
  links,
  box,
  asOfX = null,
  onNodeClick,
  selectedId = null,
  onSelect,
  fgRef: externalRef,
  background = 'rgba(0,0,0,0)',
  labelColor = '#0c1521',
}: ForceCanvasProps) {
  const { ref, width, height } = useContainerSize<HTMLDivElement>()
  const internalRef = useRef<
    ForceGraphMethods<FCNode & { x?: number; y?: number }, FCLink> | undefined
  >(undefined)
  const fgRef = externalRef ?? internalRef

  const [hovered, setHovered] = useState<FCNode | null>(null)
  const [cursor, setCursor] = useState<{ x: number; y: number }>({ x: 0, y: 0 })

  const idSig = nodes.map((n) => n.id).sort().join('|')

  // Adjacency for highlight-on-select (selected node + its direct neighbors).
  const neighbors = useMemo(() => {
    const m = new Map<string, Set<string>>()
    const add = (a: string, b: string) => {
      if (!m.has(a)) m.set(a, new Set())
      m.get(a)!.add(b)
    }
    for (const l of links) {
      add(l.source, l.target)
      add(l.target, l.source)
    }
    return m
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idSig, links.length])

  const isLit = (id: string): boolean => {
    if (!selectedId) return true
    return id === selectedId || !!neighbors.get(selectedId)?.has(id)
  }
  const linkLit = (l: FCLink): boolean => {
    if (!selectedId) return true
    return l.source === selectedId || l.target === selectedId
  }

  const graphData = useMemo(
    () => ({
      nodes: nodes.map((n) => ({ ...n, x: n.fx, y: n.fy })),
      links: links.map((l) => ({ ...l })),
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [nodes, links, idSig],
  )

  // Positions are fixed via fx/fy — kill the simulation forces so nothing drifts.
  useEffect(() => {
    const fg = fgRef.current
    if (!fg) return
    fg.d3Force('charge', null)
    fg.d3Force('link', null)
    fg.d3Force('center', null)
    const t = setTimeout(() => fg.zoomToFit(400, 40), 300)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idSig, width, height])

  // Year ticks across the data span for the time axis.
  const years = useMemo(() => {
    const out: { year: number; t: number }[] = []
    const y0 = new Date(box.min).getFullYear()
    const y1 = new Date(box.max).getFullYear()
    for (let y = y0; y <= y1; y++) out.push({ year: y, t: Date.parse(`${y}-01-01`) })
    return out
  }, [box.min, box.max])

  const drawBackground = (ctx: CanvasRenderingContext2D) => {
    // lane bands
    for (let i = 0; i < LANES.length; i++) {
      ctx.fillStyle = LANE_TINT[i % 2]
      ctx.fillRect(0, i * box.laneH, box.W, box.laneH)
    }
    // time-axis year gridlines + labels
    ctx.textAlign = 'center'
    ctx.textBaseline = 'bottom'
    ctx.font = '11px Inter, sans-serif'
    for (const { year, t } of years) {
      const x = timeToX(t, box)
      ctx.strokeStyle = 'rgba(90,107,123,0.14)'
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.moveTo(x, 0)
      ctx.lineTo(x, box.H)
      ctx.stroke()
      ctx.fillStyle = 'rgba(90,107,123,0.6)'
      ctx.fillText(String(year), x, box.H - 4)
    }
    // lane labels (left edge)
    ctx.textAlign = 'left'
    ctx.textBaseline = 'middle'
    ctx.font = '600 11px Inter, sans-serif'
    for (let i = 0; i < LANES.length; i++) {
      ctx.fillStyle = 'rgba(90,107,123,0.7)'
      ctx.fillText(LANE_LABEL[LANES[i]] ?? LANES[i], 8, box.laneH * (i + 0.5))
    }
    // Rewind "as-of" cursor
    if (asOfX != null) {
      ctx.strokeStyle = 'rgba(217,70,110,0.55)'
      ctx.lineWidth = 1.5
      ctx.setLineDash([6, 4])
      ctx.beginPath()
      ctx.moveTo(asOfX, 0)
      ctx.lineTo(asOfX, box.H)
      ctx.stroke()
      ctx.setLineDash([])
    }
  }

  return (
    <div
      ref={ref}
      className="relative h-full w-full"
      onMouseMove={(e) => {
        const r = (e.currentTarget as HTMLDivElement).getBoundingClientRect()
        setCursor({ x: e.clientX - r.left, y: e.clientY - r.top })
      }}
    >
      {width > 0 && (
        <ForceGraph2D
          ref={fgRef}
          width={width}
          height={height}
          graphData={graphData}
          backgroundColor={background}
          cooldownTicks={0}
          nodeRelSize={6}
          nodeId="id"
          onNodeClick={(n) => {
            const id = (n as FCNode).id
            onSelect?.(id)
            onNodeClick?.(id)
          }}
          onBackgroundClick={() => onSelect?.(null)}
          onNodeHover={(n) => setHovered((n as FCNode) ?? null)}
          onRenderFramePre={(ctx) => drawBackground(ctx)}
          linkColor={(l) => (l as FCLink).color}
          linkVisibility={(l) => linkLit(l as FCLink)}
          linkLineDash={(l) => ((l as FCLink).dashed ? [5, 3] : null)}
          linkWidth={(l) => ((l as FCLink).dashed ? 1.6 : 1)}
          linkDirectionalArrowLength={(l) => ((l as FCLink).arrow ? 4 : 0)}
          linkDirectionalArrowRelPos={1}
          nodeCanvasObjectMode={() => 'replace'}
          nodeCanvasObject={(node, ctx, globalScale) => {
            const n = node as FCNode & { x?: number; y?: number }
            const x = n.x ?? 0
            const y = n.y ?? 0
            const r = n.kind === 'relative' ? 7 : 6
            const lit = isLit(n.id)
            ctx.globalAlpha = !lit ? 0.12 : n.dim ? 0.4 : 1

            if (n.kind === 'relative') {
              // rounded square for a person/relative
              ctx.beginPath()
              ctx.rect(x - r, y - r, 2 * r, 2 * r)
              ctx.fillStyle = n.color
              ctx.fill()
            } else if (n.kind === 'risk') {
              // triangle for a risk
              ctx.beginPath()
              ctx.moveTo(x, y - r)
              ctx.lineTo(x + r, y + r)
              ctx.lineTo(x - r, y + r)
              ctx.closePath()
              ctx.fillStyle = n.color
              ctx.fill()
            } else {
              ctx.beginPath()
              ctx.arc(x, y, r, 0, 2 * Math.PI)
              ctx.fillStyle = n.color
              ctx.fill()
            }
            ctx.lineWidth = n.id === selectedId ? 2.4 : 1.5
            ctx.strokeStyle = n.id === selectedId ? '#0c1521' : n.dim ? 'rgba(12,21,33,0.18)' : n.color
            ctx.stroke()

            // ontology-grounded tick (small green dot, top-right)
            if (n.ontologyValid) {
              ctx.beginPath()
              ctx.arc(x + r - 1, y - r + 1, 2, 0, 2 * Math.PI)
              ctx.fillStyle = '#16a34a'
              ctx.fill()
            }
            if (n.marker) {
              ctx.strokeStyle = 'rgba(12,21,33,0.55)'
              ctx.lineWidth = 1.2
              ctx.beginPath()
              ctx.moveTo(x - r + 2, y + r - 2)
              ctx.lineTo(x + r - 2, y - r + 2)
              ctx.stroke()
            }

            // Semantic-zoom labels: only draw when relevant to keep density low.
            const relevant =
              hovered?.id === n.id ||
              (selectedId ? isLit(n.id) : n.active) ||
              globalScale > 1.4
            if (lit && relevant) {
              const fontSize = Math.max(11 / globalScale, 3)
              ctx.font = `${fontSize}px Inter, sans-serif`
              ctx.textAlign = 'center'
              ctx.textBaseline = 'top'
              ctx.lineWidth = Math.max(2.5 / globalScale, 1)
              ctx.strokeStyle = 'rgba(255,255,255,0.92)'
              ctx.strokeText(n.label, x, y + r + 3)
              ctx.fillStyle = n.dim ? '#8a99a8' : labelColor
              ctx.fillText(n.label, x, y + r + 3)
            }
            ctx.globalAlpha = 1
          }}
          nodePointerAreaPaint={(node, color, ctx) => {
            const n = node as FCNode & { x?: number; y?: number }
            ctx.fillStyle = color
            ctx.beginPath()
            ctx.arc(n.x ?? 0, n.y ?? 0, 9, 0, 2 * Math.PI)
            ctx.fill()
          }}
        />
      )}

      {hovered && (
        <div
          className="pointer-events-none absolute z-10 max-w-[240px] rounded-lg border border-border bg-surface/95 px-3 py-2 text-xs shadow-lg backdrop-blur"
          style={{
            left: Math.min(cursor.x + 14, (width || 0) - 250),
            top: Math.min(cursor.y + 14, (height || 0) - 130),
          }}
        >
          <div className="font-semibold text-text">{hovered.label}</div>
          <div className="mt-1 space-y-0.5 text-text-muted">
            {hovered.category && <div>{hovered.category}</div>}
            <div>
              {hovered.date}
              {hovered.validTo ? ` → ${hovered.validTo}` : ''}
            </div>
            {hovered.status && <div>Status: {hovered.status}</div>}
            {hovered.source && <div>Source: {hovered.source}</div>}
            {typeof hovered.confidence === 'number' && (
              <div>Confidence: {Math.round(hovered.confidence * 100)}%</div>
            )}
            {hovered.ontologyValid && <div className="text-[#16a34a]">✓ ontology-grounded</div>}
          </div>
        </div>
      )}
    </div>
  )
}
