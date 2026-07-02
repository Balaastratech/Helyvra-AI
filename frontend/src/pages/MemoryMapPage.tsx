import { MemoryGraph } from '@/components/MemoryGraph'
import { RewindSlider } from '@/components/RewindSlider'
import { Legend } from '@/components/Legend'
import { FactReel } from '@/components/FactReel'
import { PatientPicker } from '@/components/PatientPicker'
import { useUi } from '@/store'

export function MemoryMapPage() {
  const { patientId, openWhy } = useUi()
  if (!patientId) return <PatientPicker />
  return (
    <div className="grid h-full min-h-0 grid-cols-[minmax(0,1fr)_360px] gap-4 p-4">
      <div className="flex min-h-0 flex-col gap-3">
        <div>
          <h1 className="font-display text-2xl tracking-wide text-text">The Memory Map</h1>
          <p className="text-sm text-text-muted">
            Every fact the AI holds, on a timeline. Drag “Rewind time” to watch facts turn on and
            off; click a fact to see why it changed.
          </p>
        </div>
        <Legend />
        <div className="min-h-0 flex-1 overflow-hidden rounded-xl border border-border bg-surface">
          <MemoryGraph />
        </div>
        <RewindSlider />
      </div>

      <aside className="flex min-h-0 flex-col gap-3 overflow-y-auto">
        <h2 className="text-sm font-semibold text-text">The records, as photos</h2>
        <p className="text-xs text-text-muted">
          Each result is a snapshot. Rewind to develop the reel; replaced records get stamped.
        </p>
        <FactReel onCardClick={openWhy} />
      </aside>
    </div>
  )
}
