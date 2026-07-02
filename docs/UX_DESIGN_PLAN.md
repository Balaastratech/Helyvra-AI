# UX & UI DESIGN PLAN — Total Recall Clinical Copilot

> The dedicated design plan for an **exceptional**, top-tier doctor-facing experience. Companion to
> `CLINICAL_COPILOT_PLAN.md` (what we build) — this is *how it looks, moves, and feels*. The current
> frontend is a dev console; this replaces that feel entirely while honoring the established
> **dual-register** theme (`theme-hangover.md`).

---

## 0. Direction (the one decision everything hangs on)

**Dual-register, resolved for clinical trust:**

| Register | Where it lives | Job | Feel |
|---|---|---|---|
| **Clinical (light, premium)** | the entire doctor workspace — dashboard, pre-visit brief, chat, cards, tabs | be a tool a real doctor trusts and enjoys | calm, precise, warm, confident |
| **Noir (dark, cinematic)** | cold-open title, section dividers, the **Compare** (naive-villain) proof, the demo video | set the Hangover stakes + memorability | moody, neon, dramatic |

Why this split (researched, not taste): clinician studies show *transparency and calm earn trust;
overconfident/dramatic presentation triggers automation-bias and skepticism*. The Hangover framing is
a brilliant hook for judges — but it belongs at the **edges**, never on the clinical answer. This is
exactly what `theme-hangover.md §1` intended ("dark neon morning-after → light clinical clarity"); we
commit to it fully and drop the "make the whole app dark" line from `design-brief.md` (that was for the
old single-screen demo and is the root of the current "stray white panels" problem).

**North-star feel:** *the calm of a great clinical tool + the confidence of a senior colleague who
shows their reasoning.* Quality bar to study (feel, copy nothing): **Linear** (dense yet calm,
keyboard-first), **Stripe** (trust through clarity + restraint), **Arc/Things** (motion warmth and
restraint), **Dragon Copilot / Epic** (clinical legitimacy, card patterns).

**Anti-slop guardrails (hard rules):**
- No flat gray cards-nested-in-cards. No purple "AI gradient" cliché. No emoji-as-icon in clinical UI.
- Real type scale (clear display→body→caption steps), generous whitespace, one accent color.
- Every motion has a *reason* (state change, spatial continuity, attention) — never decoration.
- Color is never the only signal (icon + label + color, always — a11y + clinical safety).
- Density is a feature: doctors scan. Information-dense but never cluttered (Linear, not Bloomberg).

---

## 1. Design system

### 1.1 Color — clinical base, restrained accent, semantic status

```css
/* CLINICAL SURFACES (the workspace) */
--bg:            #FBFCFD;  /* near-white, faint cool */
--surface:       #FFFFFF;
--surface-sunken:#F4F7F9;  /* sidebars, sunken wells */
--surface-raised:#FFFFFF + shadow (see elevation)
--border:        #E6EBF0;
--border-strong: #CFD8E3;
--text:          #0C1521;  /* near-black, warm */
--text-muted:    #5A6B7B;
--text-faint:    #8A99A8;

/* ACCENT (one, used with intent) */
--accent:        #0E8C84;  /* refined teal — primary actions, active, "Total Recall" */
--accent-soft:   #E6F4F2;  /* accent wash for selected rows / chips */
--accent-strong: #0A6F68;

/* SEMANTIC SEVERITY (clinical cards — the safety system) */
--critical:      #D7263D;  --critical-soft:#FCEBED;  /* allergy / immediate harm */
--warning:       #C77700;  --warning-soft: #FBF1E2;  /* follow-up gap / risk */
--info:          #0E8C84;  --info-soft:    #E6F4F2;  /* helpful note */
--success:       #1F9D6B;  --success-soft: #E7F5EE;  /* resolved / confirmed */

/* CERTAINTY (the honesty system) */
--settled:       var(--text);        /* a settled, current fact reads as normal text */
--contested:     #C77700;            /* conflict — amber, shown as a split, never one line */
--unverified:    #8A99A8;            /* low-confidence — quiet gray "unverified" tag */

/* NOIR (framing only) */
--noir-bg:#0A0E1A; --noir-surface:#131A2A; --noir-text:#E8EEF5; --noir-muted:#94A3B8;
--neon-magenta:#FF2D95; --neon-cyan:#22D3EE; --neon-gold:#FFB020;
```
Neon usage cap unchanged: ≤5% of pixels, framing only, never body text, AA-safe.

