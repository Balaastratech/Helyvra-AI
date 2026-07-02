/**
 * API contracts — MIRROR of backend/app/api/dto.py (the source of truth).
 * Dates cross the wire as ISO `YYYY-MM-DD` strings.
 */

export type Mode = 'total_recall' | 'naive'

export type FactStatus = 'active' | 'superseded' | 'contested' | 'retracted'

export type Classification =
  | 'CONSISTENT'
  | 'NEW'
  | 'SUPERSEDES'
  | 'CONTRADICTS'

/** memory/schema.py :: ClinicalFact (label is a computed plain-English field) */
export interface ClinicalFact {
  id: string
  patient_id: string
  subject: string
  predicate: string
  value: string
  label: string
  valid_from: string
  valid_to: string | null
  source: string
  status: FactStatus
  superseded_by: string | null
  confidence: number
  reason: string | null
  raw_text: string
  cognee_data_id: string | null
  source_document: string | null
  document_title: string | null
}

// --- /seed ----------------------------------------------------------------
export interface SeedRequest {
  patient_id: string
}
export interface HeldBack {
  label: string
  text: string
}
export interface SeedResponse {
  patient_id: string
  seeded: ClinicalFact[]
  held_back: HeldBack[]
}

// --- /ingest --------------------------------------------------------------
export interface IngestRequest {
  patient_id: string
  text?: string
  structured?: Record<string, unknown> | null
}
export interface IngestResponse {
  fact: ClinicalFact
  classification: string
  target_fact_id: string | null
  reason: string
  healed: boolean
  actions: string[]
}

// --- /reset ---------------------------------------------------------------
export interface ResetRequest {
  patient_id: string
}
export interface ResetResponse {
  ok: boolean
  patient_id: string
}

// --- /forget --------------------------------------------------------------
export interface ForgetRequest {
  patient_id: string
  fact_id: string
  reason?: string
}
export interface ForgetResponse {
  fact: ClinicalFact
  restored: ClinicalFact | null
  forgotten: boolean
  cognee: Record<string, unknown>
}

// --- /ask -----------------------------------------------------------------
export interface AskRequest {
  patient_id: string
  question: string
  mode: Mode
  as_of?: string | null
}
export interface AskResponse {
  answer: string
  mode: Mode
  search_type: string
  raw: unknown
}

// --- /graph ---------------------------------------------------------------
export type GraphEdgeType = 'SUPERSEDED_BY' | 'SAME_SUBJECT' | 'RELATED_TO' | 'RISK'
export type GraphNodeKind = 'fact' | 'relative' | 'risk'
export interface GraphNode {
  id: string
  label: string
  subject: string
  value: string
  status: string // active | superseded (computed at as_of)
  valid_from: string
  valid_to: string | null
  source: string
  source_document?: string | null
  document_title?: string | null
  // visualization layer (additive)
  category?: string
  confidence?: number
  ontology_valid?: boolean | null
  kind?: GraphNodeKind
}
export interface GraphEdge {
  source: string
  target: string
  type: GraphEdgeType
  label?: string
}
export interface GraphResponse {
  as_of: string
  nodes: GraphNode[]
  edges: GraphEdge[]
}

// --- /graph/cognee --------------------------------------------------------
export interface CogneeNode {
  id: string
  label: string
  type: string
  properties: Record<string, unknown>
}
export interface CogneeEdge {
  source: string
  target: string
  type: string
}
export interface CogneeGraphResponse {
  nodes: CogneeNode[]
  edges: CogneeEdge[]
}

// --- /why -----------------------------------------------------------------
export interface WhyResponse {
  fact: ClinicalFact
  superseded_by: ClinicalFact | null
  reason: string
  source: string
  date: string | null
  chain: ClinicalFact[]
}

// --- /health --------------------------------------------------------------
export interface HealthResponse {
  ok: boolean
  cognee: string
  ledger: string
}


// --- /patients ------------------------------------------------------------
export interface Patient {
  patient_id: string
  mrn: string
  name: string
  dob: string
  sex: string
  summary: string
}
export interface PatientsResponse {
  patients: Patient[]
}
export interface CreatePatientRequest {
  name: string
  dob?: string
  sex?: string
  mrn?: string
}

// --- /patients/{id}/documents ---------------------------------------------
export interface DocumentSummary {
  doc_id: string
  date: string
  type: string
  author: string
  title: string
  entered_in_error: boolean
  ingested: boolean
  fact_id: string | null
}
export interface DocumentsResponse {
  patient_id: string
  documents: DocumentSummary[]
}
export interface DocumentDetail extends DocumentSummary {
  patient_id: string
  text: string
}

