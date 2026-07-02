/** TanStack Query hooks over the typed client. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type { AskRequest, CreatePatientRequest, IngestDocumentRequest } from './types'

export const qk = {
  timeline: (patient: string) => ['graph', patient] as const,
  cognee: (patient: string) => ['cognee', patient] as const,
  why: (factId: string | null) => ['why', factId] as const,
  health: () => ['health'] as const,
  patients: () => ['patients'] as const,
  documents: (patient: string) => ['documents', patient] as const,
  document: (docId: string | null) => ['document', docId] as const,
}

export function usePatients() {
  return useQuery({ queryKey: qk.patients(), queryFn: () => api.patients() })
}

export function useDoctors() {
  return useQuery({ queryKey: ['doctors'], queryFn: () => api.doctors() })
}

export function useBrief(patient: string | null) {
  return useQuery({
    queryKey: ['brief', patient ?? ''],
    queryFn: () => api.brief(patient as string),
    enabled: !!patient,
  })
}

export function useCreatePatient() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (req: CreatePatientRequest) => api.createPatient(req),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['patients'] }),
  })
}

export function useDocuments(patient: string | null) {
  return useQuery({
    queryKey: qk.documents(patient ?? ''),
    queryFn: () => api.documents(patient as string),
    enabled: !!patient,
  })
}

export function useDocument(docId: string | null) {
  return useQuery({
    queryKey: qk.document(docId),
    queryFn: () => api.document(docId as string),
    enabled: !!docId,
  })
}

export function useIngestDocument() {
  return useMutation({ mutationFn: (req: IngestDocumentRequest) => api.ingestDocument(req) })
}

/**
 * The full fact timeline (status at "now"). Keyed on patient ONLY — it does NOT
 * refetch while scrubbing; the Rewind slider recomputes status client-side
 * (lib/time.statusAt) so the graph morphs in real time with zero network.
 */
export function useTimeline(patient: string | null) {
  return useQuery({
    queryKey: qk.timeline(patient ?? ''),
    queryFn: () => api.graph(patient as string, null),
    enabled: !!patient,
  })
}

export function useCogneeGraph(patient: string | null, enabled: boolean) {
  return useQuery({
    queryKey: qk.cognee(patient ?? ''),
    queryFn: () => api.cogneeGraph(patient as string),
    enabled: enabled && !!patient,
  })
}

export function useWhy(factId: string | null) {
  return useQuery({
    queryKey: qk.why(factId),
    queryFn: () => api.why(factId as string),
    enabled: !!factId,
  })
}

export function useHealth() {
  return useQuery({
    queryKey: qk.health(),
    queryFn: () => api.health(),
    refetchInterval: 15_000,
  })
}

/** Invalidate everything derived from ledger/Cognee after a mutation. */
export function useInvalidateGraphs() {
  const qc = useQueryClient()
  return () => {
    qc.invalidateQueries({ queryKey: ['graph'] })
    qc.invalidateQueries({ queryKey: ['cognee'] })
    qc.invalidateQueries({ queryKey: ['documents'] })
    qc.invalidateQueries({ queryKey: ['brief'] })
  }
}

export function useAsk() {
  return useMutation({ mutationFn: (req: AskRequest) => api.ask(req) })
}
