# Phase 7 — Submission & meta-game (wins the other half of the points)

> Goal: convert a working app into a winning submission + grab bonus tracks.
> Inputs: app deployed/tunneled and demoable.

## A. Demo video (≤2 min) — shot list (record at 1440p)
1. (0:00–0:15) Hook: "AI memory's real failure isn't forgetting — it's remembering *wrong*. In healthcare that's dangerous." Show patient P001.
2. (0:15–0:40) Naive vs Total Recall: ask "Allergic to penicillin?" → Naive: **"Yes"** (red ⚠ stale) · Total Recall: **"No — cleared 2026-03-02"**.
3. (0:40–1:05) Live heal: click "Ingest: allergy cleared" → node greys + dashed SUPERSEDED_BY edge + toast. "It reconciled memory at write time."
4. (1:05–1:25) Time-travel (TWO ways): drag scrubber Feb→now → graph morphs; AND in chat ask "Allergic **back in February**?" → Total Recall: **"Yes, was allergic as of 2026-02-15"** vs now "No". "It keeps the past — it doesn't forget, it supersedes."
5. (1:25–1:40) Why: click node → chain + "Cognee's own reasoning agrees."
6. (1:40–1:52) **Forget (entered in error):** click "Retract: diabetes" → node *vanishes* from memory + graph (contrast with the grey-out of supersession). "Supersede keeps history; forget removes mistakes."
7. (1:52–2:00) One line naming the Cognee primitives used; "self-hosted, Vertex, no keys." CTA.
- Tools: OBS/loom; subtitles; upload unlisted YouTube/Loom; put link in README + submission.

## B. README (judges scan this) — required sections
1. One-liner + 20-sec problem.
2. Demo video + live link.
3. **"How we use Cognee"** — table mapping each primitive → file/function (keep it ACCURATE to the build):
   - `add` + `cognify(temporal_cognify=True)` → `memory/cognee_client.py` (`add_fact`, `cognify`); ingested via the engine `persist` node.
   - `recall` **TEMPORAL** (smart `/ask`, forced — reliable) · **RAG_COMPLETION** (naive villain over the frozen `naive_baseline` dataset) · CHUNKS (judge neighbor context). GRAPH_COMPLETION was dropped from the smart path (unreliable yes/no answers).
   - **`forget`** → `cognee_client.forget_fact` via `POST /forget` (entered-in-error retraction; single-item delete). Supersession deliberately does NOT forget — it retains dated history (the temporal/“evergreen” thesis).
   - `improve` → light pass after a heal (`persist`).
   - `get_graph_data` → `GET /graph/cognee` (raw KG view).
   - `node_set` (patient scoping) + provenance (ledger `chain` / `/why`).
   - (Stretch) custom `DataPoint` (`ClinicalFact`) + `memify` if Phase 5 done.
   Name the count: temporal add/cognify, recall (TEMPORAL/RAG), forget, improve, provenance = 5 of 6 rare primitives.
4. Architecture diagram (the MASTER_PLAN one) + the two-store rationale.
5. Run locally (Phase 0–3 commands) + deploy notes.
6. **AI-assistant disclosure** (REQUIRED by rules — list tools used). Missing this = disqualification.
7. Disclaimer: synthetic data, not medical advice.
8. License (MIT) — public repo (open-source track).

## C. Bonus tracks (same material, ~free)
- **Best Blog ($120 keyboard):** post "Building self-healing AI memory: contradiction-aware, time-travel memory on Cognee + Vertex." Reuse architecture + findings + screenshots.
- **Social Buzz (swag):** X/LinkedIn thread — the naive-kills-patient vs Total-Recall-saves clip + 3 bullets. Tag @cognee_ / @WeMakeDevs.
- **PR track ($100/PR, ≤5):** pick genuine Cognee issues; **comment + tag maintainers + wait for assignment**; no typo/AI-spam PRs (permanent-ban rules). The label-fallback bug we hit (Phase 0/5) may be a legit contribution — propose it.

## D. Submission checklist (do early, not at the deadline)
- [ ] Public repo (MIT) + README (all sections incl. AI disclosure)
- [ ] ≤2-min demo video linked
- [ ] Live link (Cloud Run or tunnel) working
- [ ] "How we use Cognee" section accurate
- [ ] Synthetic-data + not-medical-advice disclaimer in app + README
- [ ] Rename if desired (Total Recall = trademark) → e.g. Evergreen/Mnemo
- [ ] Submit on the form; declare team (solo)

## E. Final rules-compliance pass (from MASTER_PLAN §7)
Re-verify: uses Cognee memory ✅, AI disclosure ✅, built in window ✅, no PR spam ✅, disclaimer ✅.

## G. Theme tie-in (from `docs/theme-hangover.md`)
- **Video = the narrative spine:** cold-open neon "woke up with no memory" → lights-on → Hungover-AI-vs-Total-Recall contrast → live heal (REDACTED + red string) → "rewind the night" scrubber reveal → "why" case file. The film's beats, our product.
- **Submission art:** use `frontend/public/theme/og-share.png` as the repo/social OG image + the neon favicon. Thumbnail the demo video on the neon wordmark.
- **Blog/social:** lean the Hangover angle ("we gave an AI that woke up with no memory its context back — in a setting where forgetting kills"). Same assets.
- **Film grade on the video (theme-hangover.md §11):** open on the `TitleSequence`; keep subtle grain + 2.39:1 letterbox + light-leak transitions between beats; add sound — soft hum (cold-open), neon buzz, **record-scratch on "wake up"**, **camera-flash click on each reveal**, low beat under the title. Full cinematic sound lives here (muted in-app). This is what turns the screen-capture into a "movie".

## Done → submitted. 🎯
