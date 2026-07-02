import { UserRound, ShieldAlert, Activity } from 'lucide-react'
import type { Patient } from '@/api/types'

/**
 * The locked patient-context chip (UX §2 "patient context is sacred"): name ·
 * age · sex · MRN + allergy/risk badges, always visible inside a patient so a
 * mix-up is impossible.
 */
export function PatientContextChip({
  patient,
  age,
  allergyBadge,
  riskBadge,
  settle = false,
}: {
  patient: Patient
  age?: number | null
  allergyBadge?: string | null
  riskBadge?: boolean
  settle?: boolean
}) {
  return (
    <div
      className={[
        'flex items-center gap-2.5 rounded-full border border-border bg-surface py-1 pl-1.5 pr-3 elev-1',
        settle ? 'animate-chip-settle' : '',
      ].join(' ')}
    >
      <span className="grid h-7 w-7 place-items-center rounded-full bg-active-soft text-active">
        <UserRound className="h-4 w-4" />
      </span>
      <span className="text-sm font-semibold text-text">{patient.name}</span>
      <span className="text-xs text-text-muted">
        {age != null ? `${age}` : ''}{patient.sex ? patient.sex : ''}
      </span>
      <span className="tabular text-xs text-text-faint">{patient.mrn}</span>

      {allergyBadge && (
        <span className="inline-flex items-center gap-1 rounded-full bg-critical-soft px-2 py-0.5 text-[10px] font-semibold text-critical" title={`Active allergy: ${allergyBadge}`}>
          <ShieldAlert className="h-3 w-3" /> {allergyBadge}
        </span>
      )}
      {riskBadge && (
        <span className="inline-flex items-center gap-1 rounded-full bg-warning-soft px-2 py-0.5 text-[10px] font-semibold text-warning" title="Open risk flags">
          <Activity className="h-3 w-3" /> risk
        </span>
      )}
    </div>
  )
}
