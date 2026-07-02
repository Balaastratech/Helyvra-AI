import { useEffect, useState } from 'react'
import { Users, ShieldCheck, ShieldAlert } from 'lucide-react'
import { api } from '@/api/client'
import type { FamilyLink } from '@/api/types'

/** The consent gate, made visible. Auto-detected family links; toggling consent
 * is what lets the hereditary check reveal a relative's real diagnosis. */
export function FamilyPanel({ patientId }: { patientId: string }) {
  const [links, setLinks] = useState<FamilyLink[]>([])
  useEffect(() => {
    api.family(patientId).then((r) => setLinks(r.links)).catch(() => setLinks([]))
  }, [patientId])
  if (links.length === 0) return null

  async function toggle(l: FamilyLink) {
    await api.setFamilyConsent({ patient_id: l.patient_id, relative_id: l.relative_id, consent: !l.consent })
    setLinks((prev) => prev.map((x) => (x.relative_id === l.relative_id ? { ...x, consent: !x.consent } : x)))
  }

  return (
    <div className="rounded-xl border border-border bg-surface p-3">
      <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-text-muted">
        <Users className="h-3.5 w-3.5" /> Family (auto-linked)
      </div>
      <ul className="mt-2 space-y-1.5">
        {links.map((l) => (
          <li key={l.relative_id} className="flex items-center justify-between gap-2 text-xs">
            <span className="text-text">
              {l.relation} · <span className="text-text-muted">{l.relative_id}</span>
              {l.proposed && <span className="ml-1 text-amber-500">(proposed)</span>}
            </span>
            <button
              onClick={() => toggle(l)}
              className={l.consent
                ? 'inline-flex items-center gap-1 rounded-full border border-active/40 bg-active-soft px-2 py-0.5 text-active'
                : 'inline-flex items-center gap-1 rounded-full border border-border px-2 py-0.5 text-text-muted'}
              title="Consent controls whether hereditary checks may read this relative's records"
            >
              {l.consent ? <ShieldCheck className="h-3 w-3" /> : <ShieldAlert className="h-3 w-3" />}
              {l.consent ? 'consented' : 'no consent'}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
