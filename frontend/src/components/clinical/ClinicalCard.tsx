import { AlertTriangle, AlertOctagon, Info, FileText } from 'lucide-react'
import type { ClinicalCardData, Indicator } from '@/api/types'
import { useUi } from '@/store'
import { cn } from '@/lib/utils'

/**
 * A CDS-Hooks-modeled clinical card (§5.2) — severity-coded, always cited,
 * calm not alarming. Color is never the only signal: icon + label + color
 * together (a11y + clinical safety, UX §1.4).
 */
const STYLE: Record<Indicator, { ring: string; bar: string; text: string; icon: typeof Info; word: string }> = {
  critical: { ring: 'border-critical/30 bg-critical-soft', bar: 'bg-critical', text: 'text-critical', icon: AlertOctagon, word: 'Critical' },
  warning: { ring: 'border-warning/30 bg-warning-soft', bar: 'bg-warning', text: 'text-warning', icon: AlertTriangle, word: 'Review' },
  info: { ring: 'border-info/30 bg-info-soft', bar: 'bg-info', text: 'text-info', icon: Info, word: 'Note' },
}

export function ClinicalCard({ card, compact = false }: { card: ClinicalCardData; compact?: boolean }) {
  const openDoc = useUi((s) => s.openDoc)
  const openWhy = useUi((s) => s.openWhy)
  const s = STYLE[card.indicator] ?? STYLE.info
  const Icon = s.icon

  return (
    <article
      className={cn(
        'relative overflow-hidden rounded-xl border bg-surface elev-1',
        s.ring,
        card.indicator === 'critical' && 'animate-severity-pulse',
      )}
    >
      <span className={cn('absolute inset-y-0 left-0 w-1', s.bar)} aria-hidden />
      <div className="p-3.5 pl-4">
        <div className="flex items-start gap-2">
          <Icon className={cn('mt-0.5 h-4 w-4 shrink-0', s.text)} aria-hidden />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className={cn('text-[10px] font-semibold uppercase tracking-wide', s.text)}>
                {s.word}
              </span>
            </div>
            <h4 className="mt-0.5 text-sm font-semibold text-text">{card.summary}</h4>
            {!compact && card.detail && (
              <p className="mt-1 text-xs leading-relaxed text-text-muted">{card.detail}</p>
            )}

            {card.source.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {card.source.map((c, i) => (
                  <button
                    key={`${c.fact_id}-${i}`}
                    onClick={() => (c.source_document ? openDoc(c.source_document, c.page) : c.fact_id && openWhy(c.fact_id))}
                    title={c.source_document ? 'Open source document' : 'Show provenance'}
                    className="inline-flex items-center gap-1 rounded-full border border-border bg-surface px-2 py-0.5 text-[10px] font-medium text-text-muted hover:border-active/50 hover:text-active"
                  >
                    <FileText className="h-2.5 w-2.5" />
                    <span className="max-w-[16rem] truncate">
                      {c.label}
                      {c.page ? ` · p.${c.page}` : ''}
                      {c.date ? <span className="tabular"> · {c.date}</span> : null}
                    </span>
                  </button>
                ))}
              </div>
            )}

            {!compact && card.suggestions.length > 0 && (
              <ul className="mt-2 space-y-0.5">
                {card.suggestions.map((sg, i) => (
                  <li key={i} className="flex items-start gap-1.5 text-xs text-text-muted">
                    <span className={cn('mt-1.5 h-1 w-1 shrink-0 rounded-full', s.bar)} aria-hidden />
                    {sg}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </article>
  )
}