// --- /ingest_document -----------------------------------------------------
export interface IngestDocumentRequest {
  patient_id: string
  doc_id: string
}
export interface IngestDocumentResponse {
  doc_id: string
  facts: ClinicalFact[]
  classification: string
  healed: boolean
  reason: string
  actions: string[]
}

// --- /intake (universal upload) -------------------------------------------
export interface IntakeResponse {
  patient_id: string
  patient_name: string
  doc_id: string
  facts: ClinicalFact[]
  classification: string
  healed: boolean
  reason: string
  actions: string[]
  created_patient: boolean
}

// --- /chat (conversational agent) -----------------------------------------
export interface ChatRequest {
  patient_id: string
  message: string
  thread_id?: string | null
  doctor_id?: string | null
}

/** One grounding citation behind a clinical claim (answer.py :: Citation). */
export interface Citation {
  fact_id: string
  source_document: string | null
  document_title: string | null
  page?: number | null
  valid_from: string | null
  source: string
}

export type Certainty = 'settled' | 'contested' | 'low_confidence'

/** One step in the agent's per-turn tool trace (§7.5). */
export interface TraceStep {
  seq: number
  tool: string
  chip?: string
  args?: Record<string, unknown>
  ms?: number
  result_summary?: string
  fact_id?: string
  certainty?: Certainty
  deduped?: boolean
}

/** A staged correction awaiting one-click human approval (§7.1). */
export interface PendingAction {
  pending_id: string
  fact_id: string
  label: string
  valid_from: string
  source: string
  reason: string
}

export interface ChatResponse {
  reply: string
  intent: string
  thread_id: string
  fact_id: string | null
  actions: string[]
  citations: Citation[]
  certainty: Certainty
  trace: TraceStep[]
  pending: PendingAction | null
  cards?: ClinicalCardData[]
  answer?: StructuredAnswer | null
}

export interface ChatApproveRequest {
  pending_id: string
  decision: 'approve' | 'reject'
}
export interface ChatApproveResponse {
  ok: boolean
  decision: string
  message: string
  fact_id: string | null
  restored_fact_id: string | null
  forgotten: boolean
}
export interface ChatThread {
  id: string
  patient_id: string
  title: string
  created_at: string
  updated_at: string
}
export interface ChatMessage {
  id: string
  thread_id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  intent: string | null
  citations?: Citation[]
  certainty?: Certainty
  trace?: TraceStep[]
  pending?: PendingAction | null
  cards?: ClinicalCardData[]
  answer?: StructuredAnswer | null
}

// --- access / identity (routes_access.py) ---------------------------------
export interface Doctor {
  doctor_id: string
  name: string
  specialty: string
  role: string
}

export interface PatientMatch {
  patient_id: string
  name: string
  mrn: string
  dob: string
  sex: string
  age: number | null
  last_visit: string | null
  summary: string
}

export interface ResolveResponse {
  query: string
  resolved: PatientMatch | null
  candidates: PatientMatch[]
}

export interface AuditEntry {
  doctor: string
  ts: string
  patient?: string | null
  action: string
  decision?: string
  evidence_ids?: string[]
}

// --- clinical cards (checks/cards.py :: Card) -----------------------------
export type Indicator = 'info' | 'warning' | 'critical'

export interface CardCitation {
  label: string
  source_document: string | null
  page: number | null
  date: string | null
  fact_id: string | null
}

export interface ClinicalCardData {
  check_id: string
  summary: string
  indicator: Indicator
  detail: string
  source: CardCitation[]
  suggestions: string[]
}

// --- family links (routes_family.py) --------------------------------------
export interface FamilyLink {
  patient_id: string
  relative_id: string
  relation: string
  confidence: 'high' | 'medium'
  consent: boolean
  proposed?: boolean
}
export interface FamilyLinksResponse {
  patient_id: string
  links: FamilyLink[]
}

// --- pre-visit brief (routes_patients.py :: BriefResponse) ----------------
export interface BriefItem {
  fact_id: string
  label: string
  value: string
  date: string
  status: string
  resource_type: string | null
  source_document: string | null
  document_title: string | null
  page?: number | null
  attributes: Record<string, unknown>
}

export interface BriefResponse {
  patient: Patient
  age: number | null
  fact_count: number
  allergy_badge: string | null
  risk_badge: boolean
  groups: Record<string, BriefItem[]>
  cards: ClinicalCardData[]
}

// --- chat: the six-part structured clinical answer (§5.3) -----------------
export interface StructuredAnswer {
  answer?: string
  reason?: string
  evidence?: string
  confidence?: string
  missing?: string
  action?: string
  [k: string]: unknown
}
