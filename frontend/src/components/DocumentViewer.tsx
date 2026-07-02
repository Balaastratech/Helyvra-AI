import { useEffect, useMemo, useRef } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { X, FileText, AlertTriangle } from 'lucide-react'
import { useDocument } from '@/api/hooks'
import { useUi } from '@/store'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

/**
 * Read the original source file a fact came from (provenance you can see).
 * When a citation carries a page (§6), we split the doc text on the `Page N`
 * markers the PDF fixtures print, land on that page, and ring-highlight it.
 */
export function DocumentViewer() {
  const { docId, docPage, closeDoc } = useUi()
  const { data, isLoading } = useDocument(docId)
  const open = !!docId
  const citedRef = useRef<HTMLDivElement>(null)

  // Esc closes the viewer (a11y §9).
  useEffect(() => {
    if (!open) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') closeDoc()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, closeDoc])

  // Split the doc into page chunks at "Page N" markers so a cited page can be
  // isolated + highlighted. Docs without such markers stay as one chunk.
  const chunks = useMemo(() => {
    const text = data?.text ?? ''
    const parts = text.split(/(?=Page\s+\d+)/g).filter((s) => s.trim().length > 0)
    return parts.length > 0 ? parts : [text]
  }, [data?.text])

  function chunkPage(chunk: string): number | null {
    const m = chunk.match(/^\s*Page\s+(\d+)/)
    return m ? Number(m[1]) : null
  }

  // Land on the cited page when the doc (and page) resolve.
  useEffect(() => {
    if (!open || docPage == null || isLoading) return
    const t = setTimeout(() => citedRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 120)
    return () => clearTimeout(t)
  }, [open, docPage, isLoading, data?.doc_id])

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="fixed inset-0 z-40 bg-black/50"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={closeDoc}
          />
          <motion.aside
            className="fixed right-0 top-0 z-50 flex h-full w-[440px] max-w-[94vw] flex-col border-l border-border bg-surface shadow-2xl"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 28, stiffness: 280 }}
            role="dialog"
            aria-label="Source document"
          >
            <header className="flex items-center justify-between border-b border-border px-4 py-3">
              <span className="flex items-center gap-2 text-sm font-semibold text-text">
                <FileText className="h-4 w-4 text-active" /> Source record
              </span>
              <button onClick={closeDoc} className="rounded-lg p-1 text-text-muted hover:bg-white/5" aria-label="Close">
                <X className="h-5 w-5" />
              </button>
            </header>

            <div className="flex-1 space-y-3 overflow-y-auto p-4">
              {isLoading || !data ? (
                <p className="text-sm text-text-muted">Loading record…</p>
              ) : (
                <>
                  <div>
                    <h2 className="text-lg font-semibold text-text">{data.title}</h2>
                    <p className="text-xs text-text-muted">
                      {data.date} · {data.type} · {data.author} · {data.doc_id}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {docPage != null && (
                      <Badge variant="active">
                        <FileText className="h-3 w-3" /> Cited: page {docPage}
                      </Badge>
                    )}
                    {data.entered_in_error && (
                      <Badge variant="stale">
                        <AlertTriangle className="h-3 w-3" /> filed in error
                      </Badge>
                    )}
                  </div>
                  <div className="space-y-2">
                    {chunks.map((chunk, i) => {
                      const cited = docPage != null && chunkPage(chunk) === docPage
                      return (
                        <div
                          key={i}
                          ref={cited ? citedRef : undefined}
                          className={cn(
                            'rounded-xl border bg-raised p-3 transition-colors',
                            cited ? 'border-active ring-2 ring-active/40' : 'border-border',
                          )}
                        >
                          <p className="whitespace-pre-wrap text-sm leading-relaxed text-text">{chunk}</p>
                        </div>
                      )
                    })}
                  </div>
                  <p className="text-xs text-text-muted">
                    {data.ingested ? 'This record is in the AI’s memory.' : 'Not yet ingested.'}
                  </p>
                </>
              )}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  )
}
