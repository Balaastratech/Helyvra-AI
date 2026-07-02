import { UserRound, ChevronsLeft } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { usePatients, useTimeline } from '@/api/hooks'
import { useUi } from '@/store'
import { statusAt } from '@/lib/time'

export function PatientCard() {
  const { patientId, asOf, setPatient } = useUi()
  const { data: patients } = usePatients()
  const { data: timeline } = useTimeline(patientId)

  const patient = patients?.patients.find((p) => p.patient_id === patientId)
  const active = (timeline?.nodes ?? []).filter((n) => statusAt(n, asOf) === 'active')

  return (
    <Card>
      <CardContent className="pt-4">
        <div className="flex items-start gap-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-active-soft text-active ring-1 ring-active/30">
            <UserRound className="h-5 w-5" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="font-semibold text-text">{patient?.name ?? patientId}</p>
            <p className="text-xs text-text-muted">
              {patient ? `${patient.mrn} · DOB ${patient.dob} · ${patient.sex}` : 'Synthetic record'}
            </p>
          </div>
          <button
            onClick={() => setPatient(null)}
            className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-text-muted hover:bg-white/5 hover:text-text"
            title="Switch patient"
          >
            <ChevronsLeft className="h-3.5 w-3.5" /> Charts
          </button>
        </div>

        <div className="mt-3 border-t border-border pt-3">
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-text-muted">
            Current facts{asOf ? ` · as of ${asOf}` : ''}
          </p>
          {active.length === 0 ? (
            <p className="text-sm text-text-muted">
              Nothing in memory yet. Ingest records below to begin.
            </p>
          ) : (
            <ul className="space-y-1.5">
              {active.map((n) => (
                <li key={n.id} className="flex items-center justify-between gap-2">
                  <span className="text-sm text-text">{n.label}</span>
                  <Badge variant="active">Active</Badge>
                </li>
              ))}
            </ul>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
