# Phase 3 — Frontend: split-chat + graph + scrubber + live heal [TIER-1 COMPLETE]

> Goal: the clinical-pro UI that makes a judge stop scrolling. Guided demo + free chat,
> live heal-on-click, time-scrubber, react-force-graph-2d.
>
> Inputs: Phase 2 API running on :8000.

## A. Stack & setup
- `npm create vite@latest frontend -- --template react-ts`
- Tailwind v4 + shadcn/ui; TanStack Query (server state); zustand (UI state: patient, as_of, mode).
- `react-force-graph-2d`, `lucide-react` (icons), `sonner` (toasts).
- `VITE_API_BASE=http://localhost:8000`.

## B. Design system (clinical-pro, calm & trustworthy)
- Palette: bg `slate-50`/white; text `slate-900`/`slate-600`; **one accent** `teal-600` (active facts, primary actions); superseded = `slate-400`; warning amber for disclaimer; danger red ONLY for the naive/stale answer callout.
- Type: Inter; clear scale (text-sm body, text-lg section, text-2xl title). Generous spacing (p-4/6, gap-4). Rounded-xl cards, subtle border, minimal shadow. No gradients/neon.
- Motion (Framer Motion or CSS): node grey-out transition ~400ms; "contradiction detected" toast; gentle fade on graph refetch. Purposeful, not flashy.
- Accessibility: labels, focus rings, color-not-only status (icon + label on superseded).

## C. Layout (single screen, 3 zones)
```
┌ Header: "Total Recall" · amber DisclaimerBanner ────────────────────────────┐
├ Left (controls)        │ Center (split chat)        │ Right (graph) ─────────┤
│ PatientPanel (P001)    │ SplitChat:                 │ GraphTabs:             │
│ ScenarioControls:      │  ┌ Total Recall ┐┌ Naive ┐ │  [Fact Timeline]       │
│  • Seed baseline       │  │  answers...  ││ stale  │ │  [Cognee Knowledge]    │
│  • ▶ Ingest: "allergy  │  └──────────────┘└────────┘ │ GraphView (force-2d)   │
│     cleared" (LIVE HEAL)│ Shared input + PresetChips │ TimeScrubber (date)    │
│  • Reset               │                            │ → click node → WhyDrawer│
└─────────────────────────────────────────────────────────────────────────────┘
```

## D. Components
| Component | Responsibility |
|---|---|
| `AppShell` | layout, header, disclaimer |
| `DisclaimerBanner` | amber "Demo only · synthetic data · not medical advice" |
| `PatientPanel` | shows P001 + current active-fact summary (from /graph) |
| `ScenarioControls` | buttons: Seed, Ingest-contradiction(s) [live heal], Reset; calls API + toasts |
| `SplitChat` | two `ChatPane`s (total_recall, naive) sharing one input |
| `ChatPane` | message list, loading spinner, renders answer; naive answers get a red "⚠ stale" badge when they differ |
| `PresetChips` | one-click: "Allergic to penicillin?", "BP medication now?" |
| `GraphTabs` | toggle Fact-Timeline / Cognee Knowledge |
| `GraphView` | react-force-graph-2d; color by status; dashed SUPERSEDED_BY; click→WhyDrawer |
| `TimeScrubber` | slider min(valid_from)…today; sets `as_of`; refetches /graph |
| `WhyDrawer` | shows /why trace: superseded on DATE by SOURCE, reason, link to superseding node |

## E. Key interactions
1. **Seed:** Seed button → POST /seed → graph shows baseline (allergy active).
2. **Live heal:** "▶ Ingest: allergy cleared" → POST /ingest → toast "Contradiction detected — penicillin allergy superseded (2026-03-02)" → invalidate /graph query → allergy node animates to grey + dashed `SUPERSEDED_BY` edge appears.
3. **Contrast:** click preset "Allergic to penicillin?" → both panes POST /ask (mode each) → Total Recall "No — cleared 2026-03-02", Naive "Yes — allergic" with red ⚠ badge.
4. **Scrub:** drag to Feb → allergy active; drag to now → superseded.
5. **Why:** click allergy node → drawer explains.

