import { useEffect } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { X, BrainCircuit, ArrowRight, FileText } from 'lucide-react'
import { useWhy } from '@/api/hooks'
import { useUi } from '@/store'
import { Badge } from '@/components/ui/badge'
import { plainStatus } from '@/lib/labels'

export function WhyPanel() {
  const { whyFactId, closeWhy, openDoc } = useUi()
  const { data, isLoading } = useWhy(whyFactId)
  const open = !!whyFactId

  // Esc closes the panel (a11y §9).
  useEffect(() => {
    if (!open) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') closeWhy()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, closeWhy])

  // One plain sentence (design-brief): "X was cleared on DATE by SOURCE, so the earlier record no longer applies."
  // A repeated measurement (e.g. a lab value) never supersedes the last one —
  // each reading is independently true — so that case gets its own sentence
  // instead of the misleading "nothing has replaced it".
  const sentence =
    data && data.superseded_by
      ? `${data.superseded_by.label} on ${data.date} (${data.source}), so the earlier record no longer applies.`
      : data && data.trend.length > 1
        ? `No single record replaced another — this has been measured ${data.trend.length} times. Each reading stands on its own.`
        : data
          ? `${data.fact.label} — still current; nothing has replaced it.`
          : ''

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="fixed inset-0 z-40 bg-black/50"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={closeWhy}
          />
          <motion.aside
            className="fixed right-0 top-0 z-50 flex h-full w-[400px] max-w-[92vw] flex-col border-l border-border bg-surface shadow-2xl"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 28, stiffness: 280 }}
            role="dialog"
            aria-label="Why did this change?"
          >
            <header className="flex items-center justify-between border-b border-border px-4 py-3">
              <h2 className="text-lg font-semibold text-text">Why did this change?</h2>
              <button onClick={closeWhy} className="rounded-lg p-1 text-text-muted hover:bg-white/5" aria-label="Close">
                <X className="h-5 w-5" />
              </button>
            </header>

            <div className="flex-1 space-y-4 overflow-y-auto p-4">
              {isLoading || !data ? (
                <p className="text-sm text-text-muted">Loading the story…</p>
              ) : (
                <>
                  <p className="rounded-xl border border-active/20 bg-active-soft p-3 text-sm leading-relaxed text-text">
                    {sentence}
                  </p>

                  <section>
                    <p className="text-xs font-medium uppercase tracking-wide text-text-muted">This fact</p>
                    <p className="mt-0.5 text-sm text-text">{data.fact.label}</p>
                    <div className="mt-1">
                      <Badge variant={data.fact.status === 'active' ? 'active' : 'replaced'}>
                        {plainStatus(data.fact.status)}
                      </Badge>
                    </div>
                    {data.fact.source_document && (
                      <button
                        onClick={() => openDoc(data.fact.source_document as string)}
                        className="mt-2 flex items-center gap-1.5 text-xs text-active hover:underline"
                      >
                        <FileText className="h-3.5 w-3.5" />
                        View source record{data.fact.document_title ? `: ${data.fact.document_title}` : ''}
                      </button>
                    )}
                  </section>

                  {data.chain.length > 1 && (
                    <section>
                      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-text-muted">
                        What happened
                      </p>
                      <ol className="space-y-2">
                        {data.chain.map((c, i) => (
                          <li key={c.id} className="flex items-center gap-2 text-sm">
                            {i > 0 && <ArrowRight className="h-3.5 w-3.5 shrink-0 text-text-muted" />}
                            <span className="rounded-lg bg-white/5 px-2 py-1 text-text">{c.label}</span>
                            <span className="text-xs text-text-muted">{c.valid_from}</span>
                          </li>
                        ))}
                      </ol>
                    </section>
                  )}

                  {data.trend.length > 1 && (
                    <section>
                      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-text-muted">
                        Readings over time
                      </p>
                      <ol className="space-y-2">
                        {data.trend.map((c, i) => (
                          <li key={c.id} className="flex items-center gap-2 text-sm">
                            {i > 0 && <ArrowRight className="h-3.5 w-3.5 shrink-0 text-text-muted" />}
                            <span
                              className={
                                c.id === data.fact.id
                                  ? 'rounded-lg bg-active-soft px-2 py-1 font-medium text-text'
                                  : 'rounded-lg bg-white/5 px-2 py-1 text-text'
                              }
                            >
                              {c.label}
                            </span>
                            <span className="text-xs text-text-muted">{c.valid_from}</span>
                          </li>
                        ))}
                      </ol>
                    </section>
                  )}

                  <section className="flex items-start gap-2 rounded-xl border border-active/20 bg-active-soft p-3">
                    <BrainCircuit className="mt-0.5 h-4 w-4 shrink-0 text-active" />
                    <p className="text-xs text-text-muted">
                      The AI&apos;s own memory agrees — this is the reconciled truth, not a guess.
                    </p>
                  </section>
                </>
              )}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  )
}
