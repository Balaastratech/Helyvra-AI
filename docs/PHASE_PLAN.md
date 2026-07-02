# PHASE_PLAN — Total Recall (solo, 7 days)

> Window: Jun 29 (today) → Jul 5. Build top-down: **Tier 1 must be demoable by end of Day 4** so you always have a submittable entry. Everything after is upside.

## Day 1 — Foundation + spike the risky bit
- New repo, `pip install cognee`, configure cheap LLM provider + API key, `.env`, cost cap.
- **De-risk first:** smallest possible script — `add` two contradicting facts, `cognify(temporal_cognify=True)`, `search` both `GRAPH_COMPLETION` and `TEMPORAL`. Confirm temporal works locally on your machine. (If `temporal_cognify` misbehaves, you learn on Day 1, not Day 6.)
- Author synthetic patient timeline #1 (10–15 facts, ≥3 supersession events: allergy cleared, med switched, diagnosis updated).
- **Checkpoint:** Cognee runs locally; temporal search returns something sane.

## Day 2 — Self-healing engine (MUST core)
- Thin Cognee adapter module (all Cognee calls in one place).
- Implement the pipeline: `recall related → contradiction judge → SUPERSEDES/CONTRADICTS/NEW/CONSISTENT → improve/forget + valid_to + SUPERSEDED_BY edge`.
- Unit-test the judge on your seeded supersession cases (TDD the classifier — it's the heart).
- **Checkpoint:** ingesting the timeline produces correct current-truth answers in a script.

## Day 3 — Backend API + naive baseline
- FastAPI: `/seed`, `/ingest`, `/ask` (with `mode` + `as_of`), `/graph?as_of=`.
- Implement **naive mode** = plain `RAG_COMPLETION`/`CHUNKS` with no reconciliation (this is your villain).
- **Checkpoint:** curl the same question in both modes → demonstrably different answers.

## Day 4 — Frontend: split chat + graph + scrubber (MUST visual)
- React/Vite/Tailwind. Split-chat view (Total Recall vs Naive).
- Sigma graph from `/graph`; **date scrubber** filters by `valid_from/valid_to`; superseded nodes grey, edges dashed.
- Disclaimer banner ("demo only, synthetic data, not medical advice").
- **Checkpoint (END OF TIER 1): you have a complete, submittable project.** Record a rough screen capture as insurance.

## Day 5 — "Why did this change?" (SHOULD — the eye-catch)
- `/why?fact_id=` → traverse provenance/`SUPERSEDED_BY` → return path + source + date.
- "Why" panel in UI on node click.
- **Checkpoint:** clicking a corrected fact explains itself.

## Day 6 — STRETCH + harden
- `ClinicalFact` DataPoint schema + custom extraction prompt/Task (engineering-depth credit).
- Optional `memify()` "consolidation" pass + a second patient timeline.
- Polish: empty states, loading, error handling, seed reset button.
- Buffer for whatever slipped.

## Day 7 — Win the meta-game (presentation = scored)
- **Demo video ≤2 min:** problem → naive kills patient → Total Recall saves → scrubber rewind → "why" trace → one line on each Cognee primitive used.
- **README:** problem, architecture diagram, **"How we use Cognee"** section naming every primitive, run instructions, disclaimer.
- **Best-Blog post** + **Social-Buzz thread** from the same material (extra prize tracks, ~free).
- Optional: 1–3 real Cognee issue PRs ($100 each) — comment, wait for assignment, **never spam (permanent-ban rule)**.
- Submit early; don't race the deadline.

## Daily discipline
- Commit per working slice. Each tier independently demoable. If a day slips, cut from the *top of the stretch*, never from Tier 1.
- Keep a running `spend.log` of LLM calls/cost.

## Definition of done (minimum to submit)
Tier 1 complete + 2-min video + README with the Cognee section + disclaimer. Everything else is score-maximizing upside.
