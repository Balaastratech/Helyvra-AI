import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { ClipboardList, MessageSquare, Network, GitCompare, ArrowUpRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useUi } from '@/store'
import { useBrief } from '@/api/hooks'
import { PreVisitBrief } from '@/components/clinical/PreVisitBrief'
import { ClinicalCard } from '@/components/clinical/ClinicalCard'
import { ChatPane } from '@/components/ChatPane'
import { PatientTimeline } from '@/components/PatientTimeline'
import { RewindSlider } from '@/components/RewindSlider'
import { SplitChat } from '@/components/SplitChat'
import { DropZone } from '@/components/DropZone'
import { cn } from '@/lib/utils'

type Tab = 'brief' | 'consult' | 'timeline' | 'compare'

const TABS: { key: Tab; label: string; icon: typeof ClipboardList }[] = [
  { key: 'brief', label: 'Pre-visit brief', icon: ClipboardList },
  { key: 'consult', label: 'Consult', icon: MessageSquare },
  { key: 'timeline', label: 'Timeline', icon: Network },
  { key: 'compare', label: 'Compare', icon: GitCompare },
]

export function PatientWorkspace() {
  const { id } = useParams<{ id: string }>()
  const { patientId, setPatient } = useUi()
  const [tab, setTab] = useState<Tab>('brief')

  // Lock the patient context to the route (safety: one patient per workspace).
  useEffect(() => {
    if (id && id !== patientId) setPatient(id)
  }, [id, patientId, setPatient])

  const { data: brief } = useBrief(id ?? null)
  const cards = brief?.cards ?? []

  if (!id) return null

  return (
    <div className="flex h-full min-h-0">
      {/* Left: tabs + active panel */}
      <div className="flex min-h-0 flex-1 flex-col">
        <div role="tablist" aria-label="Patient views" className="flex items-center gap-1 border-b border-border bg-surface px-3">
          {TABS.map((t) => (
            <button
              key={t.key}
              role="tab"
              aria-selected={tab === t.key}
              onClick={() => setTab(t.key)}
              className={cn(
                'flex items-center gap-1.5 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors',
                tab === t.key
                  ? 'border-active text-active'
                  : 'border-transparent text-text-muted hover:text-text',
              )}
            >
              <t.icon className="h-4 w-4" /> {t.label}
            </button>
          ))}
        </div>

        <div className="min-h-0 flex-1 overflow-hidden">
          {tab === 'brief' && (
            <div className="h-full overflow-y-auto">
              <PreVisitBrief patientId={id} />
            </div>
          )}
          {tab === 'consult' && <ChatPane />}
          {tab === 'timeline' && (
            <div className="flex h-full flex-col gap-3 overflow-y-auto p-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-text">Memory timeline</h2>
                <Link to="/memory" className="flex items-center gap-1 text-xs text-active hover:underline">
                  Relationship map <ArrowUpRight className="h-3 w-3" />
                </Link>
              </div>
              <div className="shrink-0 overflow-hidden rounded-xl border border-border bg-surface">
                <PatientTimeline />
              </div>
              <RewindSlider />
              <p className="text-xs text-text-muted">
                Bars are long-running states; dots are events and short episodes; lab values
                plot as trends below. Drag the blue playhead (or the slider) to rewind —
                facts the AI didn&apos;t know yet fade, replaced facts grey out, retained not deleted.
                Click anything for “why it changed”.
              </p>
            </div>
          )}
          {tab === 'compare' && (
            <div className="h-full min-h-0 p-4">
              <SplitChat />
            </div>
          )}
        </div>
      </div>

      {/* Right rail: doctor-might-miss cards (persistent on non-brief tabs; the
          Brief tab already surfaces these cards in its own layout). */}
      {tab !== 'brief' && (
        <aside className="flex w-[340px] shrink-0 flex-col border-l border-border bg-raised">
          <div className="border-b border-border px-4 py-3">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              Doctor might miss
            </h2>
          </div>
          <div className="min-h-0 flex-1 space-y-2.5 overflow-y-auto p-3">
            {cards.length === 0 ? (
              <p className="rounded-lg border border-border bg-surface p-3 text-xs text-text-muted">
                No open flags yet. Upload this patient’s records to build the brief.
              </p>
            ) : (
              cards.map((c) => <ClinicalCard key={c.check_id} card={c} compact />)
            )}
          </div>
          <div className="border-t border-border p-3">
            <DropZone />
          </div>
        </aside>
      )}
    </div>
  )
}
