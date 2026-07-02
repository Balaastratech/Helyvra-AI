import { useNavigate } from 'react-router-dom'
import { Stethoscope, Loader2, ArrowRight } from 'lucide-react'
import { useDoctors } from '@/api/hooks'
import { useUi } from '@/store'
import type { Doctor } from '@/api/types'

/** Simulated login (UX §3.2): pick a doctor — no password theater. Sets the
 * session identity that scopes access + audit. Sub-2-second, honest. */
export function LoginPage() {
  const { data: doctors, isLoading, error } = useDoctors()
  const setDoctor = useUi((s) => s.setDoctor)
  const navigate = useNavigate()

  function pick(d: Doctor) {
    setDoctor(d)
    navigate('/')
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg p-6">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-2xl bg-active text-white elev-1">
            <Stethoscope className="h-6 w-6" />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-text">Total Recall</h1>
          <p className="mt-1 text-sm text-text-muted">Clinical copilot — choose a demo clinician to continue.</p>
        </div>

        {isLoading && (
          <p className="flex items-center justify-center gap-2 text-sm text-text-muted">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading clinicians…
          </p>
        )}
        {error && <p className="text-center text-sm text-danger">Couldn’t reach the backend.</p>}

        <ul className="space-y-2">
          {(doctors ?? []).map((d) => (
            <li key={d.doctor_id}>
              <button
                onClick={() => pick(d)}
                className="group flex w-full items-center gap-3 rounded-xl border border-border bg-surface p-3.5 text-left elev-1 transition-colors hover:border-active/50"
              >
                <span className="grid h-10 w-10 place-items-center rounded-full bg-active-soft font-semibold text-active">
                  {d.name.split(' ').map((s) => s[0]).slice(-2).join('')}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-text">{d.name}</p>
                  <p className="text-xs text-text-muted">
                    {d.specialty} · <span className="capitalize">{d.role}</span>
                  </p>
                </div>
                <ArrowRight className="h-4 w-4 text-text-faint transition-transform group-hover:translate-x-0.5 group-hover:text-active" />
              </button>
            </li>
          ))}
        </ul>

        <p className="mt-6 text-center text-xs text-text-faint">
          Demo login · synthetic data · not medical advice
        </p>
      </div>
    </div>
  )
}
