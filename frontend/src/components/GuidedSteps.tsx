import { Check } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useUi, nextStep, type StepKey } from '@/store'
import { cn } from '@/lib/utils'

const STEPS: { key: StepKey; title: string; caption: string }[] = [
  { key: 'loaded', title: 'Ingest records', caption: "Add the patient's documents to memory." },
  { key: 'added', title: 'Watch it self-correct', caption: 'A later record replaces an earlier one automatically.' },
  { key: 'asked', title: 'Ask the question', caption: 'Ask both assistants — see who stays correct.' },
]

export function GuidedSteps() {
  const steps = useUi((s) => s.steps)
  const next = nextStep(steps)

  return (
    <Card>
      <CardHeader>
        <CardTitle>Guided demo</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {STEPS.map((s, i) => {
          const done = steps[s.key]
          const active = next === s.key
          return (
            <div
              key={s.key}
              className={cn(
                'flex items-start gap-3 rounded-lg border p-2.5 transition-colors',
                done && 'border-active/30 bg-active-soft',
                active && 'border-active/40 bg-white/5',
                !done && !active && 'border-border opacity-60',
              )}
            >
              <span
                className={cn(
                  'mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full text-xs font-semibold',
                  done
                    ? 'bg-active text-[#04121a]'
                    : active
                      ? 'bg-active/20 text-active animate-pulse-ring'
                      : 'bg-white/10 text-text-muted',
                )}
              >
                {done ? <Check className="h-3.5 w-3.5" /> : i + 1}
              </span>
              <div className="min-w-0">
                <p className={cn('text-sm font-medium', done ? 'text-active' : 'text-text')}>
                  {s.title}
                </p>
                <p className="text-xs text-text-muted">{s.caption}</p>
              </div>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}
