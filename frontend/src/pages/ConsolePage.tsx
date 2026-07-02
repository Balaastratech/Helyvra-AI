import { Link } from 'react-router-dom'
import { ArrowUpRight } from 'lucide-react'
import { PatientPicker } from '@/components/PatientPicker'
import { PatientCard } from '@/components/PatientCard'
import { GuidedSteps } from '@/components/GuidedSteps'
import { RecordsInbox } from '@/components/RecordsInbox'
import { SplitChat } from '@/components/SplitChat'
import { MemoryGraph } from '@/components/MemoryGraph'
import { RewindSlider } from '@/components/RewindSlider'
import { useUi } from '@/store'

export function ConsolePage() {
  const patientId = useUi((s) => s.patientId)
  if (!patientId) return <PatientPicker />

  return (
    <div className="grid h-full min-h-0 grid-cols-[320px_minmax(0,1fr)_minmax(0,440px)] gap-4 p-4">
      <aside className="flex min-h-0 flex-col gap-4 overflow-y-auto pr-1">
        <PatientCard />
        <GuidedSteps />
        <RecordsInbox />
      </aside>

      <section className="min-h-0">
        <SplitChat />
      </section>

      <aside className="flex min-h-0 flex-col gap-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-text">Memory map</h2>
          <Link to="/memory" className="flex items-center gap-1 text-xs text-active hover:underline">
            Full map <ArrowUpRight className="h-3 w-3" />
          </Link>
        </div>
        <div className="min-h-0 flex-1 overflow-hidden rounded-xl border border-border bg-surface">
          <MemoryGraph />
        </div>
        <RewindSlider />
        <p className="text-xs text-text-muted">
          Each dot is a fact. A dashed red arrow means “replaced by”. Click a dot to see why it
          changed.
        </p>
      </aside>
    </div>
  )
}
