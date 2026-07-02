import type { StructuredAnswer } from '@/api/types'

/**
 * The six-part clinical answer contract (§5.3): Answer · Reason · Evidence ·
 * Confidence · What's missing · Suggested action. Rendered calmly — never a
 * confident single line; missing data is named, not hidden.
 */
const ROWS: { key: keyof StructuredAnswer; label: string }[] = [
  { key: 'answer', label: 'Answer' },
  { key: 'reason', label: 'Reason' },
  { key: 'evidence', label: 'Evidence' },
  { key: 'confidence', label: 'Confidence' },
  { key: 'missing', label: "What's missing" },
  { key: 'action', label: 'Suggested action' },
]

export function AnswerCard({ answer }: { answer: StructuredAnswer }) {
  const rows = ROWS.filter((r) => {
    const v = answer[r.key]
    return typeof v === 'string' && v.trim().length > 0
  })
  if (rows.length === 0) return null
  return (
    <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 rounded-xl border border-border bg-raised p-3 text-xs">
      {rows.map((r) => (
        <div key={r.key} className="contents">
          <dt className="font-semibold text-text-muted">{r.label}</dt>
          <dd className="text-text">{answer[r.key] as string}</dd>
        </div>
      ))}
    </dl>
  )
}
