import { useEffect, useMemo, useRef, useState } from 'react'
import { Timeline, type TimelineOptions } from 'vis-timeline/standalone'
import { DataSet } from 'vis-data'
import 'vis-timeline/styles/vis-timeline-graph2d.css'
import { useTimeline } from '@/api/hooks'
import { useUi } from '@/store'
import { statusAt, todayIso, parseDate, isoOf, DAY } from '@/lib/time'
import type { GraphNode } from '@/api/types'

/**
 * Patient timeline v2 — playhead edition.
 *
 * The rewind cursor is a DRAGGABLE PLAYHEAD on the chart itself (vis-timeline
 * custom time bar): drag it and facts to its right dim ("not yet known"),
 * superseded facts grey + stamp, all live with no refetch. The detached slider
 * still works — both write the same `asOf` store field.
 *
 * No-overlap guarantees:
 *  - short episodes (< 90 days) render as labeled POINTS, never slivers with
 *    clipped text; long states render as bars with room for their label
 *  - labs leave the swimlanes entirely → the LabTrends panel below, one lane
 *    per analyte, sharing the same time window (focus+context, always in sync)
 *  - empty category lanes are dropped
 */

const GROUPS: { id: string; label: string }[] = [
  { id: 'Allergy', label: 'Allergies' },
  { id: 'Condition', label: 'Conditions' },
  { id: 'Medication', label: 'Medications' },
  { id: 'Vital', label: 'Vitals' },
  { id: 'Family', label: 'Family' },
  { id: 'Lifestyle', label: 'Lifestyle' },
  { id: 'Other', label: 'Other' },
]
const GROUP_IDS = new Set(GROUPS.map((g) => g.id))
const SHORT_RANGE_DAYS = 90 // below this a state renders as a labeled point

function groupFor(n: GraphNode): string {
  if (n.kind === 'relative') return 'Family'
  const c = n.category ?? 'Other'
  return GROUP_IDS.has(c) ? c : 'Other'
}

const isLab = (n: GraphNode) => (n.category ?? '') === 'LabResult'

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

/** Current view geometry — lets buildItems know when a label won't fit on the
 *  right and must flip to the left of its bar/dot (nothing ever clips). */
type View = { start: number; end: number; centerW: number }

const CHAR_PX = 6.3 // ≈ px per character at the 11px item font

function buildItems(nodes: GraphNode[], asOf: string | null, nowIso: string, view: View | null) {
  const span = view ? Math.max(1, view.end - view.start) : 1
  const px = (t: number) => (view ? ((t - view.start) / span) * view.centerW : 0)
  return nodes
    .filter((n) => !isLab(n))
    .map((n) => {
      const st = statusAt(n, asOf)
      // statusAt is authoritative for the rewound date: a fact superseded TODAY
      // was still active back then, and must render active when rewound.
      const superseded = st === 'replaced'
      const future = st === 'future'
      const group = groupFor(n)
      const from = parseDate(n.valid_from).getTime()
      const to = parseDate(n.valid_to ?? nowIso).getTime()
      const isPointFact = group === 'Vital' || group === 'Family' || !n.valid_to && to - from < DAY
      const shortEpisode = n.valid_to != null && to - from < SHORT_RANGE_DAYS * DAY
      const point = isPointFact || shortEpisode
      // Would the label clip at the right edge of the visible panel? Then flip it left.
      let edge = false
      if (view) {
        const labelPx = n.label.length * CHAR_PX + 18
        const rightPx = point ? px(from) + labelPx : px(from) + Math.max(px(to) - px(from), labelPx)
        edge = rightPx > view.centerW - 6
      }
      const base: any = {
        id: n.id,
        group,
        content: n.label,
        title: tooltip(n, superseded),
        className:
          `tl-cat-${group}` +
          (superseded ? ' tl-superseded' : '') +
          (future ? ' tl-future' : '') +
          (edge ? ' tl-edge' : ''),
        start: n.valid_from,
      }
      if (point) {
        base.type = 'point'
      } else {
        base.type = 'range'
        base.end = n.valid_to ?? nowIso
      }
      return base
    })
}

