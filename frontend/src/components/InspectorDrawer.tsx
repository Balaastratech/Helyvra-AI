import { useState } from 'react'
import { ChevronRight, Activity, Database } from 'lucide-react'
import { PatientCard } from './PatientCard'
import { RecordsInbox } from './RecordsInbox'
import { GuidedSteps } from './GuidedSteps'
import { useUi } from '@/store'
import { cn } from '@/lib/utils'

/**
 * Collapsible Inspector drawer — engine internals for judges/devs.
 * Shows PatientCard, GuidedSteps, RecordsInbox (the "dev console" view).
 * Off by default, toggled by the nav or a button.
 */
export function InspectorDrawer() {
  const { patientId } = useUi()
  const [open, setOpen] = useState(false)

  if (!patientId) return null

  return (
    <div className={cn(
      'border-l border-border bg-raised/30 transition-all duration-200 overflow-hidden',
      open ? 'w-80' : 'w-10',
    )}>
      <button
        onClick={() => setOpen(!open)}
        className="flex h-10 w-full items-center justify-center border-b border-border text-text-muted hover:text-text"
        title={open ? 'Close Inspector' : 'Open Inspector'}
      >
        {open ? <ChevronRight className="h-4 w-4" /> : <Activity className="h-4 w-4" />}
      </button>

      {open && (
        <div className="flex flex-col gap-4 overflow-y-auto p-3 h-[calc(100%-40px)]">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase text-text-muted tracking-wide">
            <Database className="h-3.5 w-3.5" /> Engine Inspector
          </div>
          <PatientCard />
          <GuidedSteps />
          <RecordsInbox />
        </div>
      )}
    </div>
  )
}
