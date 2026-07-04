import { useState, useCallback, type DragEvent } from 'react'
import { Upload, FileText, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'
import { useUi } from '@/store'
import { cn } from '@/lib/utils'
import type { IntakeResponse } from '@/api/types'

type Status = 'idle' | 'dragover' | 'uploading' | 'success' | 'error'

export function DropZone() {
  const { patientId, setPatient } = useUi()
  const queryClient = useQueryClient()
  const [status, setStatus] = useState<Status>('idle')
  const [message, setMessage] = useState('')
  const [lines, setLines] = useState<string[]>([])

  const handleDragOver = useCallback((e: DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setStatus('dragover')
  }, [])

  const handleDragLeave = useCallback((e: DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setStatus('idle')
  }, [])

  const handleDrop = useCallback(async (e: DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    const files = Array.from(e.dataTransfer.files)
    if (files.length === 0) { setStatus('idle'); return }
    await uploadFiles(files)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [patientId])

  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return
    await uploadFiles(Array.from(files))
    e.target.value = '' // reset so the same files can be re-uploaded
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [patientId])

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['patients'] })
    queryClient.invalidateQueries({ queryKey: ['documents'] })
    queryClient.invalidateQueries({ queryKey: ['graph'] })
    queryClient.invalidateQueries({ queryKey: ['brief'] })
  }

  async function uploadFiles(files: File[]) {
    setStatus('uploading')
    setLines([])

    // Single file: the plain endpoint (unchanged, simplest path).
    if (files.length === 1) {
      const file = files[0]
      setMessage(`Uploading ${file.name}…`)
      try {
        const res: IntakeResponse = await api.intake(file, patientId || undefined)
        if (!patientId && res.patient_id) setPatient(res.patient_id)
        invalidate()
        const extra = res.created_patient ? ' · new chart' : ''
        setStatus('success')
        setMessage(`✓ ${file.name} → ${res.patient_name}${extra} · ${res.facts.length} fact(s)`)
      } catch (err: any) {
        setStatus('error')
        setMessage(`✕ ${file.name} — ${err.message}`)
      }
      setTimeout(() => { setStatus('idle'); setMessage(''); setLines([]) }, 8000)
      return
    }

    // Multiple files: ONE request for the whole drop, not one per file — the
    // backend does a single Cognee graph rebuild for the batch instead of one
    // per file (cognify's cost scales with the patient's total fact count, so
    // doing it once per file made an N-file drop take N times longer than
    // it needed to).
    setMessage(`Uploading ${files.length} files…`)
    try {
      const res = await api.intakeBatch(files, patientId || undefined)
      const ok = res.items.filter((it) => it.ok)
      const firstOk = ok.find((it) => it.patient_id)
      if (!patientId && firstOk) setPatient(firstOk.patient_id)
      const facts = ok.reduce((n, it) => n + it.facts.length, 0)
      const lines = res.items.map((it) =>
        it.ok
          ? `✓ ${it.filename} → ${it.patient_name}${it.created_patient ? ' · new chart' : ''} · ${it.facts.length} fact(s)`
          : `✕ ${it.filename} — ${it.error}`,
      )
      setLines(lines)
      invalidate()
      const failed = res.items.length - ok.length
      setStatus(failed === res.items.length ? 'error' : 'success')
      setMessage(`${ok.length}/${res.items.length} file(s) ingested · ${facts} fact(s)` + (failed ? ` · ${failed} failed` : ''))
    } catch (err: any) {
      setStatus('error')
      setMessage(`✕ Batch upload failed — ${err.message}`)
    }
    // Clear the transient banner but keep the per-file lines visible a bit longer.
    setTimeout(() => { setStatus('idle'); setMessage(''); setLines([]) }, 8000)
  }

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={cn(
        'relative rounded-xl border-2 border-dashed p-6 text-center transition-all',
        status === 'idle' && 'border-border hover:border-active/40',
        status === 'dragover' && 'border-active bg-active/5 scale-[1.01]',
        status === 'uploading' && 'border-active/50 bg-active/5',
        status === 'success' && 'border-green-500/50 bg-green-500/5',
        status === 'error' && 'border-red-500/50 bg-red-500/5',
      )}
    >
      <input
        type="file"
        multiple
        accept=".pdf,.json,.txt,.md,.csv"
        onChange={handleFileSelect}
        className="absolute inset-0 cursor-pointer opacity-0"
        aria-label="Upload clinical documents"
      />

      {status === 'idle' && (
        <div className="flex flex-col items-center gap-2">
          <Upload className="h-8 w-8 text-text-muted" />
          <p className="text-sm text-text-muted">
            Drop clinical documents here or <span className="text-active">browse</span>
          </p>
          <p className="text-xs text-text-muted/60">
            One or many · PDF, FHIR JSON, CSV, or text — patient auto-detected
          </p>
        </div>
      )}

      {status === 'dragover' && (
        <div className="flex flex-col items-center gap-2">
          <FileText className="h-8 w-8 text-active animate-pulse" />
          <p className="text-sm font-medium text-active">Drop to upload</p>
        </div>
      )}

      {status === 'uploading' && (
        <div className="flex flex-col items-center gap-2">
          <Loader2 className="h-8 w-8 animate-spin text-active" />
          <p className="text-sm text-text-muted">{message}</p>
        </div>
      )}

      {(status === 'success' || status === 'error') && (
        <div className="flex flex-col items-center gap-2">
          {status === 'success'
            ? <CheckCircle2 className="h-8 w-8 text-green-500" />
            : <AlertCircle className="h-8 w-8 text-red-500" />}
          <p className={cn('text-sm', status === 'success' ? 'text-green-600' : 'text-red-600')}>{message}</p>
        </div>
      )}

      {lines.length > 0 && (
        <ul className="mt-3 max-h-40 space-y-0.5 overflow-y-auto text-left text-xs">
          {lines.map((l, i) => (
            <li key={i} className={cn('truncate', l.startsWith('✕') ? 'text-red-600' : 'text-text-muted')}>
              {l}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
