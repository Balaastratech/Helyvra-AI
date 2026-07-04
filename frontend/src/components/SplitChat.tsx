import { useState, type FormEvent } from 'react'
import { Send } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { AssistantPane, type PaneMessage } from './AssistantPane'
import { PresetQuestions, type Preset } from './PresetQuestions'
import { api } from '@/api/client'
import { useUi } from '@/store'
import type { AskResponse } from '@/api/types'

interface Turn {
  id: string
  question: string
  asOf: string | null
  total: AskResponse | null
  naive: AskResponse | null
  loadingTotal: boolean
  loadingNaive: boolean
}

const norm = (s?: string) => (s ?? '').trim().toLowerCase().replace(/\s+/g, ' ')

export function SplitChat() {
  const { patientId, asOf, setAsOf, markStep } = useUi()
  const [input, setInput] = useState('')
  const [turns, setTurns] = useState<Turn[]>([])

  const busy = turns.some((t) => t.loadingTotal || t.loadingNaive)

  async function ask(question: string, asOfOverride?: string) {
    const q = question.trim()
    if (!q || !patientId) return
    markStep('asked')
    // A time-travel question rewinds the timeline; the answer is computed for that date.
    const effectiveAsOf = asOfOverride !== undefined ? asOfOverride : asOf
    if (asOfOverride !== undefined && asOfOverride !== asOf) setAsOf(asOfOverride)

    const id = crypto.randomUUID()
    setTurns((prev) => [
      ...prev,
      { id, question: q, asOf: effectiveAsOf, total: null, naive: null, loadingTotal: true, loadingNaive: true },
    ])
    const patch = (p: Partial<Turn>) =>
      setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, ...p } : t)))

    api
      .ask({ patient_id: patientId, question: q, mode: 'total_recall', as_of: effectiveAsOf })
      .then((res) => patch({ total: res, loadingTotal: false }))
      .catch((e: Error) =>
        patch({ total: { answer: `Error: ${e.message}`, mode: 'total_recall', search_type: 'TEMPORAL', raw: null }, loadingTotal: false }),
      )
    api
      .ask({ patient_id: patientId, question: q, mode: 'naive' })
      .then((res) => patch({ naive: res, loadingNaive: false }))
      .catch((e: Error) =>
        patch({ naive: { answer: `Error: ${e.message}`, mode: 'naive', search_type: 'RAG_COMPLETION', raw: null }, loadingNaive: false }),
      )
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    ask(input)
    setInput('')
  }

  const totalMsgs: PaneMessage[] = turns.map((t) => ({
    id: t.id,
    question: t.question,
    answer: t.total?.answer,
    searchType: t.total?.search_type,
    asOf: t.asOf,
    loading: t.loadingTotal,
  }))
  const naiveMsgs: PaneMessage[] = turns.map((t) => ({
    id: t.id,
    question: t.question,
    answer: t.naive?.answer,
    searchType: t.naive?.search_type,
    loading: t.loadingNaive,
    stale:
      !!t.total?.answer && !!t.naive?.answer && norm(t.total.answer) !== norm(t.naive.answer),
  }))

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <div className="grid min-h-0 flex-1 grid-cols-2 gap-4">
        <AssistantPane
          title="Helyvra"
          emoji="🧠"
          subtitle="Remembers what changed."
          mascot="/theme/mascot-alert.png"
          register="recall"
          messages={totalMsgs}
          emptyHint="Ask a question — it answers from up-to-date memory and respects the rewind date."
        />
        <AssistantPane
          title="Hungover AI"
          emoji="🥴"
          subtitle="Woke up with no memory."
          mascot="/theme/mascot-groggy.png"
          register="hungover"
          messages={naiveMsgs}
          emptyHint="Answers from before the records were corrected — often outdated."
        />
      </div>

      <div className="space-y-2">
        <PresetQuestions onPick={(p: Preset) => ask(p.question, p.asOf)} disabled={busy} />
        <form onSubmit={onSubmit} className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask both assistants the same question…"
            className="h-10 flex-1 rounded-xl border border-border bg-raised px-3 text-sm text-text outline-none placeholder:text-text-muted/70 focus:ring-2 focus:ring-active"
            aria-label="Ask both assistants"
          />
          <Button type="submit" disabled={busy || !input.trim()}>
            <Send className="h-4 w-4" /> Ask both
          </Button>
        </form>
      </div>
    </div>
  )
}
