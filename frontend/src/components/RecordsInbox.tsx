import { useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { toast } from 'sonner'
import { FileText, Check, Loader2, Trash2, Download, AlertTriangle, RotateCcw, Upload } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { api } from '@/api/client'
import { useDocuments, useIngestDocument, useInvalidateGraphs } from '@/api/hooks'
import { useUi } from '@/store'
import { cn } from '@/lib/utils'
import type { DocumentSummary } from '@/api/types'

export function RecordsInbox() {
  const { patientId, openDoc, markStep } = useUi()
  const invalidate = useInvalidateGraphs()
  const { data } = useDocuments(patientId)
  const ingestM = useIngestDocument()
  const [busyId, setBusyId] = useState<string | null>(null)
  const [bulk, setBulk] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)

  const docs = data?.documents ?? []

  async function uploadFiles(files: FileList | null) {
    if (!files || files.length === 0 || !patientId) return
    setUploading(true)
    for (const file of Array.from(files)) {
      try {
        const res = await api.upload(patientId, file)
        markStep('loaded')
        if (res.healed) {
          markStep('added')
          toast('The AI read your file and updated itself', {
            description: `${res.facts[0]?.label ?? file.name} — the earlier answer was replaced.`,
            className: 'shadow-[0_0_18px_rgba(255,45,149,0.35)]',
          })
        } else {
          toast.success('File added to memory', {
            description: res.facts[0]?.label ?? file.name,
          })
        }
      } catch (e) {
        toast.error(`Couldn't read ${file.name}`, { description: (e as Error).message })
      }
    }
    setUploading(false)
    invalidate()
  }

  async function ingestOne(doc: DocumentSummary) {
    setBusyId(doc.doc_id)
    try {
      const res = await ingestM.mutateAsync({ patient_id: patientId!, doc_id: doc.doc_id })
      markStep('loaded')
      if (res.healed) {
        markStep('added')
        toast('The AI updated itself', {
          description: `${res.facts[0]?.label ?? 'A record'} — the earlier answer was replaced.`,
          className: 'shadow-[0_0_18px_rgba(255,45,149,0.35)]',
        })
      } else {
        toast.success('Record added to memory', { description: res.facts[0]?.label ?? doc.title })
      }
    } catch (e) {
      toast.error("Couldn't ingest record", { description: (e as Error).message })
    } finally {
      setBusyId(null)
      invalidate()
    }
  }

  async function ingestAll() {
    setBulk(true)
    for (const d of docs) {
      if (!d.ingested) await ingestOne(d)
    }
    setBulk(false)
  }

  const forgetM = useMutation({
    mutationFn: (factId: string) =>
      api.forget({ patient_id: patientId!, fact_id: factId, reason: 'entered in error' }),
    onSuccess: (res) => {
      invalidate()
      toast.success('Removed from memory', { description: `${res.fact.label} (entered in error).` })
      if (res.restored) toast.message('Earlier fact restored', { description: res.restored.label })
    },
    onError: (e: Error) => toast.error("Couldn't remove entry", { description: e.message }),
  })

  const remaining = docs.filter((d) => !d.ingested).length
  const busy = bulk || busyId !== null || forgetM.isPending || uploading

  const resetM = useMutation({
    mutationFn: () => api.reset({ patient_id: patientId! }),
    onSuccess: () => {
      invalidate()
      toast.success('Memory cleared', { description: 'All charts reset — ingest records to start over.' })
    },
    onError: (e: Error) => toast.error('Reset failed', { description: e.message }),
  })

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Records inbox</CardTitle>
        {remaining > 0 && (
          <Button size="sm" onClick={ingestAll} disabled={busy} className={cn(remaining === docs.length && 'animate-pulse-ring')}>
            <Download className="h-3.5 w-3.5" /> Ingest all ({remaining})
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="text-xs text-text-muted">
          The patient&apos;s source documents. Ingest them to build memory — later records
          automatically correct earlier ones.
        </p>

        <input
          ref={fileInput}
          type="file"
          accept=".txt,.md,.json,text/plain,application/json"
          multiple
          className="hidden"
          onChange={(e) => {
            void uploadFiles(e.target.files)
            e.target.value = ''
          }}
        />
        <div
          onClick={() => !busy && fileInput.current?.click()}
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragging(false)
            void uploadFiles(e.dataTransfer.files)
          }}
          className={cn(
            'flex cursor-pointer flex-col items-center gap-1 rounded-xl border border-dashed p-4 text-center transition-colors',
            dragging ? 'border-active bg-active-soft' : 'border-border hover:border-active/40',
            busy && 'pointer-events-none opacity-60',
          )}
        >
          {uploading ? (
            <Loader2 className="h-5 w-5 animate-spin text-active" />
          ) : (
            <Upload className="h-5 w-5 text-active" />
          )}
          <p className="text-sm font-medium text-text">Upload a record</p>
          <p className="text-[11px] text-text-muted">
            Drop a .txt / .md / .json clinical note, or click to browse. The AI reads it and updates
            memory.
          </p>
        </div>
        {docs.length === 0 && <p className="text-sm text-text-muted">No records on file.</p>}
        {docs.map((d) => (
          <div
            key={d.doc_id}
            className={cn(
              'rounded-lg border p-2.5',
              d.ingested ? 'border-active/25 bg-active-soft' : 'border-border bg-raised',
            )}
          >
            <div className="flex items-start gap-2">
              <FileText className="mt-0.5 h-4 w-4 shrink-0 text-text-muted" />
              <div className="min-w-0 flex-1">
                <button
                  onClick={() => openDoc(d.doc_id)}
                  className="text-left text-sm font-medium text-text hover:text-active hover:underline"
                >
                  {d.title}
                </button>
                <p className="text-[11px] text-text-muted">
                  {d.date} · {d.type} · {d.author}
                </p>
                {d.entered_in_error && (
                  <span className="mt-1 inline-flex items-center gap-1 text-[11px] text-amber-400">
                    <AlertTriangle className="h-3 w-3" /> flagged: filed in error
                  </span>
                )}
              </div>
              {d.ingested ? (
                <Badge variant="active">
                  <Check className="h-3 w-3" /> in memory
                </Badge>
              ) : (
                <Button size="sm" variant="outline" onClick={() => ingestOne(d)} disabled={busy}>
                  {busyId === d.doc_id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : 'Ingest'}
                </Button>
              )}
            </div>
            {d.ingested && d.fact_id && (
              <div className="mt-2 flex justify-end">
                <button
                  onClick={() => forgetM.mutate(d.fact_id!)}
                  disabled={busy}
                  className="flex items-center gap-1 text-[11px] text-text-muted hover:text-danger"
                  title="Delete this fact — entered in error"
                >
                  <Trash2 className="h-3 w-3" /> Remove (entered in error)
                </button>
              </div>
            )}
          </div>
        ))}
        <button
          onClick={() => resetM.mutate()}
          disabled={busy || resetM.isPending}
          className="mt-1 flex items-center gap-1 text-[11px] text-text-muted hover:text-danger disabled:opacity-40"
        >
          <RotateCcw className="h-3 w-3" /> Reset all memory
        </button>
      </CardContent>
    </Card>
  )
}