### 1.2 Typography
- **Inter** — all workspace UI and body. Tight tracking on headings.
- **Inter Tight / Inter Display** — large workspace headings (patient name, section titles) for a
  crisp editorial feel without leaving the family.
- **JetBrains Mono / ui-monospace** — data that benefits from tabular alignment: MRN, dates, lab
  values + units, dosages. (Numbers a doctor scans should be monospaced and tabular-nums.)
- **Bebas Neue + Monoton** — cinematic register ONLY (cold-open, dividers, video). Never in the
  workspace.
- Scale (rem): display 2.0 / h1 1.5 / h2 1.25 / h3 1.0625 / body 0.9375 / caption 0.8125, with a
  comfortable 1.5 body line-height. Lab/data rows use tabular-nums.

### 1.3 Elevation, radius, spacing
- **Radius:** 10px cards, 8px controls, 6px chips, full for pills/badges. Consistent, slightly soft.
- **Elevation (soft, layered — never harsh):** `0 1px 2px rgba(12,21,33,.04), 0 4px 12px
  rgba(12,21,33,.06)` for raised cards; modals add a third, wider blur. No hard 1px-black borders as
  the primary separator — use `--border` hairlines + elevation.
- **Spacing:** 4px base scale; generous section padding (24–32px), comfortable card padding (16–20px),
  8–12px intra-group. Whitespace is the premium signal.

### 1.4 Iconography
- One line-icon set (Lucide — already a likely dep). 1.5px stroke, consistent sizing. Clinical icons
  (allergy, pill, lab, family, vitals) drawn from the same set; severity conveyed by color + a shape
  cue (filled dot critical / ring warning / line info), never color alone.

---

## 2. Information architecture & navigation

```
Cold-open (once/session, skippable)  →  Login (simulated, 1 tap)  →  ┌─────────────┐
                                                                     │  DASHBOARD  │  ← home
                                                                     └─────┬───────┘
                                                  resolve / search / ⌘K   │
                                                                     ┌─────▼────────────┐
                                                                     │ PATIENT WORKSPACE│
                                                                     │ chat · tabs · MM │
                                                                     └──────────────────┘
```

- **Global:** slim top bar — wordmark (small, calm — not the neon one in-workspace), the **patient
  context chip** (when in a patient), doctor avatar/role, a health pill. Amber disclaimer strip stays.
- **⌘K command palette** (a "best-in-class" touch): jump to any patient, "open today's first
  patient," "upload a record," "ask across patients." Keyboard-first like Linear. This single feature
  makes it feel professional instantly.
- **Patient context is sacred:** the chip (name · age · sex · MRN · allergy badge · risk badge) is
  always visible inside a patient. Switching patients triggers an explicit, animated context-close
  ("Closing Rahul Sharma… Now viewing Priya Mehta") so a mix-up is impossible — this is safety-as-UX.

---

## 3. Screen-by-screen (the exceptional flow)

### 3.1 Cold-open (keep, refine) — *noir*
Existing `TitleSequence` is good; keep it, tighten timing to ≤5s, ensure "Skip" is obvious, play once
per session. Ends on the "lights-on" wipe into the **light** dashboard (the sober reveal — now the
contrast actually lands because the workspace really is light).

### 3.2 Login (simulated) — *clinical*
One calm screen: pick a doctor (avatar + name + specialty), role shown. No password theater. Sets
session + audit identity. Sub-2-second. (Honest: "Demo login — synthetic data.")

### 3.3 Dashboard — the command center — *clinical*
**Not a chat box.** A calm, scannable command center:
- **Today's patients** — a clean list/cards: name, age/sex, reason for visit, and a compact
  **risk pip row** (red/amber dots = open critical/warning flags) so the doctor sees where to look
  first. Click → workspace.
