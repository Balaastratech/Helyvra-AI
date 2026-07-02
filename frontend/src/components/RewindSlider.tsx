import { useMemo, type CSSProperties } from 'react'
import { History } from 'lucide-react'
import { useTimeline } from '@/api/hooks'
import { useUi } from '@/store'
import { DAY, isoOf, parseDate, todayIso } from '@/lib/time'

/**
 * Real-time rewind. Dragging fires onChange continuously; MemoryGraph recomputes
 * fact status client-side, so the graph morphs live as you drag (no per-tick fetch).
 */
export function RewindSlider() {
  const { patientId, asOf, setAsOf } = useUi()
  const { data } = useTimeline(patientId)

  const { minDate, totalDays } = useMemo(() => {
    const froms = (data?.nodes ?? []).map((n) => parseDate(n.valid_from).getTime())
    const today = parseDate(todayIso()).getTime()
    const min = froms.length ? Math.min(...froms) : today
    return { minDate: min, totalDays: Math.max(0, Math.round((today - min) / DAY)) }
  }, [data])

  const disabled = totalDays === 0
  const selected = asOf ? Math.round((parseDate(asOf).getTime() - minDate) / DAY) : totalDays
  const clamped = Math.min(Math.max(selected, 0), totalDays)
  const fill = totalDays ? (clamped / totalDays) * 100 : 100

  function onChange(idx: number) {
    if (idx >= totalDays) setAsOf(null)
    else setAsOf(isoOf(new Date(minDate + idx * DAY)))
  }

  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <div className="mb-1 flex items-center justify-between">
        <span className="flex items-center gap-1.5 text-sm font-medium text-text">
          <History className="h-4 w-4 text-active" /> Rewind time
        </span>
        <span className="rounded-full bg-active-soft px-2 py-0.5 text-xs font-semibold text-active">
          {asOf ?? 'now'}
        </span>
      </div>
      <p className="mb-2 text-xs text-text-muted">
        Drag to see what the AI knew on any date.
      </p>
      <input
        type="range"
        className="rewind w-full"
        style={{ ['--fill' as keyof CSSProperties]: `${fill}%` } as CSSProperties}
        min={0}
        max={Math.max(totalDays, 1)}
        value={clamped}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-label="Rewind time — choose a date"
      />
      <div className="mt-1 flex justify-between text-[11px] text-text-muted">
        <span>{disabled ? '—' : isoOf(new Date(minDate))}</span>
        <span>now</span>
      </div>
    </div>
  )
}
