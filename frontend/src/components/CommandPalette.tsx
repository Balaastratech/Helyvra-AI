import { useEffect, useState } from 'react'
import { Command } from 'cmdk'
import { useNavigate } from 'react-router-dom'
import { Search, UserRound, Network, Home, LogOut } from 'lucide-react'
import { usePatients } from '@/api/hooks'
import { useUi } from '@/store'

/**
 * ⌘K command palette (UX §2). Keyboard-first patient switch + navigation — the
 * single interaction that makes the tool feel professional. cmdk provides the
 * ARIA/listbox/focus-trap mechanics; we style it with the clinical tokens and
 * move focus to the input on open (research: always focus the input).
 */
export function CommandPalette() {
  const { cmdkOpen, setCmdkOpen, setPatient, setDoctor } = useUi()
  const navigate = useNavigate()
  const { data: patientsData } = usePatients()
  const patients = patientsData?.patients ?? []
  const [q, setQ] = useState('')

  // Global ⌘K / Ctrl+K toggle.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setCmdkOpen(!cmdkOpen)
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [cmdkOpen, setCmdkOpen])

  function run(fn: () => void) {
    setCmdkOpen(false)
    setQ('')
    fn()
  }
  function openPatient(id: string) {
    run(() => { setPatient(id); navigate(`/patient/${id}`) })
  }

  if (!cmdkOpen) return null

  return (
    <div
      className="fixed inset-0 z-[80] grid place-items-start justify-center bg-black/40 pt-[12vh]"
      onClick={() => setCmdkOpen(false)}
    >
      <Command
        label="Command palette"
        className="w-full max-w-xl overflow-hidden rounded-2xl border border-border bg-surface elev-2"
        onClick={(e) => e.stopPropagation()}
        loop
      >
        <div className="flex items-center gap-2 border-b border-border px-3">
          <Search className="h-4 w-4 text-text-faint" />
          <Command.Input
            autoFocus
            value={q}
            onValueChange={setQ}
            placeholder="Search patients, jump to a view…"
            className="h-11 flex-1 bg-transparent text-sm text-text outline-none placeholder:text-text-faint"
          />
          <kbd className="rounded border border-border px-1.5 py-0.5 text-[10px] text-text-faint">esc</kbd>
        </div>
        <Command.List className="max-h-[50vh] overflow-y-auto p-2">
          <Command.Empty className="px-2 py-6 text-center text-sm text-text-muted">
            No matches.
          </Command.Empty>

          <Command.Group heading="Patients" className="text-[10px] font-semibold uppercase tracking-wide text-text-faint [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1">
            {patients.map((p) => (
              <Command.Item
                key={p.patient_id}
                value={`${p.name} ${p.mrn}`}
                onSelect={() => openPatient(p.patient_id)}
                className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-2 text-sm text-text aria-selected:bg-active-soft aria-selected:text-active"
              >
                <UserRound className="h-4 w-4 text-text-faint" />
                <span className="font-medium">{p.name}</span>
                <span className="tabular ml-auto text-xs text-text-faint">{p.mrn}</span>
              </Command.Item>
            ))}
          </Command.Group>

          <Command.Group heading="Go to" className="mt-1 text-[10px] font-semibold uppercase tracking-wide text-text-faint [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1">
            {[
              { label: 'Dashboard', icon: Home, to: '/' },
              { label: 'Memory Map', icon: Network, to: '/memory' },
            ].map((v) => (
              <Command.Item
                key={v.to}
                value={v.label}
                onSelect={() => run(() => navigate(v.to))}
                className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-2 text-sm text-text aria-selected:bg-active-soft aria-selected:text-active"
              >
                <v.icon className="h-4 w-4 text-text-faint" /> {v.label}
              </Command.Item>
            ))}
            <Command.Item
              value="Sign out"
              onSelect={() => run(() => { setDoctor(null); navigate('/login') })}
              className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-2 text-sm text-text aria-selected:bg-active-soft aria-selected:text-active"
            >
              <LogOut className="h-4 w-4 text-text-faint" /> Sign out
            </Command.Item>
          </Command.Group>
        </Command.List>
      </Command>
    </div>
  )
}