## F. react-force-graph-2d config notes
- `graphData={{nodes,edges}}` from /graph; map edge `type` → `color`/`linkLineDash` ([4,2] for SUPERSEDED_BY).
- `nodeCanvasObject`: draw circle (teal active / slate-400 superseded) + label (subject:value). Superseded → add small "⊘" + reduced opacity.
- `cooldownTicks`, fixed small graph; disable heavy physics for stability.
- On `as_of` change, recompute node status client-side OR refetch (refetch = simplest, matches /graph contract).

## G. Steps
1. Scaffold Vite+TS+Tailwind+shadcn; add deps; `api/client.ts` (typed fetch wrappers per Phase-2 contracts) + TanStack Query hooks.
2. AppShell + DisclaimerBanner + design tokens.
3. GraphView + TimeScrubber wired to /graph.
4. SplitChat + ChatPane + PresetChips wired to /ask.
5. ScenarioControls (seed/ingest/reset) + toasts + query invalidation (live heal).
6. WhyDrawer wired to /why.
7. GraphTabs + Cognee Knowledge view (/graph/cognee).
8. Polish: loading/empty states, responsive at ~1280px (demo resolution).

## H. Acceptance (verify with preview tools — screenshot each)
- Preset allergy question: Total Recall correct, Naive stale (red badge). [money shot]
- Ingest button heals live: allergy node greys + dashed edge appears, toast fires.
- Scrubber: ≥2 dates visibly change the graph.
- Why drawer: correct date/source/reason.
- Cognee Knowledge tab renders the entity graph.
- Looks clinical-pro (clean, calm), no console errors.

**→ End of Phase 3 = complete, submittable Tier-1 project. Record an insurance screen-capture now.**

## I. Risks
- react-force-graph SSR/Vite quirks → it's client-only; dynamic import if needed.
- Graph re-layout jitter on refetch → freeze node positions (store x/y) or use low cooldown.
- API latency → spinners + disable buttons while pending.

## Done → `start Phase 4`.

---

## J. Backend reality check (post Phase-2 / 2b) — FOLD THESE INTO THE ABOVE

The Phase-2 API shifted during build. The frontend must match what actually shipped:

### J1. Endpoints + contracts = `app/api/dto.py` is the source of truth
`api/client.ts` types must mirror `dto.py` exactly. Endpoints now are:
`POST /seed`, `POST /ingest`, `POST /reset`, **`POST /forget`**, `POST /ask`,
`GET /graph`, `GET /graph/cognee`, `GET /why`, `GET /health`.

### J2. Smart `/ask` returns `search_type: "TEMPORAL"` (NOT GRAPH_COMPLETION)
GRAPH_COMPLETION was unreliable (returned garbage like "Got it."), so the smart
path forces TEMPORAL. `ChatPane` should show the `search_type` chip
("TEMPORAL" for total_recall, "RAG_COMPLETION" for naive) — it doubles as the
"which Cognee primitive" label for judges.

### J3. NEW capability — past-tense time-travel in chat (tie scrubber → /ask `as_of`)
History is now RETAINED (supersession no longer forgets). So `/ask` with
`as_of=<scrubber date>` answers past-tense correctly:
- now → "No — penicillin allergy was cleared on 2026-03-02"
- `as_of=2026-02-15` → "Yes, was allergic as of 2026-02-15"
**Wire the TimeScrubber's `as_of` into the total_recall `/ask` call** (not just
`/graph`). Add a third PresetChip: "Allergic **back in February**?" This makes the
time-machine story land in the chat, not only the graph. Show the `as_of` the
answer was computed for.

### J4. NEW control — Retract (entered in error) → `POST /forget`
Add a button to `ScenarioControls`: "⌫ Retract: diabetes (entered in error)".
- Body `{patient_id, fact_id, reason}` (get `fact_id` from the seeded fact / a node).
- On success: toast "Retracted — removed from memory (entered in error)";
  invalidate `/graph` + `/graph/cognee` → the node **vanishes** (distinct from the
  grey-out of supersession). If `restored` is non-null, toast "prior fact restored".
- This is the visible proof of Cognee's `forget()` primitive. Pair it in the demo
  with supersession to contrast "retained vs removed".

