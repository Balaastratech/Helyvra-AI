import {
  Activity,
  FlaskConical,
  HeartPulse,
  Maximize2,
  Pill,
  ShieldAlert,
  Stethoscope,
  Users,
  ZoomIn,
  ZoomOut,
  type LucideIcon,
} from 'lucide-react'
import { CATEGORY_COLOR, LANE_LABEL } from '@/lib/graphLayout'
import type { FgRef } from './ForceCanvas'

const ICON: Record<string, LucideIcon> = {
  Allergy: ShieldAlert,
  Condition: Stethoscope,
  Medication: Pill,
  LabResult: FlaskConical,
  Vital: Activity,
  Family: Users,
  Lifestyle: HeartPulse,
  Other: Activity,
}

interface GraphLegendProps {
  /** categories present in the current graph (drives which chips to show). */
  categories: string[]
  hidden: Set<string>
  onToggle: (category: string) => void
  fgRef: FgRef
}

/** Legend + category filter chips + zoom/fit controls, floated over the canvas. */
export function GraphLegend({ categories, hidden, onToggle, fgRef }: GraphLegendProps) {
  const zoomBy = (factor: number) => {
    const fg = fgRef.current
    if (!fg) return
    fg.zoom(fg.zoom() * factor, 250)
  }
  return (
    <div className="pointer-events-auto absolute right-3 top-3 z-10 w-52 rounded-xl border border-border bg-surface/95 p-3 text-xs shadow-lg backdrop-blur">
      <div className="mb-1.5 flex items-center justify-between">
        <span className="font-semibold text-text">Categories</span>
        <div className="flex items-center gap-1">
          <button
            className="rounded p-1 text-text-muted hover:bg-border/40"
            title="Zoom in"
            onClick={() => zoomBy(1.3)}
          >
            <ZoomIn size={14} />
          </button>
          <button
            className="rounded p-1 text-text-muted hover:bg-border/40"
            title="Zoom out"
            onClick={() => zoomBy(1 / 1.3)}
          >
            <ZoomOut size={14} />
          </button>
          <button
            className="rounded p-1 text-text-muted hover:bg-border/40"
            title="Fit to view"
            onClick={() => fgRef.current?.zoomToFit(400, 40)}
          >
            <Maximize2 size={14} />
          </button>
        </div>
      </div>

      <div className="flex flex-col gap-1">
        {categories.map((cat) => {
          const Icon = ICON[cat] ?? Activity
          const off = hidden.has(cat)
          return (
            <button
              key={cat}
              onClick={() => onToggle(cat)}
              className={`flex items-center gap-2 rounded-md px-2 py-1 text-left transition ${
                off ? 'opacity-40' : 'hover:bg-border/30'
              }`}
              title={off ? 'Show lane' : 'Hide lane'}
            >
              <Icon size={13} style={{ color: CATEGORY_COLOR[cat] ?? CATEGORY_COLOR.Other }} />
              <span className="text-text">{LANE_LABEL[cat] ?? cat}</span>
            </button>
          )
        })}
      </div>

      <div className="mt-2 space-y-1 border-t border-border pt-2 text-text-muted">
        <div className="flex items-center gap-1.5">
          <svg width="24" height="8" aria-hidden>
            <line x1="0" y1="4" x2="24" y2="4" stroke="#d7263d" strokeWidth="1.6" strokeDasharray="5 3" />
          </svg>
          Replaced by
        </div>
        <div className="flex items-center gap-1.5">
          <svg width="24" height="8" aria-hidden>
            <line x1="0" y1="4" x2="24" y2="4" stroke="#7c3aed" strokeWidth="1.6" />
          </svg>
          Family
        </div>
      </div>
    </div>
  )
}
