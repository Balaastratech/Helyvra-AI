/** Always-visible legend so the Memory Map explains itself. */
export function Legend() {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 rounded-xl border border-border bg-surface px-4 py-2.5 text-xs text-text-muted">
      <span className="flex items-center gap-1.5">
        <span className="h-3 w-3 rounded-full" style={{ background: '#22d3ee' }} />
        Active fact
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-3 w-3 rounded-full opacity-50" style={{ background: '#64748b' }} />
        Replaced / not yet known
      </span>
      <span className="flex items-center gap-1.5">
        <svg width="26" height="8" aria-hidden>
          <line x1="0" y1="4" x2="26" y2="4" stroke="#e11d48" strokeWidth="1.6" strokeDasharray="5 3" />
        </svg>
        Replaced by
      </span>
      <span className="ml-auto text-text-muted/80">Drag “Rewind time” to watch facts turn on and off.</span>
    </div>
  )
}
