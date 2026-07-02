# DESIGN BRIEF — Total Recall UI (paste into your design tool)

Paste this whole file into v0 / Lovable / Claude design mode. Output: a **React + TypeScript +
Tailwind** single-page app that fetches from `import.meta.env.VITE_API_BASE` (FastAPI, already
running). Goal: a polished, cohesive, self-explanatory demo a hackathon judge understands in 30s.

## What this app is (say it like this in the UI)
**An AI that fixes its own memory.** When a patient's records change (an allergy gets cleared, a
drug gets switched), most AIs keep repeating the old, dangerous answer. Total Recall detects the
change, updates its memory, and can explain *why* — and even *rewind time* to show what it knew
when. We prove it by running two assistants side-by-side on the same question:
**Total Recall** (memory-aware, correct) vs **Hungover AI** (no memory, dangerously wrong).

## Fix these 3 things (the current build failed here)
1. **One cohesive theme — NOT light-center + dark-edges.** Make the WHOLE app a dark, premium
   "clinical command console" that matches the neon cold-open. Dark slate surfaces everywhere,
   off-white text, ONE teal/cyan accent for "active/correct", magenta for the Hungover/neon
   framing, red only for danger. No flat white panels. It must feel like one designed product.
2. **Human language, zero dev jargon.** Never show `RAG_COMPLETION`, `TEMPORAL`, `superseded`,
   `node_set`, "seed", "heal". Use the rewrite table below. (Keep the technical term only as a
   tiny tooltip on hover, for credibility.)
3. **Self-explanatory + guided.** A judge should never wonder what to click. Add a persistent
   "How it works" 3-step strip and a numbered guided scenario. Every panel has a one-line plain
   explanation. Empty states teach.

## Screen layout (single screen, dark, responsive ~1280–1440)
```
Header: ▣ TOTAL RECALL (neon wordmark)            [How it works ▸] [Cinema ⌃]
Amber strip: Demo only · synthetic data · not medical advice
┌ LEFT (Patient + Story) ─┬ CENTER (Two assistants) ──────────┬ RIGHT (Memory) ───────────┐
│ Patient P001 card        │ Total Recall  | Hungover AI       │ Tabs: Memory Map | The Board│
│  • current facts (plain) │  (two answer panes, shared input) │ graph (nodes = facts)       │
│ GUIDED STEPS (1·2·3):    │  preset questions as buttons      │ legend + plain explanation  │
│  1 Load history          │  answer shows "as of <date>"      │ "Rewind time" slider        │
│  2 Add new result ⚡      │                                   │ → click a fact → Why panel  │
│  3 Ask the question      │                                   │                             │
│ [Remove mistaken entry]  │                                   │                             │
│ [Reset]                  │                                   │                             │
└──────────────────────────┴───────────────────────────────────┴─────────────────────────────┘
```

## Feature inventory — surface ALL of these (label → what it does → endpoint)
| UI control (user language) | Plain caption | API |
|---|---|---|
| **Load patient history** | "Load P001's records into memory." | `POST /seed` |
| **Add new result: allergy cleared ⚡** (step 2, the WOW) | "A new lab clears the penicillin allergy — watch the AI update itself." | `POST /ingest` |
| Preset Q: *Is the patient allergic to penicillin?* | runs both assistants | `POST /ask` ×2 (mode) |
| Preset Q: *What blood-pressure medicine now?* | both | `POST /ask` |
| Preset Q: *Was the patient allergic back in February?* | time-travel | `POST /ask` with `as_of` from slider |
| Free question box | "Ask both assistants anything." | `POST /ask` |
| **Rewind time** slider | "Drag to see what the AI knew on any date." | `GET /graph?as_of=` + binds the as_of of total_recall `/ask` |
| **Memory Map** tab | "Each card is a fact. A dashed red arrow means 'replaced by'." | `GET /graph` |
| **The Board** tab | "How the AI connected the dots across the records." | `GET /graph/cognee` |
| Click a fact → **Why panel** | "Why this changed: the event, who, when, and the reasoning." | `GET /why?fact_id=` |
| **Remove mistaken entry** | "Delete a fact entered in error — it disappears from memory." | `POST /forget` |
| **Reset** | "Clear everything and start over." | `POST /reset` |
| Header dot "systems up" | quiet health pill | `GET /health` |

## Copy rewrite (dev → human) — apply everywhere
| Don't show | Show |
|---|---|
| `TEMPORAL` chip | "Time-aware memory" (tooltip: TEMPORAL) |
| `RAG_COMPLETION` chip | "No memory · plain lookup" (tooltip: RAG_COMPLETION) |
| "superseded" | "Replaced" / "Updated" |
| "Seed baseline" | "Load patient history" |
| "frozen pre-heal, no graph, no time" | "Answers from before the records were corrected." |
| "No knowledge graph yet — seed first" | "Load the patient's history to begin." |
| node label `allergy: penicillin` | use the API's `label` field — already plain English ("Allergic to penicillin", "Penicillin allergy cleared") |
| "Retract" | "Remove mistaken entry" |
| "Ask both AIs" | "Ask both assistants" |

