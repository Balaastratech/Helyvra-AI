import { PatientPicker } from '@/components/PatientPicker'
import { SplitChat } from '@/components/SplitChat'
import { useUi } from '@/store'

/**
 * Compare page — the existing Total Recall vs Hungover AI side-by-side.
 * Demonstrates the money-shot contrast between healed and naive memory.
 */
export function ComparePage() {
  const patientId = useUi((s) => s.patientId)
  if (!patientId) return <PatientPicker />

  return (
    <div className="flex h-full min-h-0 flex-col gap-4 bg-noir-bg p-4 text-noir-text">
      <div className="shrink-0">
        <h1 className="font-cinema text-2xl tracking-wide">
          <span className="neon-magenta">Hungover AI</span>{' '}
          <span className="text-noir-muted">vs</span>{' '}
          <span className="neon-cyan">Total Recall</span>
        </h1>
        <p className="text-sm text-noir-muted">
          Same question, both assistants. The naive model repeats the outdated, dangerous
          answer; Total Recall answers from self-healed, time-aware Cognee memory.
        </p>
      </div>
      <div className="min-h-0 flex-1">
        <SplitChat />
      </div>
    </div>
  )
}
