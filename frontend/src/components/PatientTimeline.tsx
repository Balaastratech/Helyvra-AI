import { useEffect, useRef } from 'react'
import { Timeline, type TimelineOptions } from 'vis-timeline/standalone'
import { DataSet } from 'vis-data'
import 'vis-timeline/styles/vis-timeline-graph2d.css'
import { useTimeline } from '@/api/hooks'
import { useUi } from '@/store'
import { statusAt, todayIso, parseDate } from '@/lib/time'
import type { GraphNode } from '@/api/types'

/**
 * Patient timeline (vis-timeline). The clinical-record pattern the research points
 * to: category swimlanes on a horizontal time axis, items that STACK instead of
 * overlapping (so labels never collide), pan/zoom, hover tooltips, click→Why.
 *
 * States with a duration (allergy / condition / medication / lifestyle) render as
 * duration BARS (start→end, end = now if still active) so "on lisinopril 2024→2026,
 * then amlodipine" reads instantly. Point-in-time facts (labs, vitals) and family
 * relatives render as POINTS. Superseded facts grey + strike through.
 */

// FHIR resource_type → swimlane (order = top-to-bottom).
const GROUPS: { id: string; label: string }[] = [
  { id: 'Allergy', label: 'Allergies' },
  { id: 'Condition', label: 'Conditions' },
  { id: 'Medication', label: 'Medications' },
  { id: 'LabResult', label: 'Labs' },
  { id: 'Vital', label: 'Vitals' },
  { id: 'Family', label: 'Family' },
  { id: 'Lifestyle', label: 'Lifestyle' },
  { id: 'Other', label: 'Other' },
]
const GROUP_IDS = new Set(GROUPS.map((g) => g.id))
const POINT_GROUPS = new Set(['LabResult', 'Vital', 'Family'])

function groupFor(n: GraphNode): string {
  if (n.kind === 'relative') return 'Family'
  const c = n.category ?? 'Other'
  return GROUP_IDS.has(c) ? c : 'Other'
}

function tooltip(n: GraphNode, superseded: boolean): string {
  const rows: string[] = [
    `<div style="font-weight:600;margin-bottom:2px">${escapeHtml(n.label)}</div>`,
    `<div>${escapeHtml(n.category ?? 'Other')}</div>`,
    `<div>${n.valid_from}${n.valid_to ? ` → ${n.valid_to}` : ''}</div>`,
    `<div>Source: ${escapeHtml(n.source ?? 'unknown')}</div>`,
  ]
  if (superseded) rows.push('<div style="color:#c77700">Replaced by a newer record</div>')
  if (n.ontology_valid) rows.push('<div style="color:#0e8c84">✓ grounded in medical ontology</div>')
  return `<div style="font:12px Inter,sans-serif;max-width:260px;line-height:1.4">${rows.join('')}</div>`
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]!))
}

export function PatientTimeline() {
  const { patientId, asOf, openWhy } = useUi()
  const { data } = useTimeline(patientId)
  const containerRef = useRef<HTMLDivElement>(null)
  const tlRef = useRef<Timeline | null>(null)
  const itemsRef = useRef<DataSet<any> | null>(null)

  // Build the timeline once the container exists.
  useEffect(() => {
    if (!containerRef.current || tlRef.current) return
    const items = new DataSet<any>([])
    const groups = new DataSet<any>(GROUPS.map((g) => ({ id: g.id, content: g.label })))
    itemsRef.current = items
    const options: TimelineOptions = {
      stack: true, // the key: overlapping items stack into rows, never collide
      editable: false, // dates are fixed — pan/zoom yes, drag items no
      selectable: true,
      zoomKey: 'ctrlKey',
      orientation: { axis: 'top', item: 'top' },
      margin: { item: { horizontal: 8, vertical: 6 }, axis: 8 },
      groupOrder: (a: any, b: any) =>
        GROUPS.findIndex((g) => g.id === a.id) - GROUPS.findIndex((g) => g.id === b.id),
      tooltip: { followMouse: true, overflowMethod: 'flip' },
      maxHeight: '100%',
      showCurrentTime: false,
    }
    const tl = new Timeline(containerRef.current, items, groups, options)
    tl.on('select', (props: { items: (string | number)[] }) => {
      const id = props.items?.[0]
      if (id != null && !String(id).startsWith('rel:')) openWhy(String(id))
    })
    tlRef.current = tl
    return () => {
      tl.destroy()
      tlRef.current = null
      itemsRef.current = null
    }
  }, [openWhy])

  // Sync items whenever the fact set or the rewind date changes.
  useEffect(() => {
    const items = itemsRef.current
    const tl = tlRef.current
    if (!items || !tl) return
    const nodes = data?.nodes ?? []
    const nowIso = todayIso()
    const next = nodes.map((n) => {
      const st = statusAt(n, asOf)
      const superseded = st === 'replaced' || n.status === 'superseded'
      const future = st === 'future'
      const group = groupFor(n)
      const isPoint = POINT_GROUPS.has(group)
      const base: any = {
        id: n.id,
        group,
        content: n.label,
        title: tooltip(n, superseded),
        className: `tl-cat-${group}` + (superseded ? ' tl-superseded' : '') + (future ? ' tl-future' : ''),
        start: n.valid_from,
      }
      if (isPoint) {
        base.type = 'point'
      } else {
        base.type = 'range'
        base.end = n.valid_to ?? nowIso // active states run to "now"
      }
      return base
    })
    items.clear()
    items.add(next)

    // Rewind cursor: a vertical marker at the as-of date.
    try {
      tl.removeCustomTime('asof')
    } catch {
      /* not set yet */
    }
    if (asOf) {
      tl.addCustomTime(parseDate(asOf), 'asof')
    }
    // Fit once we have data.
    if (nodes.length) tl.fit({ animation: false })
  }, [data, asOf])

  return <div ref={containerRef} className="tl-root h-full w-full" />
}