- **Critical reminders strip** — cross-patient, top: "3 patients have unresolved critical flags."
  Each chip → straight to that patient's flagged card.
- **Search / ⌘K** — name, MRN, phone. Front and center.
- **Recent patients** — quick re-entry.
- **Upload a record** — a real drop-zone ("drop a PDF, lab, or FHIR file — I'll file it to the right
  patient"); no patient pre-selection.
Empty state teaches: "No patients loaded — drop a record or pick a demo patient."

### 3.4 Patient resolve / disambiguation — *clinical*
Typing "Rahul Sharma" with duplicates → a **disambiguation card**, never an instant answer:
> Two matches — select the patient:
> • Rahul Sharma · 52M · MRN 10291 · last visit 12 Jun 2026
> • Rahul Sharma · 31M · MRN 20882 · last visit 04 May 2026

Selecting locks the context chip with a satisfying settle animation. This *is* the safety story, made
visible.

### 3.5 Pre-visit brief — the hero moment — *clinical*
On opening a patient, **before** the chat, the brief assembles (a calm, staged 600–900ms build — not
flashy; like a chart being laid out):
- **One-screen summary** (left): conditions · current meds · allergies (red if active) · family ·
  recent concern · lifestyle. Dense, scannable, monospaced values.
- **"Top 3 things not to miss"** (right) — the check-engine cards, severity-coded, each with a
  one-line reason + a citation chip. This is the single most important screen in the product; it must
  feel authoritative and calm, like a great resident's handoff.
A "Start consultation →" affordance drops into the chat with context loaded.

### 3.6 Patient workspace — *clinical*
```
┌ sidebar ─┬ top: «Rahul Sharma · 52M · MRN 10291 · 🔴 Penicillin · ⚠ CV risk»  health ●
│ search   ├──────────────────────────────────┬──────────────────────────────┐
│ today    │  CHAT (primary)                  │  RIGHT RAIL                   │
│ recent   │   live trace · cited answers ·   │  Doctor might miss (cards)    │
│ + new    │   approval cards · certainty     │  Missing data                 │
│          │                                  │  Follow-up tasks              │
│          ├ tabs: Timeline · Records · Labs · Meds · Family · Alerts          │
└──────────┴──────────────────────────────────┴──────────────────────────────┘
```
- **Chat is primary**, but the right rail keeps the "doctor might miss" cards persistent (not buried).
- **Tabs** reuse existing components: **Timeline/Memory-Map** = `MemoryGraph`+`RewindSlider`+`WhyPanel`
  (the photo-reel rewind is reused as the timeline scrubber — genuinely good, keep it). Records/Labs/
  Meds/Family render the structured FHIR data as clean tables.

### 3.7 The signature interactions
- **Ask** ("what should I know before this patient?") → live trace ("Checking memory… reviewing 3
  conditions, 2 allergies…") → a structured answer card: **Answer · Reason · Evidence · Confidence ·
  What's missing · Suggested action**, citations clickable.
- **Order check** ("can I prescribe amoxicillin?") → the agent runs the prescribe check **before**
  any write → a **critical allergy card** slides in with the cross-reactivity reason + the 2021
  discharge-summary citation. The "stop before harm" moment, beautifully and calmly rendered.
- **Upload mid-consult** → drop a lab PDF → live "filing… extracted HbA1c 8.9%… this updates an
  earlier value" → the affected card updates in place (the self-heal, shown).
- **Correction** ("that allergy was entered in error") → an **approval card** framed as *fixing a
  record* → on confirm, the fact visibly retires with an audit note.
- **Compare proof** (the "/Compare" tab) — *noir*: the naive "Hungover AI" says "amoxicillin is fine"
  (red, dangerous) vs Total Recall "no — penicillin allergy." This is the only place drama is welcome;
  make it cinematic.

---

## 4. Motion language
- **Principle:** transform/opacity only (GPU, 60fps on the laptop); 150–250ms for UI, 400–900ms for
  signature reveals; spring for settles, ease-out for entrances. All under
  `prefers-reduced-motion: no-preference`, with static fallbacks.
- **Signatures:** lights-on wipe (cold-open→dashboard); context-chip settle on patient select;
  pre-visit brief staged assembly; clinical card slide+severity-pulse (critical pulses once, calmly);
  citation chip → source-doc viewer shared-element transition; timeline photo-reel develop (reuse);
  supersede REDACTED stamp + red-string draw (reuse, Compare/Board only).
- **Restraint rule:** the clinical answer never bounces, sparkles, or types-out dramatically. Calm =
  trustworthy. Save flourish for framing.

---

## 5. Microcopy & voice
- **Voice:** a precise, honest senior colleague. Confident about evidence, explicit about doubt.
- **Honesty rules:** contested facts shown as a conflict ("two records disagree…"), never one
  confident line; low-confidence tagged "unverified"; missing data named, not hidden; never a
  diagnosis beyond evidence; treatment phrased "for your review."
- **No dev jargon in the clinical UI** (keep the existing dev→human rewrite table; technical term only
  as a hover tooltip for credibility). Playful copy is allowed ONLY on non-clinical actions
  (loading the demo, the cold-open) — never on a medical answer.

---

## 6. Component inventory (new + reused)
**New:** `Dashboard`, `TodayList`, `CriticalStrip`, `CommandPalette`, `PatientResolver`,
`PatientContextChip`, `PreVisitBrief`, `ClinicalCard` (severity-coded, cited, dismissible),
`AnswerCard` (the 6-part structured answer), `RightRail`, `SourceDocViewer` (page-highlighted),
`ApprovalCard`, `AgentTrace`, `CertaintyBadge`, `LoginPicker`.
**Reused (re-skinned to clinical-light):** `MemoryGraph`, `RewindSlider`, `WhyPanel`, `SplitChat`
(→ Compare tab), `DisclaimerBanner`, `DocumentViewer`, cinematic `TitleSequence`/`CinematicLayer`
(framing only).
Every component specs: default · hover · focus · loading (skeleton, not spinner where possible) ·
empty (teaches) · error (honest, recoverable) · reduced-motion.

---

## 7. Responsive & accessibility
- Target desktop 1280–1600 (clinical tools are desktop); graceful down to 1024. Not mobile-first
  (out of scope), but no horizontal scroll.
- WCAG AA everywhere (verified contrast on the tokens above); full keyboard path (⌘K, tab order,
  focus rings using `--accent`); ARIA on cards/tabs/dialogs; reduced-motion honored; color never the
  sole signal.

---

## 8. Build approach (maps to CLINICAL_COPILOT_PLAN Day 4)
- **Tailwind v4 `@theme`** tokens from §1 (replace the current mixed dark/light tokens). **shadcn/ui**
  primitives (button/card/dialog/tabs/command) re-skinned to clinical-light. **Framer Motion** for §4.
- **Refactor, don't rebuild blind:** keep `MemoryGraph`/`RewindSlider`/`WhyPanel` (logic good,
  re-skin), replace the page shells (`ConsolePage`/`BoardPage` console feel) with `Dashboard` +
  `PatientWorkspace`. The "Inspector drawer" idea is dropped (UPGRADE_PLAN audit) — trace is inline.
- **Sequence within Day 4:** tokens+shell → dashboard+resolve → pre-visit brief → workspace chat+cards
  → tabs (reuse) → Compare/cinematic polish.
- **Cut order (never cut the brief or the cards):** ⌘K palette → Records/Labs/Meds sub-tabs (keep
  Timeline+Alerts) → cinematic dividers → cold-open refinements.

## 9. Acceptance bar (when is it "exceptional")
1. A doctor lands, opens a patient, and the pre-visit brief makes them say "this is genuinely useful"
   in 5 seconds — calm, dense, authoritative.
2. Zero stray white-on-dark or dark-on-light mismatches; one cohesive light-clinical system top to
   bottom; noir only at the framed edges.
3. The critical allergy stop, the citation→source jump, and the patient-switch context-close each feel
   crafted, not generic.
4. 60fps on the IdeaPad; AA contrast; full keyboard; reduced-motion clean.
5. A judge feels the Hangover hook (cold-open + Compare) AND would trust it with a patient.
