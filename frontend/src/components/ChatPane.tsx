import { useState, useRef, useEffect, type FormEvent } from 'react'
import {
  Send, Plus, MessageSquare, Brain, Sparkles, FileText,
  AlertTriangle, HelpCircle, ChevronRight, Check, X, Wrench,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { api } from '@/api/client'
import { useUi } from '@/store'
import { useInvalidateGraphs } from '@/api/hooks'
import type {
  Certainty, ChatResponse, ChatThread, Citation, PendingAction, TraceStep,
  ClinicalCardData, StructuredAnswer,
} from '@/api/types'
import { cn } from '@/lib/utils'
import { ClinicalCard } from '@/components/clinical/ClinicalCard'
import { AnswerCard } from '@/components/clinical/AnswerCard'

interface LocalMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  intent?: string | null
  actions?: string[]
  citations?: Citation[]
  certainty?: Certainty
  trace?: TraceStep[]
  pending?: PendingAction | null
  cards?: ClinicalCardData[]
  answer?: StructuredAnswer | null
  loading?: boolean
}

/** Honest uncertainty (§2.6.B): the AI's doubt must be as visible as its answer. */
function CertaintyBadge({ certainty }: { certainty?: Certainty }) {
  if (!certainty || certainty === 'settled') return null
  if (certainty === 'contested') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/50 bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-400">
        <AlertTriangle className="h-2.5 w-2.5" /> needs review — records conflict
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-text-muted/40 bg-white/5 px-2 py-0.5 text-[10px] font-medium text-text-muted">
      <HelpCircle className="h-2.5 w-2.5" /> unverified
    </span>
  )
}

/** Citation chips — click opens the exact source document (provenance you can see). */
function CitationChips({ citations }: { citations?: Citation[] }) {
  const openDoc = useUi((s) => s.openDoc)
  const openWhy = useUi((s) => s.openWhy)
  if (!citations || citations.length === 0) return null
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5">
      {citations.map((c, i) => (
        <button
          key={`${c.fact_id}-${i}`}
          onClick={() => (c.source_document ? openDoc(c.source_document, c.page) : openWhy(c.fact_id))}
          title={c.source_document ? 'Open source document' : 'Show provenance'}
          className="inline-flex items-center gap-1 rounded-full border border-active/40 bg-active-soft px-2 py-0.5 text-[10px] font-medium text-active hover:border-active hover:bg-active/10"
        >
          <FileText className="h-2.5 w-2.5" />
          {c.document_title || c.source || `${c.valid_from ?? ''}`.trim() || 'source'}
        </button>
      ))}
    </div>
  )
}

const TOOL_LABEL: Record<string, string> = {
  recall_patient_facts: 'checked memory',
  ingest_fact: 'recorded a fact',
  propose_forget: 'proposed a correction',
  why_changed: 'traced history',
}

/**
 * The agent's work, in the chat (§8). Calm one-line summary by default;
 * progressive disclosure (§2.6.D) opens the raw tool/args/timing on demand.
 */
