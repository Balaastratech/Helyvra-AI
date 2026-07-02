import { FilmTransition } from '@/components/cinematic/FilmTransition'
import { EvidenceBoard } from '@/components/EvidenceBoard'
import { PatientPicker } from '@/components/PatientPicker'
import { useUi } from '@/store'

export function BoardPage() {
  const patientId = useUi((s) => s.patientId)
  if (!patientId) return <PatientPicker />

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 p-4">
      <FilmTransition trigger="board" variant="warm" />
      <div>
        <h1 className="font-display text-2xl tracking-wide text-text">The Board</h1>
        <p className="text-sm text-text-muted">
          The investigation wall — every record pinned, grouped by topic, with a red string where
          one record replaced another. Click a card to read the original file.
        </p>
      </div>
      <div
        className="min-h-0 flex-1 overflow-hidden rounded-xl border border-white/10 bg-noir-bg bg-cover bg-center"
        style={{ backgroundImage: 'url(/theme/board-cork.png)' }}
      >
        <EvidenceBoard />
      </div>
    </div>
  )
}
