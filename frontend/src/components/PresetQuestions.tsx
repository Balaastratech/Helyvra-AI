import { Button } from '@/components/ui/button'

export interface Preset {
  question: string
  /** if set, also rewinds the timeline to this date (time-travel question). */
  asOf?: string
}

export const PRESETS: Preset[] = [
  { question: 'Is the patient allergic to penicillin?' },
  { question: 'What blood-pressure medicine is the patient on now?' },
  { question: 'Was the patient allergic to penicillin back in February?', asOf: '2026-02-15' },
]

export function PresetQuestions({
  onPick,
  disabled,
}: {
  onPick: (p: Preset) => void
  disabled?: boolean
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {PRESETS.map((p) => (
        <Button
          key={p.question}
          variant="outline"
          size="sm"
          className="rounded-full"
          disabled={disabled}
          onClick={() => onPick(p)}
        >
          {p.question}
        </Button>
      ))}
    </div>
  )
}
