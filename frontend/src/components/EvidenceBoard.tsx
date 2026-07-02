import { FileText } from 'lucide-react'
import { useTimeline } from '@/api/hooks'
import { useUi } from '@/store'
import { statusAt } from '@/lib/time'
import { cn } from '@/lib/utils'
import type { GraphNode } from '@/api/types'

const ROT = [-2.5, 2, -1.5, 2.5, -2, 1.5]

/**
 * The Board — an evidence wall built from the authoritative ledger: each record
 * is a pinned polaroid, grouped by topic, with a red "replaced by" string down
 * each chain. Every card links to its source file. (Reliable; doesn't depend on
 * Cognee's internal graph.)
 */
export function EvidenceBoard() {
  const { patientId, openDoc, openWhy } = useUi()
  const { data } = useTimeline(patientId)
  const nodes = data?.nodes ?? []

  const groups = new Map<string, GraphNode[]>()
  for (const n of nodes) {
    const g = groups.get(n.subject) ?? []
    g.push(n)
    groups.set(n.subject, g)
  }
  for (const g of groups.values()) g.sort((a, b) => a.valid_from.localeCompare(b.valid_from))

  if (nodes.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-noir-text/80">
        Ingest this patient&apos;s records to build the board.
      </div>
    )
  }

  return (
    <div className="flex h-full flex-wrap content-start gap-x-10 gap-y-8 overflow-auto p-8">
      {[...groups.entries()].map(([subject, facts]) => (
        <div key={subject} className="flex flex-col items-center gap-1">
          <span className="mb-1 rounded-full bg-black/40 px-3 py-0.5 font-display text-sm uppercase tracking-widest text-amber-200">
            {subject}
          </span>
          {facts.map((n, i) => {
            const replaced = statusAt(n, null) === 'replaced'
            return (
              <div key={n.id} className="flex flex-col items-center">
                {i > 0 && <div className="h-6 w-0.5 bg-[#e11d48]" />}
                <button
                  onClick={() => (n.source_document ? openDoc(n.source_document) : openWhy(n.id))}
                  style={{ rotate: `${ROT[i % ROT.length]}deg` }}
                  className={cn(
                    'relative w-48 rounded-sm bg-[#f4f1ea] p-2 pb-6 text-left shadow-xl ring-1 ring-black/30 transition-transform hover:z-10 hover:scale-105',
                    replaced && 'opacity-80 grayscale',
                  )}
                >
                  <img src="/theme/pushpin.png" alt="" aria-hidden className="absolute -top-3 left-1/2 z-10 h-6 w-6 -translate-x-1/2 drop-shadow" />
                  <div className="flex min-h-16 flex-col justify-center rounded-sm bg-white px-2 py-2 text-center">
                    <p className="text-sm font-semibold leading-tight text-slate-900">{n.label}</p>
                  </div>
                  <p className="mt-1.5 flex items-center gap-1 px-1 text-[10px] text-slate-500">
                    <FileText className="h-2.5 w-2.5" /> {n.valid_from} · {n.source}
                  </p>
                  {replaced && (
                    <img src="/theme/stamp-redacted.png" alt="replaced" className="pointer-events-none absolute inset-x-3 top-5 z-10" />
                  )}
                </button>
              </div>
            )
          })}
        </div>
      ))}
    </div>
  )
}
