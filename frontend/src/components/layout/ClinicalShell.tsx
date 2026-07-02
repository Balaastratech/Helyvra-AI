import { Navigate, Outlet, useNavigate, NavLink } from 'react-router-dom'
import { Stethoscope, Circle, HelpCircle, LogOut, Home, Search, GitCompare, Network, LayoutGrid } from 'lucide-react'
import { useHealth, useBrief } from '@/api/hooks'
import { useUi } from '@/store'
import { PatientContextChip } from '@/components/clinical/PatientContextChip'
import { DisclaimerBanner } from '@/components/DisclaimerBanner'
import { WhyPanel } from '@/components/WhyPanel'
import { DocumentViewer } from '@/components/DocumentViewer'
import { HowItWorks } from '@/components/HowItWorks'
import { CommandPalette } from '@/components/CommandPalette'
import { cn } from '@/lib/utils'

/**
 * The light clinical chrome for the whole doctor workspace (UX §2). Slim top
 * bar: wordmark · patient-context chip (when in a patient) · clinician · health.
 * Noir lives only at the framed edges (cold-open, Compare), not here.
 */
export function ClinicalShell() {
  const { doctor, patientId, setPatient, setDoctor, setHowOpen, setCmdkOpen } = useUi()
  const { data: health } = useHealth()
  const { data: brief } = useBrief(patientId)
  const navigate = useNavigate()

  if (!doctor) return <Navigate to="/login" replace />
  const ok = health?.ok

  return (
    <div className="flex h-screen flex-col bg-bg text-text">
      <header className="flex items-center justify-between gap-4 border-b border-border bg-surface px-5 py-2.5">
        <div className="flex items-center gap-3">
          <button
            onClick={() => { setPatient(null); navigate('/') }}
            className="flex items-center gap-2"
            title="Dashboard"
          >
            <span className="grid h-7 w-7 place-items-center rounded-lg bg-active text-white">
              <Stethoscope className="h-4 w-4" />
            </span>
            <span className="text-sm font-semibold tracking-tight text-text">Total Recall</span>
          </button>
          {patientId && brief && (
            <>
              <button
                onClick={() => { setPatient(null); navigate('/') }}
                className="ml-1 flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-text-muted hover:bg-raised hover:text-text"
                title="Close patient — back to dashboard"
              >
                <Home className="h-3.5 w-3.5" />
              </button>
              <PatientContextChip
                patient={brief.patient}
                age={brief.age}
                allergyBadge={brief.allergy_badge}
                riskBadge={brief.risk_badge}
              />
            </>
          )}
          <nav className="ml-2 hidden items-center gap-0.5 md:flex">
            {[
              { to: '/compare', label: 'Compare', icon: GitCompare },
              { to: '/memory', label: 'Memory Map', icon: Network },
              { to: '/board', label: 'Cognee graph', icon: LayoutGrid },
            ].map((v) => (
              <NavLink
                key={v.to}
                to={v.to}
                className={({ isActive }) =>
                  cn('flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium transition-colors',
                    isActive ? 'bg-active-soft text-active' : 'text-text-muted hover:bg-raised hover:text-text')
                }
              >
                <v.icon className="h-3.5 w-3.5" /> {v.label}
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setCmdkOpen(true)}
            className="hidden items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-xs text-text-muted hover:text-text sm:flex"
            title="Command palette"
          >
            <Search className="h-3.5 w-3.5" />
            <kbd className="tabular text-[10px]">⌘K</kbd>
          </button>
          <button
            onClick={() => setHowOpen(true)}
            className="flex items-center gap-1.5 rounded-full border border-border px-3 py-1 text-xs text-text-muted hover:text-text"
          >
            <HelpCircle className="h-3.5 w-3.5" /> How it works
          </button>
          <span
            className="flex items-center gap-1.5 text-xs text-text-muted"
            title={`memory: ${health?.cognee ?? '?'} · records: ${health?.ledger ?? '?'}`}
          >
            <Circle className={cn('h-2.5 w-2.5 fill-current', ok ? 'text-success' : 'text-warning')} />
            {ok ? 'systems up' : 'connecting…'}
          </span>
          <div className="flex items-center gap-2 border-l border-border pl-3">
            <div className="text-right">
              <p className="text-xs font-medium leading-tight text-text">{doctor.name}</p>
              <p className="text-[10px] capitalize leading-tight text-text-faint">{doctor.specialty}</p>
            </div>
            <button
              onClick={() => { setDoctor(null); navigate('/login') }}
              className="rounded-lg p-1.5 text-text-muted hover:bg-raised hover:text-text"
              title="Sign out"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </header>

      <DisclaimerBanner />
      <main className="min-h-0 flex-1 overflow-hidden">
        <Outlet />
      </main>

      <WhyPanel />
      <DocumentViewer />
      <HowItWorks />
      <CommandPalette />
    </div>
  )
}
