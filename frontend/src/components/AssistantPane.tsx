import { Loader2, AlertTriangle, Info } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { searchTypeCopy } from '@/lib/labels'
import { cn } from '@/lib/utils'

export interface PaneMessage {
  id: string
  question: string
  answer?: string
  searchType?: string
  asOf?: string | null
  loading: boolean
  stale?: boolean
}

interface AssistantPaneProps {
  title: string
  emoji: string
  subtitle: string
  mascot: string
  /** hungover = desaturated magenta villain; recall = crisp cyan hero. */
  register: 'recall' | 'hungover'
  messages: PaneMessage[]
  emptyHint: string
}

export function AssistantPane({
  title,
  emoji,
  subtitle,
  mascot,
  register,
  messages,
  emptyHint,
}: AssistantPaneProps) {
  const hungover = register === 'hungover'
  return (
    <div
      className={cn(
        'flex h-full min-h-0 flex-col rounded-xl border bg-surface',
        hungover ? 'border-magenta/25' : 'border-active/25',
      )}
    >
      <header
        className={cn(
          'flex items-center justify-between gap-2 rounded-t-xl border-b px-4 py-3',
          hungover ? 'border-magenta/15 bg-magenta-soft' : 'border-active/15 bg-active-soft',
        )}
      >
        <div className="flex items-center gap-2">
          <span aria-hidden className="text-lg">
            {emoji}
          </span>
          <div className="leading-tight">
            <h3 className={cn('text-sm font-semibold', hungover ? 'text-magenta' : 'text-active')}>
              {title}
            </h3>
            <p className="text-[11px] text-text-muted">{subtitle}</p>
          </div>
        </div>
      </header>

      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
            <img src={mascot} alt="" className="h-20 w-20 opacity-80" />
            <p className="max-w-[14rem] text-sm text-text-muted">{emptyHint}</p>
          </div>
        ) : (
          messages.map((m) => {
            const chip = m.searchType ? searchTypeCopy(m.searchType) : null
            return (
              <div key={m.id} className="space-y-1.5">
                <div className="ml-auto w-fit max-w-[90%] rounded-xl bg-white/5 px-3 py-1.5 text-sm text-text-muted">
                  {m.question}
                </div>
                <div
                  className={cn(
                    'w-fit max-w-[95%] rounded-xl px-3 py-2 text-sm ring-1',
                    hungover ? 'bg-magenta-soft text-text ring-magenta/15' : 'bg-active-soft text-text ring-active/15',
                  )}
                >
                  {m.loading ? (
                    <span className="flex items-center gap-2 text-text-muted">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      {hungover ? 'Mumbling something…' : 'Checking the records…'}
                    </span>
                  ) : (
                    <>
                      <p className="leading-relaxed">{m.answer}</p>
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        {m.stale && (
                          <Badge variant="stale">
                            <AlertTriangle className="h-3 w-3" /> outdated — could be dangerous
                          </Badge>
                        )}
                        {chip && (
                          <span
                            className={cn(
                              'inline-flex items-center gap-1 text-[11px]',
                              hungover ? 'text-magenta/80' : 'text-active/80',
                            )}
                            title={chip.tip}
                          >
                            <Info className="h-3 w-3" />
                            {chip.label}
                          </span>
                        )}
                        {!hungover && (
                          <span className="text-[11px] text-text-muted">
                            as of {m.asOf ?? 'today'}
                          </span>
                        )}
                      </div>
                    </>
                  )}
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
