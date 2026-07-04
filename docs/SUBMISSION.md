# Submission — Total Recall

Ready-to-paste answers for the WeMakeDevs × Cognee hackathon submission form
(**The Hangover Part AI: Where's My Context?**, Jun 29 – Jul 5 2026).
Submit at: https://forms.gle/KXFatNScKAqAvCyM8

---

## Basics

- **Project name:** Total Recall
- **Track:** Best Use of Open Source (self-hosted Cognee)
- **Team size:** 1 (solo)
- **Repo:** _paste your public GitHub URL_
- **Demo video:** _paste your YouTube/Drive link (~3 min)_


## Tagline (one line)

A self-healing, time-aware clinical memory on self-hosted Cognee that never confidently tells a doctor
something that's no longer true — it catches allergy conflicts, missed follow-ups, and stale facts a
busy clinician would miss.

## Problem (2–3 sentences)

The headline failure of AI memory isn't forgetting — it's remembering *wrong*. Naive RAG answers with
whichever chunk ranks highest, so it confidently repeats superseded facts ("allergic to penicillin",
"on lisinopril"). In healthcare, a confidently stale answer is a prescription for a patient who can't
breathe.

## Solution (short)

A doctor uploads whatever records a clinic actually has (notes, PDFs, lab CSVs, even a photo of a paper
prescription). Cognee builds a self-healing, time-aware knowledge graph per patient. Every new fact is
reconciled at write time: contradictions supersede old facts with a validity window + `SUPERSEDED_BY`
edge (never hard-deleted), so you can rewind the graph to any date and ask "why did this change?".
`forget()` is reserved for entered-in-error facts. The result is a pre-visit brief, prescribe-time
safety STOPs, a naive-vs-healed compare view, and a consented family graph — every answer cited.

## How we used Cognee (the "Best Use of Cognee" answer)

Full `remember → recall → improve → forget` lifecycle, plus rare primitives:
- **remember** — `add(node_set=[patient])` + `cognify(temporal_cognify=True)` (isolated per-patient
  datasets, time-aware), grounded against an OWL/RDF medical ontology (`ontology_valid`).
- **recall** — `search` in TEMPORAL (current + point-in-time), RAG_COMPLETION (the naive baseline
  villain), and CHUNKS/graph modes.
- **improve** — `improve()` / memify after each heal; materializes cross-fact `CardiovascularRisk`
  relationships spanning three documents.
- **forget** — surgical retraction of entered-in-error facts (distinct from supersession, which retains
  dated history).
- **Custom DataPoints** — `ClinicalFact` (attribute-rich, grounded) and `Dedup()` `FamilyMember` nodes
  shared across linked charts.
- **Self-hosted** — SQLite + LanceDB + Kuzu, local embeddings (fastembed), no API keys. (This is the
  Best Use of Open Source track.)

## Judging-criteria mapping (see README for the table)

1. **Potential Impact** — stale clinical memory = patient harm; concrete safety outcomes.
2. **Creativity & Innovation** — forgetting-as-a-feature, a time-machine over the graph, reading a photo
   of a prescription, a consented family graph.
3. **Technical Excellence** — write-time reconciliation, temporal cognify, ontology grounding, memify,
   Dedup graph, multimodal ingest, auditable LangGraph engine (SQLite checkpointer).
4. **Best Use of Cognee** — whole lifecycle + rare primitives, self-hosted.
5. **User Experience** — calm light clinical UI, cited answers, honest uncertainty, ⌘K, noir compare.
6. **Presentation Quality** — README + docs/ARCHITECTURE.md + code-generated demo video.

## Tech stack

Cognee (self-hosted: SQLite + LanceDB + Kuzu) · FastAPI · LangGraph · Vertex AI Gemini (ADC) ·
fastembed (local) · React 19 + Vite + TypeScript + Tailwind.

## AI-assistance disclosure

Built with AI assistance (Claude Code, Gemini) for pair-programming, scaffolding, and the code-generated
demo video. All architecture, verification, and final review by the author.

## Compliance checklist

- [x] Uses Cognee for memory (self-hosted).
- [x] Synthetic data only — no real PHI/PII; "not medical advice" disclaimer visible in app + video.
- [x] AI-assistance disclosed.
- [x] Public repo with README + architecture doc.
- [ ] Demo video uploaded and link pasted above (~2–3 min, demo not slideshow).
- [ ] Repo is public and the submission form is filled before the deadline.