### J5. Node status handling
`/graph` status is `active | superseded` (retracted facts are EXCLUDED, not
greyed — forget makes them disappear). `GraphView`: teal=active, slate-400+⊘=
superseded, dashed `SUPERSEDED_BY`. No "retracted" color needed (they're gone).

### J6. Naive baseline is a frozen pre-heal snapshot (server-side)
The frontend does nothing special — `mode:"naive"` already hits the frozen
`naive_baseline` dataset server-side. Just render the contrast + red ⚠ badge.

### J7. Graph lib note
MASTER_PLAN + this phase use **react-force-graph-2d** (ARCHITECTURE.md's older
"Sigma.js" line is superseded). Build with react-force-graph-2d.

---

## K. Theme layer — "Neon-Noir Clinic" (full spec in `docs/theme-hangover.md`)
Additive skin/copy/motion on top of everything above. Build the functional UI first, then apply.
- **Dual register:** dark neon-noir framing (cold-open, header, The Board, Hungover pane) → light clinical-pro working UI. Neon is emphasis-only (WCAG: never body text).
- **Color tokens / fonts / motion:** copy the hex tokens + Inter/Bebas Neue/Monoton + the 8 motion specs from theme-hangover.md §3–5 into the Tailwind `@theme` + CSS.
- **New component:** `ColdOpen` (neon flicker logo → "Your AI woke up with no memory…" → **Wake it up** → lights-on whiteout wipe to dashboard).
- **Re-skin existing (no logic change):** Naive pane → "🥴 Hungover AI · RAG_COMPLETION" (desaturated + faint magenta); Total Recall pane → "🧠 Total Recall · TEMPORAL"; supersede → REDACTED stamp; TimeScrubber label "Rewind the night"; Cognee-Knowledge tab → "The Board" (corkboard + red string).
- **Assets:** ALL generated + background-removed already — build-ready in `assets/theme/` (transparent props + scene/overlay assets). **First step of Phase 3:** `copy assets/theme/* → frontend/public/theme/`, reference as `/theme/<name>.png`. Full filename→component→usage map in `docs/assets-manifest.md`.
- **Acceptance (theme):** cold-open → lights-on transition works; both panes read on-theme; one preset + heal demo still passes; `prefers-reduced-motion` disables flicker/develop; AA contrast holds; looks premium, not gimmicky.

---

## L. Cinematic / movie-feel layer (spec: theme-hangover.md §11)
Build after §K. Pure presentation — no engine/API/logic change. Three new components + overlays.
- **`TitleSequence`** (the 6-sec cold-open; supersedes the simple ColdOpen in §K): letterbox in → studio card → neon-logo flicker → taglines → **[Wake it up]** → record-scratch + light-leak wipe → letterbox out → dashboard. Skippable; plays once via `sessionStorage`.
- **`CinematicLayer`** (fixed, `pointer-events:none`, app-wide): letterbox bars (2.39:1 cold-open / thin via "Cinema mode" toggle), film grain (`grain.png` OR SVG `feTurbulence` ~5%), vignette (radial gradient), chromatic aberration on neon headings only (CSS red/cyan `text-shadow`).
- **`FilmTransition`** (light-leak PNG, `mix-blend-mode:screen`, 500–700ms) on cold-open→dashboard and tab→The Board.
- **Photo-reel reveal:** reveal/Board fact cards = flash-lit polaroids (`polaroid-frame.png`+`pushpin.png`+rotate); scrubber-drag → `flash-burst.png` overlay then CSS "develop" (filter sepia/contrast/blur→normal 600ms); supersede → REDACTED slam + red-string draw.
- **Where to integrate:** `TitleSequence` gates the app at `App.tsx` root; `CinematicLayer` wraps `AppShell`; `FilmTransition` triggers on the cold-open "wake up" and `GraphTabs` change; photo-reel styling lives in `GraphView`/reveal cards + `TimeScrubber` onChange.
- **Assets:** `title-bg, lightleak-1/2, flash-burst, grain, (opt) flash-frame-1` in `frontend/public/theme/`. Letterbox/vignette/chromatic = CSS, no asset.
- **a11y/perf:** gate flicker/grain-jitter/flash/chromatic/film-burn behind `prefers-reduced-motion` (static fallback OK); animate transform/opacity only; pause overlays on hidden tab; target 60fps on the laptop; "Skip intro" always present.
- **Acceptance (cinematic):** intro plays once → wake-up wipe → dashboard; grain/letterbox/vignette read "film" not "noisy"; photo-reel flash+develop fires on scrub; reduced-motion path clean; demo flow + AA contrast still pass.
