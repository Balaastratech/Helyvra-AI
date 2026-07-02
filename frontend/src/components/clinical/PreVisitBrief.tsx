import {
  Stethoscope, Pill, ShieldAlert, FlaskConical, Users, HeartPulse,
  Inbox, FileText,
} from 'lucide-react'
import type { BriefItem, BriefResponse } from '@/api/types'
import { useBrief } from '@/api/hooks'
import { ClinicalCard } from './ClinicalCard'
import { FamilyPanel } from './FamilyPanel'
import { DropZone } from '@/components/DropZone'
import { Skeleton } from '@/components/ui/Skeleton'
import { useUi } from '@/store'
import { cn } from '@/lib/utils'

const GROUPS: { key: string; label: string; icon: typeof Pill }[] = [
  { key: 'conditions', label: 'Conditions', icon: Stethoscope },
  { key: 'medications', label: 'Medications', icon: Pill },
  { key: 'allergies', label: 'Allergies', icon: ShieldAlert },
  { key: 'labs', label: 'Labs', icon: FlaskConical },
  { key: 'family', label: 'Family history', icon: Users },
  { key: 'lifestyle', label: 'Lifestyle', icon: HeartPulse },
]

function Row({ item }: { item: BriefItem }) {
  const openDoc = useUi((s) => s.openDoc)
  const openWhy = useUi((s) => s.openWhy)
  return (
    <li className="flex items-baseline justify-between gap-3 py-1">
      <button
        onClick={() => (item.source_document ? openDoc(item.source_document, item.page) : openWhy(item.fact_id))}
        className="group flex min-w-0 items-baseline gap-1.5 text-left"
      >
        <span className={cn('truncate text-text', item.status !== 'active' && 'text-text-faint line-through')}>
          {item.label}
        </span>
        {item.source_document && (
          <FileText className="h-3 w-3 shrink-0 text-text-faint opacity-0 group-hover:opacity-100" />
        )}
      </button>
      <span className="tabular shrink-0 text-xs text-text-faint">{item.date}</span>
    </li>
  )
}

export function PreVisitBrief({ patientId }: { patientId: string }) {
  const { data, isLoading, error } = useBrief(patientId)

  if (isLoading) {
    return (
      <div className="grid gap-5 p-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,380px)]">
        <div className="space-y-4">
          <Skeleton className="h-3 w-28" />
          <div className="grid gap-3 sm:grid-cols-2">
            {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-28 w-full rounded-xl" />)}
          </div>
        </div>
        <div className="space-y-3">
          <Skeleton className="h-3 w-40" />
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-24 w-full rounded-xl" />)}
        </div>
      </div>
    )
  }
  if (error || !data) {
    return (
      <div className="mx-auto max-w-md p-8 text-center">
        <p className="text-sm text-text">The brief couldn’t load just now.</p>
        <p className="mt-1 text-xs text-text-muted">
          This is a display hiccup — the patient’s records are safe. Try again in a moment.
        </p>
        <button
          onClick={() => window.location.reload()}
          className="mt-4 rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-text hover:border-active/50 hover:text-active"
        >
          Retry
        </button>
      </div>
    )
  }

  const brief = data as BriefResponse
  const empty = brief.fact_count === 0

  if (empty) {
    return (
      <div className="mx-auto max-w-2xl p-8 text-center">
        <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-full bg-raised text-text-muted">
          <Inbox className="h-6 w-6" />
        </div>
        <h3 className="text-lg font-semibold text-text">No records yet for {brief.patient.name}</h3>
        <p className="mx-auto mt-1 max-w-md text-sm text-text-muted">
          Drop this patient’s clinical documents below — discharge summaries, labs,
          FHIR bundles, notes. The chart, brief, and safety checks build themselves.
        </p>
        <div className="mx-auto mt-5 max-w-lg">
          <DropZone />
        </div>
      </div>
    )
  }

  return (
    <div className="grid gap-5 p-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,380px)]">
      {/* Summary (left) */}
      <section className="animate-brief-rise space-y-4">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-text-muted">Chart summary</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {GROUPS.map(({ key, label, icon: Icon }) => {
            const items = brief.groups[key] ?? []
            return (
              <div key={key} className="rounded-xl border border-border bg-surface p-3.5 elev-1">
                <div className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-text-muted">
                  <Icon className="h-3.5 w-3.5" /> {label}
                  <span className="ml-auto tabular text-text-faint">{items.length}</span>
                </div>
                {items.length === 0 ? (
                  <p className="text-xs text-text-faint">None on record</p>
                ) : (
                  <ul className="text-sm">
                    {items.slice(0, 6).map((it) => <Row key={it.fact_id} item={it} />)}
                  </ul>
                )}
              </div>
            )
          })}
        </div>
      </section>

      {/* Top not-to-miss (right) */}
      <section className="animate-brief-rise space-y-3" style={{ animationDelay: '120ms' }}>
        <h2 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
          Top {brief.cards.length || ''} things not to miss
        </h2>
        {brief.cards.length === 0 ? (
          <div className="rounded-xl border border-success/30 bg-success-soft p-4 text-sm text-text">
            No open safety flags from the current records.
          </div>
        ) : (
          <div className="space-y-2.5">
            {brief.cards.map((c) => <ClinicalCard key={c.check_id} card={c} />)}
          </div>
        )}
        <FamilyPanel patientId={patientId} />
      </section>
    </div>
  )
}
