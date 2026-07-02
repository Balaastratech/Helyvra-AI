# UPGRADE PLAN — Total Recall (real agent pass)

> v3 of this plan. v1 (intake + answer synthesis + UI) and v2 (real tool-calling agent, Cognee ACL
> hardening) are unchanged and still correct. v3 adds the constraints and surfacing that an audit
> against a comparable WeMakeDevs hackathon winner (§2.5) showed were missing — not new subsystems,
> changes to how the existing agent is constrained and how its work is shown. Does not touch the
> self-healing engine (`engine/{state,nodes,judge,graph}.py`) — proven, the actual differentiator.
>
> Deadline: **Jul 5**, ~5 days left as of today (Jun 30).

---

## 0. Implementation status (Jun 30)

| Work item | Status | Notes |
|---|---|---|
| §5 Universal intake | ✅ already shipped | `intake/pipeline.py` + `POST /intake` |
| §6 Answer synthesis | ✅ already shipped | `engine/answer.synthesize` (also behind `recall_patient_facts`) |
| §7 Real tool-calling agent | ✅ built | `agent/tools.py` (four closure-bound tools) + `agent/router.py` (ReAct loop). `POST /chat` now drives it; v1 intent classifier removed. |
| §8 UI action chips | ✅ built | `ChatResponse.actions` → inline chips in `ChatPane`; affected fact opens the Inspector. |
| §4 Cognee ACL hardening | ⚠️ **deviated — see below** | |

