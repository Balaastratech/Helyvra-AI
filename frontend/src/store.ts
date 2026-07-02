/** UI state (zustand). Server state lives in TanStack Query, not here. */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Doctor } from '@/api/types'

export type StepKey = 'loaded' | 'added' | 'asked'

interface UiState {
  /** simulated logged-in doctor (§7). null = show login. */
  doctor: Doctor | null
  /** active chart (null = patient picker / none selected yet). */
  patientId: string | null
  asOf: string | null
  whyFactId: string | null
  /** doc_id open in the document viewer, or null. */
  docId: string | null
  /** page of the citation that opened the doc (highlight target), or null. */
  docPage: number | null
  cinemaMode: boolean
  howOpen: boolean
  /** ⌘K command palette open state (§2). */
  cmdkOpen: boolean
  steps: Record<StepKey, boolean>

  setDoctor: (d: Doctor | null) => void
  setPatient: (id: string | null) => void
  setAsOf: (d: string | null) => void
  openWhy: (factId: string) => void
  closeWhy: () => void
  openDoc: (docId: string, page?: number | null) => void
  closeDoc: () => void
  toggleCinema: () => void
  setHowOpen: (v: boolean) => void
  setCmdkOpen: (v: boolean) => void
  markStep: (k: StepKey) => void
}

export const useUi = create<UiState>()(persist((set) => ({
  doctor: null,
  patientId: null,
  asOf: null,
  whyFactId: null,
  docId: null,
  docPage: null,
  cinemaMode: false,
  howOpen: false,
  cmdkOpen: false,
  steps: { loaded: false, added: false, asked: false },

  setDoctor: (d) => set({ doctor: d, patientId: null }),
  setPatient: (id) =>
    set({
      patientId: id,
      asOf: null,
      whyFactId: null,
      docId: null,
      docPage: null,
      steps: { loaded: false, added: false, asked: false },
    }),
  setAsOf: (d) => set({ asOf: d }),
  openWhy: (factId) => set({ whyFactId: factId }),
  closeWhy: () => set({ whyFactId: null }),
  openDoc: (docId, page = null) => set({ docId, docPage: page }),
  closeDoc: () => set({ docId: null, docPage: null }),
  toggleCinema: () => set((s) => ({ cinemaMode: !s.cinemaMode })),
  setHowOpen: (v) => set({ howOpen: v }),
  setCmdkOpen: (v) => set({ cmdkOpen: v }),
  markStep: (k) => set((s) => ({ steps: { ...s.steps, [k]: true } })),
}), {
  // ponytail: persist ONLY the demo login so a judge's F5 doesn't log them out.
  name: 'total-recall-ui',
  partialize: (s) => ({ doctor: s.doctor }) as UiState,
}))

export function nextStep(steps: Record<StepKey, boolean>): StepKey | null {
  if (!steps.loaded) return 'loaded'
  if (!steps.added) return 'added'
  if (!steps.asked) return 'asked'
  return null
}
