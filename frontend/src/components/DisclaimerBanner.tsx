import { AlertTriangle } from 'lucide-react'

/** Amber, always-serious disclaimer (never themed away). */
export function DisclaimerBanner() {
  return (
    <div
      role="note"
      className="flex items-center justify-center gap-2 border-b border-amber-400/20 bg-amber-400/10 px-4 py-1.5 text-xs font-medium text-amber-300"
    >
      <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden />
      <span>Demo only · synthetic data · not medical advice</span>
    </div>
  )
}