**Deviation on §4 (Cognee isolation hardening).** Flipping
`ENABLE_BACKEND_ACCESS_CONTROL=true` and routing through `create_authorized_dataset()`
is **not** done. In the installed Cognee (1.2.2) that flag coerces the process into
*authentication-required, multi-tenant* mode and `create_authorized_dataset(name, user)`
requires a `User` principal + dataset-**ID** addressing — which conflicts with the
proven, name-based `dataset_for()` flow that `/seed`, `/ingest`, and `/ask` depend on.
Turning it on globally would break the working demo two days before the deadline for
marginal gain. The core requirement ("a doctor asking about a patient only gets that
patient") is already met **structurally** by the closure-bound tool scoping in
`agent/tools.py` — the model never sees or supplies a `patient_id`, so it cannot reach
another patient's dataset (covered by `tests/test_agent.py`). The ACL upgrade path is
documented inline in `memory/cognee_client.py` for when per-clinician auth becomes real.

**Deviation on §7.2 (graph framework).** Built on google-genai's native
function-calling loop instead of LangGraph `ToolNode`, to avoid adding a
langchain/langgraph-prebuilt dependency the repo doesn't already have. Same
hand-rolled-loop spirit as `engine/graph.py`; iteration cap lives in `agent/router.py`
(`_MAX_ROUNDS`).

### v3 status (Days 1–4 — implemented)

| v3 work item | Status | Where |
|---|---|---|
| §6 / §2.6.B — cited, certainty-aware synthesis | ✅ | `engine/answer.py`: `synthesize_answer()` → `{answer_text, citations, certainty}`; deterministic `_enforce_certainty` guard so a contested fact can never be reported as settled. `synthesize()` kept as the back-compat string accessor for `/ask`. |
| §7.1 / §2.5 — forced grounding | ✅ | `agent/router._SYSTEM` forbids parametric clinical answers (must call `recall_patient_facts`). Prompt-invariant test in `tests/test_agent.py::test_system_prompt_forces_grounding` (live model-level assertion is an online/integration check). |
| §7.1 / §2.6.C — staged correction | ✅ | `forget_fact` → `propose_forget` (stages a pending action, no delete) + `POST /chat/approve` executes via `tools.execute_forget`. Pending + idempotency stores in `agent/pending.py`. Tests updated. |
| §7.5 — idempotency on writes | ✅ | `ingest_fact` deduped by `make_key(patient_id, text)`; approve is idempotent via `pop_pending`. `tests/test_agent.py::test_ingest_fact_is_idempotent`. |
| §7.5 — structured per-turn trace, persisted | ✅ | Router builds `{seq,tool,args,result_summary,ms,...}`; persisted as JSON on the assistant `ChatMessage.meta` (additive migration in `history._migrate`), re-served by the messages endpoint so the UI re-renders after reload. |
| §8 — UI surfacing | ✅ | `ChatPane.tsx`: certainty badge, clickable citation chips (→ `DocumentViewer`), inline tool trace with a "Raw" toggle (progressive disclosure), and a correction-framed approval card calling `/chat/approve`. |
| §7.3 — SSE streaming | ⏸️ deferred (plan cut-order) | Shipped the plan's sanctioned fallback: a single non-streamed JSON `/chat` response carrying the full `trace`/`citations`/`certainty`/`pending`. The UI renders the same data; live token streaming is the documented cut. |
| §7.5 — durable turn checkpoint/resume | ⏸️ deferred (plan cut-order) | Idempotency (the retry-safety half) shipped; SqliteSaver-style resume of an interrupted agent turn on the native-genai loop is the plan's explicit first-to-cut item. Trace is persisted, so observability is intact. |

---

## 1. The core requirement this version satisfies

> "Real agent that can do things — data update, data injection, data retrieval, data deletion —
> like a real running agent. If a doctor asks about a specific patient, it should only answer from
> that patient's data. All patient data should be retrievable from one chat."

This is a **tool-calling agent**, not a chat UI with API buttons behind it, and not an "intent
classifier that picks an endpoint" (the v1 draft of this plan). The agent must:
1. Actually decide, per turn, whether to ingest, recall, forget, or explain — via real LangGraph
   tool calls, looping until it has enough to answer (ReAct pattern).
2. Be **structurally** incapable of answering from another patient's data — not "prompted not to,"
   but bound to one patient's Cognee dataset at the tool level, so the model can't leak across
   patients even if it tried.
3. Use Cognee as the actual backing store for every one of those four verbs — Cognee is the hero,
   confirmed: `remember`/`recall`/`improve`/`forget` are literally the hackathon's named primitives
   (per the hackathon's own rules: "stronger submissions lean on its memory lifecycle APIs").

## 2. Research findings that ground this design (not assumed)

- **Cognee's real isolation mechanism is dataset-scoped permissions, not just naming.**
  `ENABLE_BACKEND_ACCESS_CONTROL` (on by default) enforces dataset boundaries on every query.
  `create_authorized_dataset()` creates a dataset *and* grants the creator full
  read/write/delete/share ACL in one call — the documented recommended path for per-entity
  isolation (per-customer/per-tenant/per-patient). True isolation requires SQLite/Postgres
  (relational) + LanceDB/PGVector/Qdrant (vector) + Kùzu/Neo4j (graph) — **exactly the stack this
  project already runs.** [Cognee permissions docs](https://docs.cognee.ai/core-concepts/multi-user-mode/permissions-system/datasets)
- **`node_set` is a complementary, lighter-weight filter, not a security boundary.** It only
  affects `GRAPH_COMPLETION`-family and `TEMPORAL` search types, has no effect on
  `RAG_COMPLETION`/`CHUNKS`/`CYPHER`. Good for sub-scoping *within* an already-isolated dataset
  (e.g. tag facts by category), not for guaranteeing patient isolation on its own.
  [Cognee search basics](https://docs.cognee.ai/guides/search-basics)
- **The official Cognee+LangGraph pattern wraps `add`/`search` as tools bound to a session via
  closures** (`get_sessionized_cognee_tools(session_id)` in the `langgraph_cognee` package),
  fed into a tool-calling loop. We mirror this shape (closure-bound scope) but hand-build the
  graph instead of using `create_react_agent`, because (a) LangGraph's own reference docs now flag
  `create_react_agent` as deprecated in favor of hand-built graphs, and (b) this codebase's engine
  already hand-builds `StateGraph`s with explicit nodes/edges — consistent style, no new
  abstraction. [Cognee+LangGraph integration](https://www.cognee.ai/blog/integrations/langgraph-cognee-integration-build-langgraph-agents-with-persistent-cognee-memory)
- **Cognee's own agent-facing skill doc confirms the four core verbs map to `add`/`cognify`/
  `search`/`forget`/`memify`**, and documents a `node_set` tagging convention
  (`node_set=["customer_123", "preferences"]`) and a feedback-reinforcement search type
  (`SearchType.FEEDBACK`) for closing the loop on what answers were useful — a rare primitive,
  noted as Day-5 stretch (§7). [cognee/skill.md](https://github.com/topoteretes/cognee/blob/main/cognee/skill.md)
- **Hackathon rules confirm:** stronger submissions lean on the full memory lifecycle
  (`remember/recall/improve/forget`), theme is open as long as Cognee is the memory layer, AI-tool
  use must be disclosed. Consistent with `MASTER_PLAN.md`; no change to the existing rubric
  understanding. [Hackathon rules](https://www.wemakedevs.org/hackathons/cognee/rules)

## 2.5 Audit against a winning bar (researched, not assumed)

Total Recall isn't in the Coral hackathon, but it's the same organizer (WeMakeDevs) and almost
certainly overlapping judges/criteria philosophy, so its winner (**Manthan**, Coral-hackathon
winner — [site](https://www.manthan.quest/), [repo](https://github.com/akash-mondal/manthan)) is
the right calibration for "what depth actually wins" here. Manthan is an autonomous B2B billing-
dispute investigator; the domain is irrelevant, the *constraints* are what won:

| What won for Manthan | What it actually means | Where our plan was missing it |
|---|---|---|
| System prompt **forbids** one-shot/sequential lookups — forces real cross-source reasoning | Winning isn't "uses an LLM," it's "the system makes shortcuts structurally impossible" | Nothing stopped our agent from answering a clinical question from parametric knowledge instead of calling Cognee |
| Every claim in the brief is **cited to a source record**, clickable to the exact row | Hallucination defense is structural (forced grounding), not "trust the model" | `engine/answer.py` synthesized prose only; `ClinicalFact.source_document` already exists in our schema but was unused by the answer step |
| Tool calls **stream live into the UI**, branded ("Manthan is asking 🟢 Intercom"), raw-feed toggle for power users | Transparency *is* the product polish, not a debug feature | v2 planned to hide the actions log in a collapsed "Inspector drawer" — backwards |
| Destructive/consequential actions staged behind one **human-approval click** before executing | Real agents that can delete/change things need a checkpoint before acting, not after | `forget_fact` was just another tool the agent could call and execute freely mid-conversation |

This section drives the changes in §6, §7, §8 below. None of it is a new subsystem — it's
constraints on the existing agent loop and how its existing action log is surfaced.

## 2.6 Quality bar — the concepts behind what wins (researched, not assumed)

The audit (§2.5) caught *missing features*. This section is the deeper pass the project needs:
the *qualities* that separate a demo from a product clinicians would actually use. Each is a
researched principle with a concrete "where we apply it" — none is a new subsystem; all raise the
bar on code that already exists or is already planned.

**A. Transparency beats accuracy for trust (clinical-AI research).** In real clinician studies,
*visible reasoning mattered more for trust than raw prediction performance* — clinicians valued
understanding *why* over a perfect black-box answer; passive "here's the answer" displays caused
**automation bias** (over-reliance), while interactive reasoning made clinicians evaluate
critically. → The live tool-call trace (§7.3/§8) is therefore not polish; it is the primary trust
mechanism and must be on by default, in plain language ("checking memory… found 2 historical
records for *allergy*"), not buried. [Clinical copilot study](https://arxiv.org/pdf/2602.00726)

**B. Honest uncertainty increases trust; overconfidence destroys it.** The same research: "a
copilot that presents itself as a confident expert sets a bar it cannot clear… a capable assistant
that sometimes needs correction keeps people using it." Confidence calibration *increased* trust.
→ **This is our biggest current gap.** `ClinicalFact` already carries `confidence` and a
`contested` status (from the engine's CONTRADICTS path), and `cognee_client` notes
`GRAPH_COMPLETION` is unreliable — yet nothing surfaces any of it. New requirement (§6): the
synthesized answer must explicitly flag low-confidence or `contested` facts ("two records conflict
here and I can't resolve which is current — Dr. Lee 2026-03-02 vs …"), and never present a
contested fact as settled truth. Honesty about what it doesn't know is a feature, not a bug.
[Clinical copilot UX](https://www.theskinsfactory.com/uiux-design-blog/ai-copilot-ux-design)

**C. Editable predictions / collaborative correction (sense of control).** Clinicians adopt AI
they can *correct and watch update* — control without friction. → Reframe "forget" (§7.1): it's
not just deletion, it's the clinician correcting the record. The flow "that allergy entry is
wrong" should feel like fixing a colleague's note (propose → one-click confirm → visible update),
which is exactly the propose/approve gate — but the *framing and copy* matter: collaborative
correction, not a destructive admin operation.

**D. Progressive disclosure governs the whole UI (anti-overload).** Dense technical explanation
*decreased* usability; the winning balance is concise-by-default, depth-on-demand. → Governing UI
principle for §8: the default chat view stays calm (answer + citation chips + a one-line trace);
the raw tool/args/Cognee-dataset detail lives behind the "Raw" toggle; the full graph/provenance
lives in the Memory-Map tab. Never dump everything at once.

**E. Production-agent robustness is a named concern, not an afterthought** (what made Manthan's
actor worker trustworthy, and the consensus of durable-execution literature): *idempotency keys on
every write so a retry can't double-apply; durable checkpoint/resume so an interrupted turn
recovers; structured observability — every tool call's input/output/timing logged.* → New work
item §7.5. We already have pieces (the engine's `SqliteSaver` checkpointer; idempotent
`ingest_document`; the `actions` log) — §7.5 makes them consistent across the *agent* path, not
just the ingest path. [Idempotent agents](https://www.buildmvpfast.com/blog/idempotent-ai-agent-retry-safe-patterns-production-workflow-2026) ·
[Durable execution for agents](https://temporal.io/blog/from-ai-hype-to-durable-reality-why-agentic-flows-need-distributed-systems)

**F. Graceful error recovery, in-context (agentic-UX pattern).** Agents fail (Cognee down,
extraction returns garbage, model calls a bad tool); the pattern is *communicate the failure in
human terms, preserve context, offer the next step* — not a stack trace, not a silent wrong
answer. → The codebase already degrades correctly on the backend ("ledger is authoritative if
Cognee sync fails", `cognee_client.py`) but never tells the *user*. New requirement (§8): when a
tool errors or memory is degraded, the agent says so plainly ("I saved this but couldn't refresh
the semantic index — the record is stored, search may lag a moment") and the conversation
continues. Honest degradation over false success. [Agentic UI/UX patterns](https://agentic-design.ai/patterns/ui-ux-patterns)

## 3. What's reused unchanged

Everything from v1 §2, plus: the v1 universal-intake design (§5 there) is unchanged — it's still
the right way to get a fact in from an uploaded document. What changes here is what happens to a
fact typed directly into chat, and how retrieval/forget/why are invoked — they become **tool
calls inside one agent loop**, not separate endpoints the frontend calls directly.

## 4. Work item 0 — Cognee isolation hardening (new, small, high rubric value)

In `memory/cognee_client.py`, when a patient's dataset is first touched (`dataset_for(patient_id)`
/ `naive_dataset_for(patient_id)`), create it via `create_authorized_dataset()` instead of letting
`add(..., dataset_name=...)` implicitly create a bare dataset. Set `ENABLE_BACKEND_ACCESS_CONTROL=
true` (confirm in `config.py`). This turns "isolated by naming convention" into "isolated by ACL,"
which is both the *correct* engineering answer to "where should patient data be stored for
isolation" and a deeper, rarer Cognee primitive for the judges (permissions system — almost no
hackathon team will touch this).
`// ponytail: single default user owns all authorized datasets (no real multi-clinician auth in
this demo) — upgrade to per-clinician principals only if multi-user login becomes a real feature.`

## 5. Work item 1 — Universal intake (unchanged from v1)

See v1 plan §5 — format sniffing (text/PDF/FHIR), identity resolution (match-or-create patient,
no manual entry), reusing the existing `_run_ingest` → engine pipeline. No changes here; this is
the entry point that feeds facts into the agent's `ingest_fact` tool path below.

## 6. Work item 2 — Answer synthesis with forced citations (extends v1, audit-driven)

Base mechanics unchanged from v1 §6 — full fact history → one synthesized answer (current + prior
+ when/why changed + source). **New requirement from the audit (§2.5):** the synthesis call's
output schema is `{answer_text: str, citations: list[Citation]}`, not free prose. Each
`Citation = {fact_id, source_document, document_title, valid_from, source}` — fields that already
exist on `ClinicalFact` today (`source_document`/`document_title`), just never surfaced. Every
sentence in `answer_text` that asserts a fact must correspond to at least one citation; the
synthesis prompt requires this structurally (structured output, same `response_schema` pattern as
`judge.py`/`extract.py` already use — no new technique, just a richer schema).

**Uncertainty surfacing (quality bar §2.6.B — the biggest current gap).** The schema extends to
`{answer_text, citations, certainty: "settled"|"contested"|"low_confidence"}`. The synthesis input
already has each fact's `status` and `confidence` from the ledger; the prompt must (a) set
`certainty="contested"` and refuse to present a single answer when same-subject facts are
`contested`, instead naming both conflicting records and their sources; (b) flag `low_confidence`
when the active fact's `confidence` is below a threshold; (c) only say "settled" when there is one
clear, current, non-contested fact. The agent's voice is "capable assistant that sometimes needs
correction," never "confident expert." A wrong confident answer is the one failure mode this
project exists to prevent — it must not reappear in our *own* answers.

This becomes the implementation of the `recall_patient_facts` tool (§7), not a branch inside
`/ask`. `/ask`'s `total_recall` branch calls the same underlying function for the Compare tab.

## 7. Work item 3 — The real agent (`backend/app/agent/`) — replaces v1's intent router

### 7.1 Tools (`agent/tools.py`)

Four tools, each a thin wrapper over existing, already-correct code — **no new business logic**,
only new bindings:

| Tool | Wraps | Verb |
|---|---|---|
| `recall_patient_facts(query)` | `engine/answer.py` synthesis (§6, now cited) over `dataset_for(patient_id)` | recall |
| `ingest_fact(text)` | existing `extract.build_fact` → `engine/service.run_fact` (recall→judge→reconcile→persist) | remember / improve |
| `propose_forget(fact_id, reason)` | builds a pending forget request (does **not** call `cognee_client.forget_fact` yet — see approval gate below) | forget (proposal) |
| `why_changed(subject)` | existing `/why` provenance trace | explain |

**`forget` is staged, not direct (audit §2.5).** `propose_forget` returns a pending action the
agent surfaces to the user ("Remove the penicillin-allergy entry from 2026-01-10 — entered in
error? This can't be undone.") instead of executing immediately. A second endpoint,
`POST /chat/approve {pending_id}`, is the only path that actually calls the existing
`cognee_client.forget_fact` / `/forget` logic. Mirrors Manthan's Investigate→Decide→**Approve**
split for any action that mutates or deletes memory — `ingest_fact` stays auto-executing (additive,
already self-healing/reversible via supersession history), only `forget` (destructive, no history
retained) gets the human checkpoint.

**Forced grounding (audit §2.5).** The agent's system prompt explicitly states it must never
answer a clinical question (allergy/medication/diagnosis/lab) from its own knowledge — every such
claim requires a `recall_patient_facts` call this turn, no exceptions, mirroring Manthan's
"forbid one-shot lookups" constraint. A turn that produces a clinical claim with zero tool calls
is treated as a bug, not a valid path — add a unit test asserting this (ask a clinical question,
assert at least one `recall_patient_facts` call occurred before any clinical claim in the reply).

**Patient scoping is closure-bound, not an LLM-supplied argument.** `build_patient_tools(patient_id)`
returns these four tools with `patient_id` already baked into each closure (mirroring the official
`get_sessionized_cognee_tools(session_id)` shape). The tool signatures the model sees never include
`patient_id` — the model cannot ask for, guess, or be tricked into another patient's data, because
the Python closure (not a prompt instruction) determines which Cognee dataset every call touches.
This is the literal mechanism for "if a doctor asks about a specific patient, it should only answer
from that patient" — enforced twice: once by the closure binding, once by Cognee's own ACL (§4).

### 7.2 Agent graph (`agent/graph.py`)

Hand-built `StateGraph` (same style as `engine/graph.py`), not the deprecated `create_react_agent`:

```
START -> agent_node -> route -> tools_node -> agent_node  (loop)
                     -> route -> END (no more tool calls)
```

- `agent_node`: one Vertex Gemini call with the four tools bound (function-calling), given the
  running message history.
- `tools_node`: executes whichever tool(s) the model called.
- `route`: END when the model's response has no tool calls (it's ready to answer in plain text);
  otherwise loop back through `tools_node`.
- Iteration cap (`_MAX_ROUNDS` in `agent/router.py`) prevents an unbounded loop.

**As-built note (§0 deviation):** the shipped version implements this loop on **google-genai's
native function-calling** rather than LangGraph `ToolNode`, to avoid adding a langgraph-prebuilt
dependency the repo didn't already carry. Same hand-rolled-loop spirit as `engine/graph.py`; the
§7.5 durable-checkpoint addition reuses the engine's `SqliteSaver` pattern on top of it.

### 7.3 Endpoints

`POST /chat {patient_id, message, session_id}` → resolves the patient (already known from intake
or the patient context bar), builds that patient's bound tools, invokes the graph. **Streams** via
SSE (audit §2.5 — "the agent's reasoning is the show, live"): each tool call and its result is
emitted as an event the moment it happens (`{type: "tool_call", tool, args}` →
`{type: "tool_result", tool, summary}`), then a final `{type: "answer", text, citations}`. This is
one additive change to FastAPI's response (`StreamingResponse`/SSE), not a new transport — no
websocket infra needed for a single-turn-at-a-time chat.

`POST /chat/approve {pending_id, decision: "approve"|"reject"}` → executes (or discards) a
`propose_forget` pending action (§7.1).

This **is** "all patient data retrievable from one chat" — recall, update (ingest), and delete
(propose+approve forget) all happen through the same conversation; the agent decides which tool(s)
a message needs, chaining several in one turn where needed (e.g. recall the current allergy, then
propose its removal, in one reply).

### 7.4 What this replaces from v1

v1's `agent/router.py` (a 4-way intent classifier guessing which single endpoint to call) is
dropped entirely — this tool-calling loop is the real version of that idea: the model decides,
can chain multiple actions in one turn, and is scoped at the binding layer instead of by prompt
instruction alone.

## 7.5 Work item 3b — Agent robustness (quality bar §2.6.E, new)

Makes the agent path as production-honest as Manthan's actor worker, reusing pieces that already
exist on the ingest path — small, mostly wiring:

- **Idempotency on every write tool.** `ingest_fact` and the approved-forget execution take an
  idempotency key (hash of patient_id + normalized fact + session turn). The ingest path is
  *already* idempotent (`ingest_document` checks `ingested_doc_ids`); extend the same guard to the
  agent tool so a model retry or duplicate tool call can't double-write a fact or double-forget.
- **Durable turn checkpointing.** The agent loop persists state per round via the existing
  `SqliteSaver` pattern (§7.2), so an interrupted turn (process restart, timeout) resumes instead
  of replaying side effects — the agent's equivalent of the engine checkpointer already proven in
  `engine/graph.py`.
- **Structured per-turn trace, persisted.** Every turn records an ordered list of
  `{seq, tool, args, result_summary, ms}` (the same shape Manthan logs per query) — this is both
  the observability record *and* the exact data the live UI trace (§8) renders. One artifact serves
  debugging and UX; don't build two.
- `// ponytail: idempotency key is an in-process/SQLite dedupe, not a distributed lock — fine for
  single-box demo; upgrade to a real key store only if this ever runs multi-instance.`

## 8. Work item 4 — UI redesign (audit-revised: trace is the UX, not a drawer)

Same base as v1 §8 (chat-first landing, global drop-zone, Compare/Memory-Map tabs), but the
"Inspector drawer" idea from v1/v2 is **dropped** per the audit — Manthan's lesson is that hiding
the agent's work is the wrong instinct. Instead:

- **Live inline trace, branded, in the chat itself.** As the SSE stream (§7.3) arrives, render
  small inline steps as they happen — "Total Recall is checking memory…" → "Found 2 historical
  records for *allergy*" — collapsing into the final answer once it lands. Not hidden, not a
  separate panel; this *is* the chat.
- **Citation chips** on every clinical claim in the final answer, built from the `citations` array
  (§6) — clicking one opens the source document (`DocumentViewer`, already built) at that record.
- **Approval card** for any `propose_forget` pending action — a small inline confirm/reject UI
  inside the chat, not a modal; rejecting just continues the conversation.
- A **"Raw" toggle** (mirrors Manthan's raw-SQL-feed toggle) on the trace for anyone who wants the
  literal tool name/args/Cognee dataset queried — same data as before, opt-in detail instead of an
  always-hidden drawer.
- **Certainty rendering (quality bar §2.6.B).** Answers carry their `certainty` (§6) visibly: a
  `contested` answer renders both conflicting records side by side with a "needs review" marker,
  never a single confident sentence; `low_confidence` gets a quiet "unverified" tag. The UI must
  make the AI's *doubt* as visible as its answer — this is the anti-automation-bias requirement.
- **Correction framing (quality bar §2.6.C).** The forget/correct approval card reads as fixing a
  record ("Mark this 2026-01-10 penicillin-allergy entry as entered-in-error?"), with the resulting
  memory change shown inline after approval — collaborative correction, not a destructive admin
  action.
- **Honest error/degraded states (quality bar §2.6.F).** When a tool errors or Cognee sync is
  degraded, the chat shows a plain-language notice ("stored, but semantic search may lag a moment")
  and continues — never a silent success, never a stack trace.

**Governing UI principle (§2.6.D): progressive disclosure.** Default view is calm — answer,
citation chips, one-line trace. Tool/args/dataset detail is behind "Raw"; full graph + provenance
lives in the Memory-Map tab. Depth is always one click away and never forced.

## 9. Explicitly deferred (unchanged from v1, +1 item)

Everything in v1 §10 (C-CDA, OCR, multi-user auth, fuzzy identity matching), plus:
- **`SearchType.FEEDBACK` reinforcement loop** (cognee/skill.md's documented pattern for having
  the agent learn which retrievals were useful) — genuine stretch credit, Day-5-if-time-allows,
  not required for the core "real agent" requirement.

## 10. Data/API surface changes (supersedes v1 §9 for the agent row)

| New | Changed | Unchanged |
|---|---|---|
| `POST /chat` (SSE-streamed, tool-calling agent) | `cognee_client.dataset_for`/`naive_dataset_for` now call `create_authorized_dataset()` | engine/*, ledger.py |
| `POST /chat/approve` (forget approval gate) | `engine/answer.py` returns `{answer_text, citations, certainty}`, not prose | `/why`, `/graph`, `/seed`, `/reset`, `/forget` (reused as functions, not duplicated) |
| `agent/{tools,graph}.py` | `/ask` total_recall branch calls shared (cited, certainty-aware) synthesis fn | intake/* (v1, unchanged) |
| `engine/answer.py`, `ledger.query_all()` | agent write tools gain idempotency keys (§7.5) | engine checkpointer pattern (reused for agent turns) |
| persisted per-turn trace `{seq,tool,args,result_summary,ms}` (§7.5) | ~~`config.py`: `ENABLE_BACKEND_ACCESS_CONTROL`~~ — deferred, see §0 | closure-bound patient scoping (the real isolation guarantee) |

## 11. Day-by-day (v3 — remaining work only)

v1/v2 are shipped (§0). What's left is the audit (§2.5) + quality-bar (§2.6) layer — constraints,
honesty, robustness, and surfacing on top of the working agent. Ordered so the highest-trust-impact
gaps land first and there's always a demoable state.

- **Day 1 — Honesty in the answer (highest trust impact, §2.6.B + §2.5 citations).** Extend
  `engine/answer.synthesize` to the `{answer_text, citations, certainty}` schema; wire `confidence`
  + `contested` status into the prompt. Verify: a contested subject returns both records, not one
  confident answer; every clinical claim maps to a real `source_document`. *Demoable: answers stop
  being "No." and start being honest, cited, and uncertainty-aware.*
- **Day 2 — Forced grounding + staged correction (§2.5 + §2.6.C).** System-prompt the agent to
  never answer clinical questions from parametric knowledge (+ the grounding unit test); split
  `forget` into `propose_forget` → `POST /chat/approve`. Verify: grounding test passes; a "this was
  entered in error" turn produces a proposal, not an immediate delete; cross-patient leakage test
  (§12) passes.
- **Day 3 — Robustness (§7.5).** Idempotency keys on `ingest_fact`/approved-forget; durable
  turn checkpoint via existing `SqliteSaver`; structured persisted per-turn trace
  (`{seq,tool,args,result_summary,ms}`). Verify: a duplicated/ retried tool call does not
  double-write; an interrupted turn resumes without replaying side effects.
- **Day 4 — Surfacing it all (§8).** SSE-stream `/chat`; live inline trace, citation chips,
  certainty rendering (contested side-by-side), correction-framed approval card, honest
  error/degraded notices; progressive-disclosure default + "Raw" toggle. Verify in browser: one
  thread handles a recall (live trace + chips + certainty), a correction (approval card → visible
  update), and an induced error (plain-language notice, conversation continues).
- **Day 5 — Buffer + Phase 7** (demo video, README "How we use Cognee" naming all six primitives +
  the permissions path, AI disclosure). Demo script now leads with the *quality* story: honest
  uncertainty, clickable citations, visible reasoning, human-approved correction — the things the
  audit says actually win.

> **Cut order if a day slips** (never cut Day 1): drop §7.5 durable-resume (keep idempotency) →
> drop the "Raw" toggle (keep the one-line trace) → defer SSE to non-streamed JSON (§12). Day 1–2
> honesty/grounding is the irreducible core and ships first for exactly this reason.

## 12. Risks (supersedes v1 §12)

| Risk | Mitigation |
|---|---|
| Model calls a tool with malformed/missing args | Standard LangGraph `ToolNode` error handling — return the error as a `ToolMessage`, let the model retry/recover in-loop. |
| Agent loops indefinitely (never reaches END) | Cap iterations (e.g. max 6 tool-call rounds per turn) in `route`, same defensive pattern as any ReAct loop. |
| `create_authorized_dataset` API differs from docs once actually called (Cognee API drift, same risk MASTER_PLAN.md already flags) | Behind the single `cognee_client.py` seam already established — one place to fix. |
| Patient-scoping closure has a bug that leaks `patient_id` | Unit test specifically: build tools for patient A, call with a query mentioning patient B by name, assert the Cognee call's `dataset`/`datasets` argument is still A's. |
| Agent answers a clinical claim without citations (forced-grounding constraint silently fails) | Unit test (§7.1): assert every clinical reply has ≥1 citation and ≥1 `recall_patient_facts` call this turn; treat a violation as a hard test failure, not a warning. |
| SSE adds complexity/flakiness under demo conditions | Single-turn-at-a-time SSE over plain HTTP, no websocket/reconnect logic needed; fallback is a non-streamed JSON response if SSE proves unstable close to the deadline. |

## References

- [Cognee permissions / datasets docs](https://docs.cognee.ai/core-concepts/multi-user-mode/permissions-system/datasets)
- [Cognee search basics (node_set vs dataset scoping)](https://docs.cognee.ai/guides/search-basics)
- [Cognee + LangGraph integration (official blog)](https://www.cognee.ai/blog/integrations/langgraph-cognee-integration-build-langgraph-agents-with-persistent-cognee-memory)
- [cognee/skill.md (agent-facing tool guidance)](https://github.com/topoteretes/cognee/blob/main/cognee/skill.md)
- [Cognee hackathon rules — WeMakeDevs](https://www.wemakedevs.org/hackathons/cognee/rules)
- [LangGraph `create_react_agent` reference (deprecation note)](https://reference.langchain.com/python/langgraph.prebuilt/chat_agent_executor/create_react_agent)
- [Coral hackathon rules — WeMakeDevs (audit baseline)](https://www.wemakedevs.org/hackathons/coral)
- [Manthan — winning project site](https://www.manthan.quest/)
- [Manthan — repo/README (architecture audited in §2.5)](https://github.com/akash-mondal/manthan)
- [Clinical AI copilot user study — transparency, calibration, control (§2.6.A–C)](https://arxiv.org/pdf/2602.00726)
- [AI copilot UX — "capable assistant, not confident expert" (§2.6.B)](https://www.theskinsfactory.com/uiux-design-blog/ai-copilot-ux-design)
- [Agentic UI/UX patterns — disclosure, status, recovery (§2.6.D, §2.6.F)](https://agentic-design.ai/patterns/ui-ux-patterns)
- [Idempotent / durable agent patterns (§2.6.E, §7.5)](https://www.buildmvpfast.com/blog/idempotent-ai-agent-retry-safe-patterns-production-workflow-2026)
- [Durable execution for agentic flows — Temporal (§2.6.E)](https://temporal.io/blog/from-ai-hype-to-durable-reality-why-agentic-flows-need-distributed-systems)
