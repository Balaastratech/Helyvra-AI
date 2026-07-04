/**
 * Typed fetch wrappers — one function per Phase-2 endpoint (dto.py contracts).
 * Base URL from VITE_API_BASE (defaults to localhost:8000).
 */
import type {
  AskRequest,
  AskResponse,
  AuditEntry,
  BatchIntakeResponse,
  BriefResponse,
  ChatApproveRequest,
  ChatApproveResponse,
  ChatMessage,
  ChatRequest,
  ChatResponse,
  ChatThread,
  CogneeGraphResponse,
  CreatePatientRequest,
  Doctor,
  DocumentDetail,
  DocumentsResponse,
  FamilyLinksResponse,
  ForgetRequest,
  ForgetResponse,
  GraphResponse,
  HealthResponse,
  IngestDocumentRequest,
  IngestDocumentResponse,
  IngestRequest,
  IngestResponse,
  IntakeResponse,
  Patient,
  PatientsResponse,
  ResetRequest,
  ResetResponse,
  ResolveResponse,
  SeedRequest,
  SeedResponse,
  WhyResponse,
} from './types'

export const API_BASE =
  import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body?.detail ?? detail
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<T>
}

const post = <T>(path: string, body: unknown) =>
  http<T>(path, { method: 'POST', body: JSON.stringify(body) })

const qs = (params: Record<string, string | null | undefined>) => {
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v != null && v !== '') sp.set(k, v)
  }
  const s = sp.toString()
  return s ? `?${s}` : ''
}

export const api = {
  seed: (body: SeedRequest) => post<SeedResponse>('/seed', body),
  ingest: (body: IngestRequest) => post<IngestResponse>('/ingest', body),
  reset: (body: ResetRequest) => post<ResetResponse>('/reset', body),
  forget: (body: ForgetRequest) => post<ForgetResponse>('/forget', body),
  ask: (body: AskRequest) => post<AskResponse>('/ask', body),

  patients: () => http<PatientsResponse>('/patients'),
  createPatient: (body: CreatePatientRequest) => post<Patient>('/patients', body),
  brief: (patient_id: string) =>
    http<BriefResponse>(`/patients/${encodeURIComponent(patient_id)}/brief`),

  // --- access / identity (§7) ---
  doctors: () => http<Doctor[]>('/doctors'),
  resolve: (query: string, doctor_id?: string | null) =>
    http<ResolveResponse>(`/patients/resolve${qs({ query, doctor_id })}`),
  audit: (patient_id?: string | null) =>
    http<{ entries: AuditEntry[] }>(`/audit${qs({ patient_id })}`),
  documents: (patient_id: string) =>
    http<DocumentsResponse>(`/patients/${encodeURIComponent(patient_id)}/documents`),
  document: (doc_id: string) =>
    http<DocumentDetail>(`/documents/${encodeURIComponent(doc_id)}`),
  ingestDocument: (body: IngestDocumentRequest) =>
    post<IngestDocumentResponse>('/ingest_document', body),
  upload: async (patient_id: string, file: File) => {
    const form = new FormData()
    form.append('patient_id', patient_id)
    form.append('file', file)
    const res = await fetch(`${API_BASE}/upload`, { method: 'POST', body: form })
    if (!res.ok) {
      let detail = res.statusText
      try {
        detail = (await res.json())?.detail ?? detail
      } catch {
        /* ignore */
      }
      throw new ApiError(res.status, detail)
    }
    return res.json() as Promise<IngestDocumentResponse>
  },

  graph: (patient_id: string, as_of?: string | null) =>
    http<GraphResponse>(`/graph${qs({ patient_id, as_of })}`),
  cogneeGraph: (patient_id: string) =>
    http<CogneeGraphResponse>(`/graph/cognee${qs({ patient_id })}`),
  why: (fact_id: string) => http<WhyResponse>(`/why${qs({ fact_id })}`),
  health: () => http<HealthResponse>('/health'),

  // --- family links + consent gate (routes_family.py) ---
  family: (patient_id: string) =>
    http<FamilyLinksResponse>(`/family/${encodeURIComponent(patient_id)}`),
  setFamilyConsent: (body: { patient_id: string; relative_id: string; consent: boolean }) =>
    post<{ ok: boolean; consent: boolean }>('/family/consent', body),

  // --- Universal intake ---
  intake: async (file: File, patient_id?: string, force = false) => {
    const form = new FormData()
    form.append('file', file)
    if (patient_id) form.append('patient_id', patient_id)
    if (force) form.append('force', 'true')
    const res = await fetch(`${API_BASE}/intake`, { method: 'POST', body: form })
    if (!res.ok) {
      let detail = res.statusText
      try { detail = (await res.json())?.detail ?? detail } catch { /* */ }
      throw new ApiError(res.status, detail)
    }
    return res.json() as Promise<IntakeResponse>
  },

  // Multi-file drop as ONE request: the backend does one Cognee graph rebuild
  // for the whole batch instead of one per file (the actual fix for a 7-file
  // drop taking minutes — cognify's cost scales with the patient's total
  // fact count, so doing it N times instead of once was the real bottleneck).
  intakeBatch: async (files: File[], patient_id?: string) => {
    const form = new FormData()
    for (const file of files) form.append('files', file)
    if (patient_id) form.append('patient_id', patient_id)
    const res = await fetch(`${API_BASE}/intake/batch`, { method: 'POST', body: form })
    if (!res.ok) {
      let detail = res.statusText
      try { detail = (await res.json())?.detail ?? detail } catch { /* */ }
      throw new ApiError(res.status, detail)
    }
    return res.json() as Promise<BatchIntakeResponse>
  },

  // --- Chat (conversational agent) ---
  chat: (body: ChatRequest) => post<ChatResponse>('/chat', body),
  chatApprove: (body: ChatApproveRequest) =>
    post<ChatApproveResponse>('/chat/approve', body),
  chatThreads: (patient_id: string) =>
    http<ChatThread[]>(`/chat/threads${qs({ patient_id })}`),
  chatMessages: (thread_id: string) =>
    http<ChatMessage[]>(`/chat/threads/${encodeURIComponent(thread_id)}/messages`),
  createChatThread: (patient_id: string, title?: string) =>
    post<ChatThread>(`/chat/threads${qs({ patient_id, title })}`, {}),
  deleteChatThread: (thread_id: string) =>
    http<{ ok: boolean }>(`/chat/threads/${encodeURIComponent(thread_id)}`, { method: 'DELETE' }),
}

export { ApiError }