## The two assistants (make the contrast obvious & fun)
- **Total Recall** — teal accent, 🧠, sub: "Remembers what changed." Correct answers. Small green "as of <date>" tag.
- **Hungover AI** — magenta/desaturated, 🥴, sub: "Woke up with no memory." When its answer differs from Total Recall, badge it red **"⚠ outdated — could be dangerous."**
- The naive answer is intentionally wrong (it's the villain). Make that legible, not a bug.

## Memory Map (the graph) — make it self-explanatory
- Each node = a fact card with its plain `label`, the date, and the source (e.g. "Dr. Lee").
- **active** = teal solid; **replaced** = greyed + a small "REPLACED" tag; dashed red arrow = "replaced by".
- Always-visible legend + one sentence: "Drag *Rewind time* to watch facts turn on and off."
- Use the supplied art: superseded cards can stamp `/theme/stamp-redacted.png`; The Board uses
  `/theme/board-cork.png` with pinned polaroids (`/theme/polaroid-frame.png` + `/theme/pushpin.png`).

## Why panel — plain, reassuring
Title: **"Why did this change?"** Then:
- One sentence: *"Penicillin allergy was cleared on 2026-03-02 by Dr. Lee, so the earlier 'allergic'
  record no longer applies."*
- A small 2-step history timeline (old → new) using the plain `label`s.
- Keep the "✓ The AI's own memory agrees — this is the reconciled truth, not a guess." line.
- NEVER show a fact replaced by an identically-named fact (fixed backend-side; render `label`).

## Guided onboarding (so it explains itself)
- A top **"How it works"** opens a 3-step popover: 1) Load history 2) Add a new result 3) Ask the
  same question to both AIs — see who's right.
- The left **Guided steps (1·2·3)** light up in order; the next action pulses subtly.
- First load (after cold-open): a one-time 3-dot coachmark on the "Load patient history" button.

## Design system (dark, cohesive, premium)
- Surfaces: `#0A0E1A` app bg, `#131A2A` cards, `#1C2536` raised; text `#E8EEF5`, muted `#94A3B8`,
  hairlines `rgba(255,255,255,.08)`.
- Accents: active/correct **teal/cyan `#22D3EE`**; framing **magenta `#FF2D95`**; danger `#EF4444`;
  replaced grey `#64748B`; disclaimer amber `#F59E0B`. Neon = emphasis only (glows, single words),
  never body text (WCAG AA on dark).
- Fonts: **Inter** (UI), **Bebas Neue** (section headers), **Monoton** (only the neon wordmark).
- Motion (Framer Motion): soft 150–250ms; the "Add new result" action animates the old fact card
  greying + the red arrow drawing; toasts on actions; `prefers-reduced-motion` respected.
- Assets in `/public/theme/` (already generated, backgrounds removed where needed): `logo-neon`,
  `coldopen-bg`, `board-cork`, `stamp-redacted/error/superseded`, `polaroid-frame`, `pushpin`,
  `mascot-groggy` (Hungover), `mascot-alert` (Total Recall), `lightleak-1/2`, `flash-burst`,
  `grain`, `og-share`, `favicon`. (Manifest: `docs/assets-manifest.md`.)
- Keep the existing cold-open `TitleSequence` (it's good) → on "Wake it up", reveal the dark console.

## Quality bar (acceptance)
- A first-time judge completes Load → Add new result → Ask, and *gets it*, with zero instructions.
- One cohesive dark look top to bottom; no stray white panels; no dev jargon visible.
- The two-assistant contrast is unmistakable; the wrong answer is clearly flagged, not confusing.
- Memory Map + Rewind + Why + The Board + Remove-mistaken-entry are all reachable and explained.
- 60fps on a laptop; AA contrast; responsive 1280–1440.

---

## API CONTRACT (bind the UI to this — base = `VITE_API_BASE`, e.g. http://localhost:8000)
All POST bodies JSON; default `patient_id:"P001"`.

- `POST /seed {patient_id}` → `{ patient_id, seeded:Fact[], held_back:[{label,text}] }`
- `POST /ingest {patient_id, text}` → `{ fact:Fact, classification, target_fact_id, reason, healed, actions[] }`
  (use the held_back item's `text` for the "Add new result" button.)
- `POST /ask {patient_id, question, mode:"total_recall"|"naive", as_of?:"YYYY-MM-DD"}` →
  `{ answer, mode, search_type, raw }`
- `GET /graph?patient_id=&as_of=` → `{ as_of, nodes:Node[], edges:Edge[] }`
- `GET /graph/cognee?patient_id=` → `{ nodes:[], edges:[] }`  (raw KG for The Board)
- `GET /why?fact_id=` → `{ fact:Fact, superseded_by:Fact|null, reason, source, date, chain:Fact[] }`
- `POST /forget {patient_id, fact_id, reason}` → `{ fact:Fact, restored:Fact|null, forgotten, cognee }`
- `GET /health` → `{ ok, cognee, ledger }`

**Fact** = `{ id, patient_id, subject, predicate, value, label, valid_from, valid_to|null,
source, status:"active|superseded|contested|retracted", superseded_by|null, confidence,
reason|null }` — **always render `label`** (plain English), never `subject: value`.

**Node** = `{ id, label, subject, value, status:"active|superseded", valid_from, valid_to|null, source }`
**Edge** = `{ source, target, type:"SUPERSEDED_BY"|"SAME_SUBJECT" }`  (render SUPERSEDED_BY as a
dashed red "replaced by" arrow; SAME_SUBJECT as a faint grey link).

Tip for the tool: keep components small, fetch with `fetch()` + the base URL, no auth. Match the
field names above exactly so it drops into the existing FastAPI backend with no changes.