function TraceView({ trace }: { trace?: TraceStep[] }) {
  const [raw, setRaw] = useState(false)
  if (!trace || trace.length === 0) return null
  const summary = trace.map((s) => s.chip || TOOL_LABEL[s.tool] || s.tool).join(' · ')
  return (
    <div className="mt-2 border-t border-border/60 pt-2">
      <button
        onClick={() => setRaw((v) => !v)}
        className="flex items-center gap-1 text-[10px] text-text-muted hover:text-text"
      >
        <ChevronRight className={cn('h-3 w-3 transition-transform', raw && 'rotate-90')} />
        <Wrench className="h-2.5 w-2.5" />
        <span className="truncate">{summary}</span>
        <span className="ml-1 underline">{raw ? 'hide' : 'raw'}</span>
      </button>
      {raw && (
        <div className="mt-1.5 space-y-1 rounded-lg bg-black/30 p-2 font-mono text-[10px] text-text-muted">
          {trace.map((s) => (
            <div key={s.seq}>
              <span className="text-active">{s.tool}</span>
              {s.args && Object.keys(s.args).length > 0 && (
                <span>({JSON.stringify(s.args)})</span>
              )}
              {typeof s.ms === 'number' && <span className="text-text-muted/60"> · {s.ms}ms</span>}
              {s.result_summary && (
                <div className="truncate pl-2 text-text-muted/80">→ {s.result_summary}</div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/**
 * Correction approval (§2.6.C) — framed as fixing a record together, not a
 * destructive admin op. Nothing is deleted until the clinician confirms.
 */
function ApprovalCard({
  pending, onResolved,
}: {
  pending: PendingAction
  onResolved: (msg: string) => void
}) {
  const [busy, setBusy] = useState(false)
  const invalidate = useInvalidateGraphs()
  const openWhy = useUi((s) => s.openWhy)

  async function decide(decision: 'approve' | 'reject') {
    if (busy) return
    setBusy(true)
    try {
      const res = await api.chatApprove({ pending_id: pending.pending_id, decision })
      if (decision === 'approve') {
        invalidate()
        openWhy(pending.fact_id)
      }
      onResolved(res.message)
    } catch (err: any) {
      onResolved(`Could not apply the correction: ${err.message}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mt-2 rounded-xl border border-amber-500/40 bg-amber-500/5 p-3 text-xs">
      <div className="flex items-center gap-1.5 font-medium text-amber-300">
        <AlertTriangle className="h-3.5 w-3.5" /> Confirm correction
      </div>
      <p className="mt-1 text-text">
        Mark <span className="font-medium">{pending.label}</span>{' '}
        <span className="text-text-muted">({pending.valid_from}, {pending.source})</span> as
        entered in error and remove it from memory?
      </p>
      <div className="mt-2 flex gap-2">
        <button
          onClick={() => decide('approve')}
          disabled={busy}
          className="inline-flex items-center gap-1 rounded-lg bg-amber-500 px-3 py-1 font-medium text-black hover:bg-amber-400 disabled:opacity-50"
        >
          <Check className="h-3 w-3" /> Confirm
        </button>
        <button
          onClick={() => decide('reject')}
          disabled={busy}
          className="inline-flex items-center gap-1 rounded-lg border border-border px-3 py-1 text-text-muted hover:text-text disabled:opacity-50"
        >
          <X className="h-3 w-3" /> Keep it
        </button>
      </div>
    </div>
  )
}

export function ChatPane() {
  const { patientId, openWhy, doctor } = useUi()
  const [threads, setThreads] = useState<ChatThread[]>([])
  const [activeThread, setActiveThread] = useState<string | null>(null)
  const [messages, setMessages] = useState<LocalMessage[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const scrollRef = useRef<HTMLDivElement>(null)

  // Load threads on patient change
  useEffect(() => {
    if (!patientId) return
    api.chatThreads(patientId).then(setThreads).catch(() => setThreads([]))
    setActiveThread(null)
    setMessages([])
  }, [patientId])

  // Load messages when thread changes
  useEffect(() => {
    if (!activeThread) {
      setMessages([])
      return
    }
    api.chatMessages(activeThread).then((msgs) => {
      setMessages(msgs.map((m) => ({
        id: m.id, role: m.role, content: m.content, intent: m.intent,
        citations: m.citations, certainty: m.certainty, trace: m.trace, pending: m.pending,
        cards: m.cards, answer: m.answer,
      })))
    }).catch(() => setMessages([]))
  }, [activeThread])

  // Auto-scroll
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  async function sendMessage(text: string) {
    if (!text.trim() || !patientId || sending) return
    setSending(true)

    const userMsg: LocalMessage = {
      id: crypto.randomUUID(), role: 'user', content: text.trim(),
    }
    const loadingMsg: LocalMessage = {
      id: crypto.randomUUID(), role: 'assistant', content: '', loading: true,
    }
    setMessages((prev) => [...prev, userMsg, loadingMsg])
    setInput('')

    try {
      const res: ChatResponse = await api.chat({
        patient_id: patientId,
        message: text.trim(),
        thread_id: activeThread,
        doctor_id: doctor?.doctor_id ?? null,
      })

      // If no active thread, this created one
      if (!activeThread) {
        setActiveThread(res.thread_id)
        api.chatThreads(patientId).then(setThreads).catch(() => {})
      }

      setMessages((prev) =>
        prev.map((m) =>
          m.loading
            ? {
                id: m.id, role: 'assistant', content: res.reply, intent: res.intent,
                actions: res.actions, citations: res.citations, certainty: res.certainty,
                trace: res.trace, pending: res.pending, cards: res.cards, answer: res.answer,
              }
            : m
        )
      )

      // The agent may have changed memory mid-turn — surface the affected fact.
      if (res.fact_id) openWhy(res.fact_id)
    } catch (err: any) {
      setMessages((prev) =>
        prev.map((m) =>
          m.loading
            ? {
                id: m.id, role: 'assistant',
                content:
                  "I couldn't reach memory just now — your message wasn't lost. " +
                  "Please try again; if it keeps happening, the backend may be starting up.",
              }
            : m
        )
      )
    } finally {
      setSending(false)
    }
  }

  // Resolve a pending correction: clear the card and append the outcome.
  function resolvePending(msgId: string, outcome: string) {
    setMessages((prev) => {
      const next = prev.map((m) => (m.id === msgId ? { ...m, pending: null } : m))
      return [
        ...next,
        { id: crypto.randomUUID(), role: 'assistant' as const, content: outcome },
      ]
    })
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    sendMessage(input)
  }

  function startNewThread() {
    setActiveThread(null)
    setMessages([])
  }

  function selectThread(id: string) {
    setActiveThread(id)
  }

  if (!patientId) return null

  return (
    <div className="flex h-full min-h-0">
      {/* Thread sidebar */}
      {sidebarOpen && (
        <aside className="flex w-64 flex-col border-r border-border bg-raised/50">
          <div className="flex items-center justify-between border-b border-border px-3 py-2">
            <span className="text-xs font-semibold text-text-muted uppercase tracking-wide">Conversations</span>
            <button
              onClick={startNewThread}
              className="rounded-lg p-1.5 text-text-muted hover:bg-white/5 hover:text-active"
              title="New conversation"
            >
              <Plus className="h-4 w-4" />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            <button
              onClick={startNewThread}
              className={cn(
                'flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors',
                !activeThread
                  ? 'bg-active-soft text-active'
                  : 'text-text-muted hover:bg-white/5 hover:text-text'
              )}
            >
              <Sparkles className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">New chat</span>
            </button>
            {threads.map((t) => (
              <button
                key={t.id}
                onClick={() => selectThread(t.id)}
                className={cn(
                  'flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors',
                  activeThread === t.id
                    ? 'bg-active-soft text-active'
                    : 'text-text-muted hover:bg-white/5 hover:text-text'
                )}
              >
                <MessageSquare className="h-3.5 w-3.5 shrink-0" />
                <span className="truncate">{t.title || 'Untitled'}</span>
              </button>
            ))}
          </div>
        </aside>
      )}

      {/* Main chat area */}
      <div className="flex flex-1 flex-col min-h-0">
        <div className="flex items-center border-b border-border px-4 py-2">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="rounded-lg p-1.5 text-text-muted hover:text-text hover:bg-white/5"
            title={sidebarOpen ? 'Hide sidebar' : 'Show sidebar'}
          >
            <MessageSquare className="h-4 w-4" />
          </button>
          <h2 className="ml-3 text-sm font-medium text-text">
            {activeThread
              ? threads.find((t) => t.id === activeThread)?.title || 'Chat'
              : 'New conversation'}
          </h2>
        </div>

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center gap-4">
              <Brain className="h-12 w-12 text-active/40" />
              <div>
                <h3 className="text-lg font-medium text-text">Total Recall Assistant</h3>
                <p className="mt-1 text-sm text-text-muted max-w-md">
                  Ask about this patient's medical history. I remember everything —
                  what's current, what changed, when, and why.
                </p>
              </div>
              <div className="grid grid-cols-2 gap-2 mt-4 max-w-lg">
                {[
                  'Is the patient allergic to penicillin?',
                  'What medications are they on?',
                  'Why was the allergy cleared?',
                  'Show me the medication history',
                ].map((q) => (
                  <button
                    key={q}
                    onClick={() => sendMessage(q)}
                    className="rounded-xl border border-border bg-raised px-3 py-2 text-left text-xs text-text-muted hover:border-active/40 hover:text-text transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m) => (
            <div
              key={m.id}
              className={cn('flex', m.role === 'user' ? 'justify-end' : 'justify-start')}
            >
              <div
                className={cn(
                  'max-w-[80%] rounded-2xl px-4 py-2.5 text-sm',
                  m.role === 'user'
                    ? 'bg-active text-white rounded-br-md'
                    : 'bg-raised border border-border text-text rounded-bl-md'
                )}
              >
                {m.loading ? (
                  <div className="flex items-center gap-2 text-text-muted">
                    <div className="flex gap-1">
                      <span className="h-1.5 w-1.5 rounded-full bg-active animate-bounce [animation-delay:0ms]" />
                      <span className="h-1.5 w-1.5 rounded-full bg-active animate-bounce [animation-delay:150ms]" />
                      <span className="h-1.5 w-1.5 rounded-full bg-active animate-bounce [animation-delay:300ms]" />
                    </div>
                    <span className="text-xs">Checking memory…</span>
                  </div>
                ) : (
                  <>
                    <div className="whitespace-pre-wrap">{m.content}</div>
                    {m.role === 'assistant' && (
                      <>
                        {m.answer && <AnswerCard answer={m.answer} />}
                        {m.cards && m.cards.length > 0 && (
                          <div className="mt-2 space-y-2">
                            {m.cards.map((c) => <ClinicalCard key={c.check_id} card={c} />)}
                          </div>
                        )}
                        {m.certainty && m.certainty !== 'settled' && (
                          <div className="mt-2">
                            <CertaintyBadge certainty={m.certainty} />
                          </div>
                        )}
                        <CitationChips citations={m.citations} />
                        {m.pending && (
                          <ApprovalCard
                            pending={m.pending}
                            onResolved={(msg) => resolvePending(m.id, msg)}
                          />
                        )}
                        <TraceView trace={m.trace} />
                      </>
                    )}
                  </>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Input */}
        <form onSubmit={onSubmit} className="border-t border-border p-4">
          <div className="flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about this patient…"
              className="h-10 flex-1 rounded-xl border border-border bg-raised px-4 text-sm text-text outline-none placeholder:text-text-muted/70 focus:ring-2 focus:ring-active"
              aria-label="Chat message"
              disabled={sending}
            />
            <Button type="submit" disabled={sending || !input.trim()}>
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
