import { useState } from 'react'
import { UserRound, ChevronRight, Loader2, UserPlus } from 'lucide-react'
import { usePatients, useCreatePatient } from '@/api/hooks'
import { useUi } from '@/store'
import { Button } from '@/components/ui/button'

/** Landing: choose a chart, or create your own and bring your own records. */
export function PatientPicker() {
  const { data, isLoading, error } = usePatients()
  const setPatient = useUi((s) => s.setPatient)
  const createM = useCreatePatient()
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [dob, setDob] = useState('')
  const [sex, setSex] = useState('')

  async function create() {
    if (!name.trim()) return
    const p = await createM.mutateAsync({ name, dob, sex })
    setPatient(p.patient_id)
  }

  return (
    <div className="mx-auto flex h-full max-w-2xl flex-col justify-center gap-4 overflow-y-auto p-6">
      <div>
        <h1 className="font-display text-3xl tracking-wide text-text">Select a patient chart</h1>
        <p className="text-sm text-text-muted">
          Open a chart to review its records, build the AI&apos;s memory, and ask questions — or
          create a new chart and upload your own records.
        </p>
      </div>

      {isLoading && (
        <p className="flex items-center gap-2 text-sm text-text-muted">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading charts…
        </p>
      )}
      {error && (
        <p className="text-sm text-danger">Couldn&apos;t reach the records service. Is the backend running?</p>
      )}

      <ul className="space-y-2">
        {(data?.patients ?? []).map((p) => (
          <li key={p.patient_id}>
            <button
              onClick={() => setPatient(p.patient_id)}
              className="flex w-full items-center gap-4 rounded-xl border border-border bg-surface p-4 text-left transition-colors hover:border-active/40 hover:bg-white/5"
            >
              <span className="grid h-11 w-11 place-items-center rounded-full bg-active-soft text-active ring-1 ring-active/30">
                <UserRound className="h-5 w-5" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="font-medium text-text">{p.name}</p>
                <p className="text-xs text-text-muted">
                  {p.mrn}
                  {p.dob ? ` · DOB ${p.dob}` : ''}
                  {p.sex ? ` · ${p.sex}` : ''} — {p.summary}
                </p>
              </div>
              <ChevronRight className="h-5 w-5 text-text-muted" />
            </button>
          </li>
        ))}
      </ul>

      {open ? (
        <div className="space-y-3 rounded-xl border border-active/30 bg-surface p-4">
          <p className="text-sm font-medium text-text">New patient chart</p>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Patient name *"
            className="h-10 w-full rounded-lg border border-border bg-raised px-3 text-sm text-text outline-none focus:ring-2 focus:ring-active"
          />
          <div className="flex gap-2">
            <input
              value={dob}
              onChange={(e) => setDob(e.target.value)}
              placeholder="DOB (YYYY-MM-DD)"
              className="h-10 flex-1 rounded-lg border border-border bg-raised px-3 text-sm text-text outline-none focus:ring-2 focus:ring-active"
            />
            <input
              value={sex}
              onChange={(e) => setSex(e.target.value)}
              placeholder="Sex"
              className="h-10 w-24 rounded-lg border border-border bg-raised px-3 text-sm text-text outline-none focus:ring-2 focus:ring-active"
            />
          </div>
          <div className="flex gap-2">
            <Button onClick={create} disabled={!name.trim() || createM.isPending}>
              {createM.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserPlus className="h-4 w-4" />}
              Create &amp; open
            </Button>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
          </div>
          <p className="text-xs text-text-muted">
            After creating, drop your own clinical notes (.txt / .md / .json) into the chart&apos;s
            Records inbox.
          </p>
        </div>
      ) : (
        <Button variant="outline" className="self-start" onClick={() => setOpen(true)}>
          <UserPlus className="h-4 w-4" /> New patient (bring your own records)
        </Button>
      )}
    </div>
  )
}
