import { useEffect } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { X, Database, Zap, MessageSquare } from 'lucide-react'
import { useUi } from '@/store'

const STEPS = [
  { icon: Database, title: '1 · Open a chart', body: 'Pick a patient and review their source records.' },
  { icon: Zap, title: '2 · Ingest the records', body: 'Add documents to memory — later records correct earlier ones automatically.' },
  { icon: MessageSquare, title: '3 · Ask the same question', body: 'Ask both assistants. Helyvra stays correct; Hungover AI repeats the outdated, dangerous answer.' },
]

export function HowItWorks() {
  const { howOpen, setHowOpen } = useUi()
  const reduced = useReducedMotion()

  // Esc closes; keeps focus management honest for a modal dialog (a11y §9).
  useEffect(() => {
    if (!howOpen) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setHowOpen(false)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [howOpen, setHowOpen])

  return (
    <AnimatePresence>
      {howOpen && (
        <motion.div
          className="fixed inset-0 z-[70] grid place-items-center bg-black/60 p-4"
          initial={reduced ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={() => setHowOpen(false)}
          role="dialog"
          aria-modal="true"
          aria-label="How it works"
        >
          <motion.div
            className="w-full max-w-lg rounded-2xl border border-border bg-surface p-6 shadow-2xl"
            initial={reduced ? false : { scale: 0.95, y: 10 }}
            animate={{ scale: 1, y: 0 }}
            exit={reduced ? undefined : { scale: 0.95, opacity: 0 }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-start justify-between">
              <div>
                <h2 className="text-xl font-semibold text-text">An AI that fixes its own memory</h2>
                <p className="mt-1 text-sm text-text-muted">
                  When records change, most AIs keep repeating the old answer. Helyvra detects
                  the change, updates its memory, and can explain why — and even rewind time.
                </p>
              </div>
              <button onClick={() => setHowOpen(false)} className="rounded-lg p-1 text-text-muted hover:bg-white/5" aria-label="Close">
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-3">
              {STEPS.map((s) => (
                <div key={s.title} className="flex items-start gap-3 rounded-xl border border-border bg-raised p-3">
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-active-soft text-active">
                    <s.icon className="h-5 w-5" />
                  </span>
                  <div>
                    <p className="text-sm font-medium text-text">{s.title}</p>
                    <p className="text-sm text-text-muted">{s.body}</p>
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