/* ------------------------- Lab trends (synced) --------------------------- */

const ANALYTE_NAMES: Record<string, string> = {
  hba1c: 'HbA1c', ldl: 'LDL', hdl: 'HDL', creatinine: 'Creatinine',
  glucose: 'Glucose', tsh: 'TSH', egfr: 'eGFR',
}

function analyteOf(n: GraphNode): string {
  const key = (n.subject ?? '').replace(/^lab\s+/, '').trim()
  return ANALYTE_NAMES[key] ?? (key ? key.charAt(0).toUpperCase() + key.slice(1) : 'Lab')
}

function numOf(n: GraphNode): number | null {
  // Last number wins: "HbA1c 8.6 %" must parse 8.6, not the 1 inside "A1c".
  const m = (n.value ?? n.label).match(/\d+(?:\.\d+)?/g)
  return m?.length ? parseFloat(m[m.length - 1]) : null
}

const LANE = 56

function LabTrends({
  nodes, win, leftPad, asOf,
}: {
  nodes: GraphNode[]
  win: { start: number; end: number }
  leftPad: number
  asOf: string | null
}) {
  const { openWhy } = useUi()

  const series = useMemo(() => {
    const by = new Map<string, { name: string; pts: { n: GraphNode; t: number; v: number }[] }>()
    for (const n of nodes.filter(isLab)) {
      const v = numOf(n)
      if (v === null) continue
      const name = analyteOf(n)
      if (!by.has(name)) by.set(name, { name, pts: [] })
      by.get(name)!.pts.push({ n, t: parseDate(n.valid_from).getTime(), v })
    }
    const out = [...by.values()]
    out.forEach((s) => s.pts.sort((a, b) => a.t - b.t))
    return out.sort((a, b) => a.name.localeCompare(b.name))
  }, [nodes])

  if (!series.length) return null
  const atTime = parseDate(asOf ?? todayIso()).getTime()
  const span = Math.max(1, win.end - win.start)
  // Percent along the plot area — no pixel measurement, always in sync.
  const pct = (t: number) => ((t - win.start) / span) * 100
  const phPct = pct(Math.min(atTime + DAY, win.end))

  return (
    <div className="border-t border-border">
      {series.map((s) => {
        const vs = s.pts.map((p) => p.v)
        const lo = Math.min(...vs), hi = Math.max(...vs)
        const y = (v: number) => (hi === lo ? LANE / 2 + 8 : 22 + ((hi - v) / (hi - lo)) * (LANE - 34))
        return (
          <div key={s.name} className="flex border-b border-border/50 last:border-b-0">
            <div
              className="flex shrink-0 items-center px-2.5 text-[11px] font-semibold text-text-muted"
              style={{ width: leftPad, height: LANE }}
            >
              {s.name}
            </div>
            <div className="relative min-w-0 flex-1 overflow-hidden" style={{ height: LANE }}>
              {s.pts.length > 1 && (
                <svg
                  className="absolute inset-0 h-full w-full"
                  viewBox={`0 0 100 ${LANE}`}
                  preserveAspectRatio="none"
                  aria-hidden="true"
                >
                  <polyline
                    points={s.pts.map((p) => `${pct(p.t)},${y(p.v)}`).join(' ')}
                    fill="none" stroke="#c77700" strokeWidth="1.5" opacity="0.7"
                    vectorEffect="non-scaling-stroke"
                  />
                </svg>
              )}
              {s.pts.map((p) => {
                const px = pct(p.t)
                if (px < 0 || px > 100) return null
                const dim = p.t > atTime
                return (
                  <button
                    key={p.n.id}
                    onClick={() => openWhy(p.n.id)}
                    title={`${p.n.label} — ${p.n.valid_from}`}
                    className="absolute -translate-x-1/2 text-center transition-opacity"
                    style={{ left: `${px}%`, top: y(p.v) - 16, opacity: dim ? 0.18 : 1 }}
                  >
                    <span className="block text-[10px] leading-3 text-text">{p.v}</span>
                    <span
                      className="mx-auto mt-0.5 block h-2.5 w-2.5 rounded-full border-2 border-white"
                      style={{ background: '#c77700' }}
                    />
                  </button>
                )
              })}
              {phPct >= 0 && phPct <= 100 && (
                <span
                  className="absolute top-0 h-full w-[1.5px] bg-active opacity-60"
                  style={{ left: `${phPct}%` }}
                />
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

/* ------------------------------ Timeline --------------------------------- */

export function PatientTimeline() {
  const { patientId, asOf, setAsOf, openWhy } = useUi()
  const { data } = useTimeline(patientId)
  const containerRef = useRef<HTMLDivElement>(null)
  const tlRef = useRef<Timeline | null>(null)
  const itemsRef = useRef<DataSet<any> | null>(null)
  const groupsRef = useRef<DataSet<any> | null>(null)
  const draggingRef = useRef(false)
  const loadedRef = useRef<string | null>(null)
  const viewRef = useRef<View | null>(null)
  const [win, setWin] = useState<{ start: number; end: number }>(() => {
    const now = parseDate(todayIso()).getTime()
    return { start: now - 365 * DAY, end: now }
  })
  const [leftPad, setLeftPad] = useState(110)

  // Build the timeline once the container exists.
  useEffect(() => {
    if (!containerRef.current || tlRef.current) return
    const items = new DataSet<any>([])
    const groups = new DataSet<any>([])
    itemsRef.current = items
    groupsRef.current = groups
    const options: TimelineOptions = {
      stack: true,
      editable: false,
      selectable: true,
      zoomKey: 'ctrlKey',
      zoomMin: 1000 * 60 * 60 * 24 * 30,
      orientation: { axis: 'top', item: 'top' },
      margin: { item: { horizontal: 8, vertical: 6 }, axis: 8 },
      groupOrder: (a: any, b: any) =>
        GROUPS.findIndex((g) => g.id === a.id) - GROUPS.findIndex((g) => g.id === b.id),
      tooltip: { followMouse: true, overflowMethod: 'flip' },
      showCurrentTime: false,
    }
    const tl = new Timeline(containerRef.current, items, groups, options)
    tl.on('select', (props: { items: (string | number)[] }) => {
      const id = props.items?.[0]
      if (id != null && !String(id).startsWith('rel:')) openWhy(String(id))
    })
    // The playhead — draggable "as of" cursor on the chart itself.
    tl.addCustomTime(parseDate(todayIso()), 'asof')
    ;(tl as any).setCustomTimeMarker('now', 'asof', false) // in runtime, missing from the standalone types
    tl.on('timechange', (ev: { id: string; time: Date }) => {
      if (ev.id !== 'asof') return
      draggingRef.current = true
      const today = parseDate(todayIso()).getTime()
      const t = Math.min(ev.time.getTime(), today)
      setAsOf(t >= today ? null : isoOf(new Date(t)))
    })
    tl.on('timechanged', (ev: { id: string; time: Date }) => {
      if (ev.id !== 'asof') return
      draggingRef.current = false
      const today = parseDate(todayIso()).getTime()
      if (ev.time.getTime() >= today) {
        tl.setCustomTime(parseDate(todayIso()), 'asof') // clamp to now
        setAsOf(null)
      }
    })
    const syncWindow = () => {
      const w = tl.getWindow()
      const left = containerRef.current?.querySelector('.vis-panel.vis-left') as HTMLElement | null
      const center = containerRef.current?.querySelector('.vis-panel.vis-center') as HTMLElement | null
      viewRef.current = {
        start: w.start.getTime(),
        end: w.end.getTime(),
        centerW: center?.clientWidth ?? 800,
      }
      setWin({ start: w.start.getTime(), end: w.end.getTime() })
      if (left) setLeftPad(left.offsetWidth)
    }
    tl.on('rangechange', syncWindow)
    tl.on('changed', syncWindow)
    tlRef.current = tl
    return () => {
      tl.destroy()
      tlRef.current = null
      itemsRef.current = null
      groupsRef.current = null
    }
  }, [openWhy, setAsOf])

  // Full rebuild when the fact set changes (patient switch / new data).
  useEffect(() => {
    const items = itemsRef.current
    const groups = groupsRef.current
    const tl = tlRef.current
    if (!items || !groups || !tl) return
    const nodes = data?.nodes ?? []
    const nowIso = todayIso()
    const built = buildItems(nodes, asOf, nowIso, viewRef.current)
    const used = new Set(built.map((i) => i.group))
    groups.clear()
    groups.add(GROUPS.filter((g) => used.has(g.id)).map((g) => ({ id: g.id, content: g.label })))
    items.clear()
    items.add(built)
    // Fit to data once per patient/data load — never during a drag.
    const key = `${patientId}:${nodes.length}`
    if (nodes.length && loadedRef.current !== key) {
      loadedRef.current = key
      fitAll()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, patientId])

  // Light update when the rewind date or the visible window moves: reclass
  // items (superseded / future / edge-flip) + playhead. Cheap: ~20 items.
  useEffect(() => {
    const items = itemsRef.current
    const tl = tlRef.current
    if (!items || !tl) return
    const nodes = data?.nodes ?? []
    if (nodes.length) items.update(buildItems(nodes, asOf, todayIso(), viewRef.current))
    const at = parseDate(asOf ?? todayIso())
    if (!draggingRef.current) {
      try { tl.setCustomTime(at, 'asof') } catch { /* not mounted yet */ }
    }
    try { (tl as any).setCustomTimeMarker(asOf ?? 'now', 'asof', false) } catch { /* ignore */ }
    // "Not yet known" backdrop from the playhead to the right edge.
    const endPad = parseDate(todayIso()).getTime() + 60 * DAY
    items.update({
      id: '__future',
      type: 'background',
      className: 'tl-notyet',
      start: asOf ? at : new Date(endPad),
      end: new Date(endPad),
      content: '',
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [asOf, data, win])

  function fitAll() {
    const tl = tlRef.current
    const nodes = data?.nodes ?? []
    if (!tl) return
    const today = parseDate(todayIso()).getTime()
    const froms = nodes.map((n) => parseDate(n.valid_from).getTime())
    const min = froms.length ? Math.min(...froms) : today - 365 * DAY
    const pad = Math.max(45 * DAY, (today - min) * 0.05)
    // extra right pad: labels of items at "now" need room to breathe
    tl.setWindow(new Date(min - pad), new Date(today + pad * 2), { animation: false })
  }

  function setSpan(days: number) {
    const tl = tlRef.current
    if (!tl) return
    const today = parseDate(todayIso()).getTime()
    tl.setWindow(new Date(today - days * DAY), new Date(today + 14 * DAY), { animation: false })
  }

  const nodes = data?.nodes ?? []
  return (
    <div className="flex flex-col">
      <div className="flex items-center justify-end gap-1 border-b border-border px-2 py-1.5">
        <span className="mr-auto pl-2 text-[11px] text-text-muted">
          Drag the blue playhead to rewind — facts to its right fade out.
        </span>
        {([['Fit all', 0], ['1 year', 365], ['90 days', 90]] as const).map(([label, days]) => (
          <button
            key={label}
            onClick={() => (days === 0 ? fitAll() : setSpan(days))}
            className="rounded-md border border-border px-2 py-0.5 text-[11px] text-text-muted transition-colors hover:border-active/50 hover:text-text"
          >
            {label}
          </button>
        ))}
      </div>
      <div ref={containerRef} className="tl-root" />
      <LabTrends nodes={nodes} win={win} leftPad={leftPad} asOf={asOf} />
    </div>
  )
}
