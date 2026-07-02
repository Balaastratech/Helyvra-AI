import { useMemo, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueries } from '@tanstack/react-query'
import { Search, UserRound, ChevronRight, AlertOctagon, Loader2, Upload } from 'lucide-react'
import { usePatients } from '@/api/hooks'
import { api } from '@/api/client'
import { useUi } from '@/store'
import { DropZone } from '@/components/DropZone'
import { Skeleton } from '@/components/ui/Skeleton'
import type { BriefResponse, PatientMatch } from '@/api/types'

export function Dashboard() {
  const doctor = useUi((s) => s.doctor)
  const setPatient = useUi((s) => s.setPatient)
  const navigate = useNavigate()
  const { data: patientsData, isLoading } = usePatients()
  const patients = patientsData?.patients ?? []

  // brief per patient powers the risk pips + the cross-patient critical strip.
  const briefs = useQueries({
    queries: patients.map((p) => ({
      queryKey: ['brief', p.patient_id],
      queryFn: () => api.brief(p.patient_id),
      staleTime: 10_000,
    })),
  })
  const briefById = useMemo(() => {
    const m: Record<string, BriefResponse> = {}
    patients.forEach((p, i) => {
      const d = briefs[i]?.data as BriefResponse | undefined
      if (d) m[p.patient_id] = d
    })
    return m
  }, [patients, briefs])

  const critical = patients.filter((p) => {
    const b = briefById[p.patient_id]
    return b?.cards?.some((c) => c.indicator === 'critical')
  })

  function open(id: string) {
    setPatient(id)
    navigate(`/patient/${id}`)
  }

  // --- resolver / disambiguation (§3.4) ---
  const [query, setQuery] = useState('')
  const [matches, setMatches] = useState<PatientMatch[] | null>(null)
  const [resolving, setResolving] = useState(false)

  async function onResolve(e: FormEvent) {
    e.preventDefault()
    if (!query.trim()) return
    setResolving(true)
    try {
      const res = await api.resolve(query.trim(), doctor?.doctor_id)
      if (res.resolved) {
        open(res.resolved.patient_id)
      } else {
        setMatches(res.candidates)
      }
    } finally {
      setResolving(false)
    }
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl space-y-6 p-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-text">
            Good day{doctor ? `, ${doctor.name.replace(/^Dr\.?\s*/, 'Dr. ')}` : ''}
          </h1>
          <p className="text-sm text-text-muted">Resolve a patient, review today’s charts, or file a new record.</p>
        </div>

        {/* Resolver */}
        <form onSubmit={onResolve} className="rounded-xl border border-border bg-surface p-3 elev-1">
          <div className="flex items-center gap-2">
            <Search className="h-4 w-4 text-text-faint" />
            <input
              value={query}
              onChange={(e) => { setQuery(e.target.value); setMatches(null) }}
              placeholder="Find a patient by name or MRN…"
              className="h-9 flex-1 bg-transparent text-sm text-text outline-none placeholder:text-text-faint"
              aria-label="Resolve patient"
            />
            <button type="submit" disabled={resolving || !query.trim()} className="rounded-lg bg-active px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-40">
              {resolving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : 'Resolve'}
            </button>
          </div>
          {matches && (
            <div className="mt-3 border-t border-border pt-3">
              {matches.length === 0 ? (
                <p className="text-xs text-text-muted">No patients match “{query}”.</p>
              ) : (
                <>
                  <p className="mb-2 text-xs font-medium text-text-muted">
                    {matches.length > 1 ? `${matches.length} matches — select the patient:` : 'Match found:'}
                  </p>
                  <ul className="space-y-1.5">
                    {matches.map((m) => (
                      <li key={m.patient_id}>
                        <button
                          onClick={() => open(m.patient_id)}
                          className="flex w-full items-center gap-3 rounded-lg border border-border bg-raised px-3 py-2 text-left text-sm hover:border-active/50"
                        >
                          <span className="font-medium text-text">{m.name}</span>
                          <span className="text-xs text-text-muted">{m.age != null ? `${m.age}` : ''}{m.sex}</span>
                          <span className="tabular text-xs text-text-faint">{m.mrn}</span>
                          {m.last_visit && <span className="tabular ml-auto text-xs text-text-faint">last visit {m.last_visit}</span>}
                        </button>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          )}
        </form>

        {/* Critical reminders strip */}
        {critical.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 rounded-xl border border-critical/30 bg-critical-soft p-3">
            <span className="flex items-center gap-1.5 text-sm font-semibold text-critical">
              <AlertOctagon className="h-4 w-4" /> {critical.length} patient{critical.length > 1 ? 's' : ''} with critical flags
            </span>
            {critical.map((p) => (
              <button key={p.patient_id} onClick={() => open(p.patient_id)} className="rounded-full border border-critical/40 bg-surface px-2.5 py-0.5 text-xs font-medium text-critical hover:bg-critical-soft">
                {p.name}
              </button>
            ))}
          </div>
        )}

        {/* Today's patients */}
        <section>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-muted">Patients</h2>
          {isLoading ? (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="flex items-start gap-3 rounded-xl border border-border bg-surface p-4 elev-1">
                  <Skeleton className="h-10 w-10 rounded-full" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-4 w-1/2" />
                    <Skeleton className="h-3 w-full" />
                    <Skeleton className="h-3 w-2/3" />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {patients.map((p) => {
                const b = briefById[p.patient_id]
                const nCrit = b?.cards?.filter((c) => c.indicator === 'critical').length ?? 0
                const nWarn = b?.cards?.filter((c) => c.indicator === 'warning').length ?? 0
                return (
                  <button
                    key={p.patient_id}
                    onClick={() => open(p.patient_id)}
                    className="group flex items-start gap-3 rounded-xl border border-border bg-surface p-4 text-left elev-1 transition-colors hover:border-active/50"
                  >
                    <span className="grid h-10 w-10 place-items-center rounded-full bg-active-soft text-active">
                      <UserRound className="h-5 w-5" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5">
                        <p className="truncate font-medium text-text">{p.name}</p>
                        <span className="tabular text-[10px] text-text-faint">{p.mrn}</span>
                      </div>
                      <p className="mt-0.5 line-clamp-2 text-xs text-text-muted">{p.summary}</p>
                      {(nCrit > 0 || nWarn > 0) && (
                        <div className="mt-1.5 flex items-center gap-1.5">
                          {nCrit > 0 && <span className="h-2 w-2 rounded-full bg-critical" title={`${nCrit} critical`} />}
                          {nWarn > 0 && <span className="h-2 w-2 rounded-full bg-warning" title={`${nWarn} warning${nWarn > 1 ? 's' : ''}`} />}
                          <span className="text-[10px] text-text-faint">{nCrit + nWarn} open flag{nCrit + nWarn > 1 ? 's' : ''}</span>
                        </div>
                      )}
                    </div>
                    <ChevronRight className="h-5 w-5 shrink-0 text-text-faint group-hover:text-active" />
                  </button>
                )
              })}
            </div>
          )}
        </section>

        {/* Upload dropbox */}
        <section>
          <h2 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-text-muted">
            <Upload className="h-3.5 w-3.5" /> File a record
          </h2>
          <DropZone />
          <p className="mt-2 text-xs text-text-faint">
            Drop a PDF, FHIR bundle, CSV, or note — the system detects the patient (or creates a new chart) and files it.
          </p>
        </section>
      </div>
    </div>
  )
}
