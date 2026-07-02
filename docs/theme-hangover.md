# THEME — "Neon-Noir Clinic" (Hangover × clinical, fully designed)

> The complete visual identity. Blends the hackathon's Hangover theme with the
> patient/health domain WITHOUT losing clinical trust. Additive skin/copy/motion only —
> no engine/API/data change. Honors the shipped build (Hungover AI vs Total Recall panes,
> `search_type` chips, supersede=grey, retract=vanish).

## 1. The idea (why it's cohesive, not a costume)
The Hangover's real mechanic = wake up with **no memory** → reconstruct the **true timeline**
from contradictory clues → **the photo-reel reveal**. That IS Total Recall. So the theme is a
**narrative spine**, not decoration:

> **Dark neon "morning-after"** (amnesia, confusion) → the app **"sobers up"** → **light clinical clarity** (truth).

This gives us a **dual-register** design — which also solves the WCAG problem (neon fails body-text contrast): neon lives only in the *dark framing surfaces*; the *working clinical UI* stays light and accessible.

## 2. Two registers (the whole system in one table)
| | NOIR register ("hungover / the night") | CLINICAL register ("sober / the truth") |
|---|---|---|
| Where | Cold-open, header band, **The Board** tab, Hungover-AI pane accents, loading | Dashboard, answers, forms, Total Recall pane, Fact-Timeline graph |
| Mood | dark, neon, mysterious | light, calm, trustworthy |
| Job | set stakes + theme | be a believable medical tool |

## 3. Color tokens (actual hex — drop into Tailwind v4 `@theme`)
```css
/* CLINICAL (default working UI) */
--bg:            #F8FAFC;   /* slate-50  */
--surface:       #FFFFFF;
--border:        #E2E8F0;   /* slate-200 */
--text:          #0F172A;   /* slate-900 */
--text-muted:    #475569;   /* slate-600 */
--active:        #0D9488;   /* teal-600  — active facts, Total Recall, primary CTA */
--active-glow:   rgba(13,148,136,.25);

/* NOIR (dark framing surfaces) */
--noir-bg:       #0A0E1A;   /* near-black navy */
--noir-surface:  #131A2A;
--noir-text:     #E8EEF5;   /* mint-tinted off-white (never pure #fff) */
--noir-muted:    #94A3B8;   /* slate-400 */

/* NEON ACCENTS (emphasis only: single words, lines, glows — NEVER body text) */
--neon-magenta:  #FF2D95;   /* primary neon — wordmark, "Hungover AI" label */
--neon-cyan:     #22D3EE;   /* secondary neon — Total Recall accent in noir, scrubber */
--neon-gold:     #FFB020;   /* "the reveal" / photo-reel highlight */

/* SEMANTIC STATUS (consistent everywhere) */
--stale:         #EF4444;   /* naive/wrong answer ⚠ */
--string:        #E11D48;   /* red evidence string = SUPERSEDED_BY on The Board */
--warn:          #F59E0B;   /* disclaimer amber (stays serious) */
```
**Status semantics:** active = teal/cyan-glow · superseded = slate-400 + REDACTED stamp (clinical) / red string (board) · retracted(forget) = **vanish** · stale(naive) = red. (Matches phase-3 J4/J5.)

**WCAG rules:** body copy = `--text` on light or `--noir-text` on noir (both pass). Neon only on ≥18px bold, or as non-text glow. Everything works if neon were greyscale (color is never the only signal).

## 4. Typography (free Google Fonts)
- **Inter** — all functional/body UI (accessible).
- **Bebas Neue** — cinematic marquee headlines (cold-open title, section dividers, video). Trailer-grade.
- **Monoton** — the literal neon-tube logo glyphs ONLY (the wordmark + cold-open). Never for reading.
Pairing: Monoton (logo) → Bebas Neue (headlines) → Inter (everything else).

## 5. Motion specs (actual techniques; all wrapped in `@media (prefers-reduced-motion: no-preference)`)
1. **Neon flicker** (cold-open logo, header wordmark): CSS `@keyframes` toggling multi-layer `text-shadow` + `opacity` at `0,19,21,23,25,54,56,100%` (standard neon-flicker keyframe set). Magenta glow stack.
2. **"Lights on" sober transition** (cold-open → dashboard): on Enter, a brightness/whiteout wipe (800ms) from `--noir-bg` to `--bg`. The narrative hinge.
3. **Live heal — red string draws**: SVG line `stroke-dasharray`/`stroke-dashoffset` animated 0→full, 500ms ease-out, between the superseded and superseding cards on The Board.
4. **Supersede stamp**: REDACTED PNG scales in `scale .6→1, rotate -8deg`, 350ms spring; node desaturates `filter: grayscale(0→1); opacity 1→.45`, 400ms.
5. **Photo-reel reveal (scrubber)**: as a node becomes active while scrubbing, "polaroid develop" = CSS `filter` sepia/contrast→normal + opacity, 600ms. Dragging the scrubber = the camera reveal.
6. **Toasts**: slide-up + faint neon `box-shadow` glow keyed to event (magenta "context recovered", red "stale", gold "reveal").
7. **Loading copy** — split by gravity (per content guidance): playful only on non-answer actions (seed/board) — "Piecing together the night…", "Checking the evidence…"; **plain** for the actual clinical answer — "Retrieving records…". Never joke on a medical answer.
8. **Graph node hover**: cyan glow ring.

## 6. Component-by-component theming (maps to existing plan + J-deltas)
| Component | Theme treatment |
|---|---|
| **Cold-open** (new, Phase 3) | Noir screen, Monoton neon logo flickers on, Bebas tagline *"Your AI woke up with no memory of last night."* → sub *"It still thinks the patient is allergic to penicillin."* → **[ Wake it up ]** → lights-on wipe to dashboard. |
| Header band | Thin noir strip: neon wordmark + one cyan hairline. Amber disclaimer stays. |
| **Hungover AI pane** (naive) | Slightly desaturated card, faint magenta glow, 🥴 label `Hungover AI · RAG_COMPLETION`. Wrong answer gets red ⚠ stale badge. |
| **Total Recall pane** (smart) | Crisp clinical card, teal, 🧠 label `Total Recall · TEMPORAL` (show `search_type` chip per J2). |
| Fact-Timeline graph | Clinical/light. active=teal, superseded=slate-400 + ⊘, dashed `SUPERSEDED_BY`. |
| **The Board** tab (Cognee Knowledge) | Noir register: corkboard texture bg, facts as polaroid/evidence cards w/ pushpins, **red string** = SUPERSEDED_BY. The "investigation wall." |
| TimeScrubber | Cyan neon track; label "Rewind the night"; drives both `/graph` and total_recall `/ask?as_of` (J3). |
| Retract button | "⌫ Retract: diabetes (entered in error)" → node **vanishes** (J4); toast gold. |
| WhyDrawer | Clinical card + a small "🧠 Cognee's own reasoning agrees" block. |

## 7. Asset checklist + Gemini image prompts
Generate each in Gemini (Nano-Banana/Imagen on your Vertex or the Gemini app). **Shared art direction** (paste atop every prompt for consistency):
> *Art direction: cinematic neon-noir meets clean medical UI. Deep navy-black background (#0A0E1A), neon magenta (#FF2D95) + neon cyan (#22D3EE) accents, occasional warm gold (#FFB020). Moody, premium, high contrast, subtle film grain. NOT cartoonish, NO real celebrities, NO copyrighted logos or movie stills. Minimal, elegant.*

Save returned files to `frontend/public/theme/` with the **exact filenames** below so I can wire them in.

| # | File | Aspect | Prompt (append to art direction) |
|---|---|---|---|
| A | `logo-neon.png` | 1024×512, plain black bg | "A neon-tube sign reading **'TOTAL RECALL'**, glowing magenta with cyan underglow, realistic glass-tube look, switched on, faint reflection, isolated on solid black for easy keying." |
| B | `coldopen-bg.png` | 1920×1080 | "Abstract morning-after Vegas hotel suite at dawn, blurred neon city bokeh through a window, scattered soft light, empty and quiet, deep navy with magenta/cyan glints, cinematic, no people, no text." |
| C | `board-cork.png` | 1920×1080, tileable | "Dark moody corkboard texture under a warm investigation spotlight, subtle vignette, fine grain, empty, top-down, premium noir." |
| D | `stamp-redacted.png` | 800×400, plain white bg | "A distressed red rubber-ink stamp that reads **'REDACTED'**, slightly rotated, worn texture, isolated on pure white, high contrast for background removal." |
| D2 | `stamp-error.png` | 800×400, plain white bg | "A distressed red rubber-ink stamp that reads **'ENTERED IN ERROR'**, worn ink, isolated on pure white." |
| E | `polaroid-frame.png` | 600×720, transparent or white | "An empty white polaroid photo frame, slight shadow, clean, top-down, isolated on white, room for a photo in the window." |
| F | `pushpin.png` | 256×256, plain white bg | "A single glossy red push-pin seen from front-top angle, soft shadow, isolated on pure white." |
| G | `mascot-groggy.png` | 768×768, transparent/white | "A minimal friendly robot mascot just waking up, groggy, one eye half-open, tiny question mark, flat modern vector, navy + magenta accents, isolated on white. Subtle, not cartoonish." |
| H | `og-share.png` | 1200×630 | "Hero share image: neon 'TOTAL RECALL' sign (magenta/cyan) on deep navy, small tagline space, a faint corkboard-with-red-string motif on one side, premium cinematic. Leave the lower-left clear for overlaid text." |
| I | favicon | 512×512 | "A minimal app icon: a glowing magenta brain-with-a-clock-hand mark on deep navy, simple, recognizable at small size, isolated." |

Tip: for D/D2/E/F/G/I generate on **plain white/black** then run background removal (or ask Gemini for transparent PNG). I'll wire whatever you send back.

Optional motion asset (skip Gemini): grab a subtle looping **neon line / scanline** Lottie from lottiefiles.com (search "neon loader") → `frontend/public/theme/neon-loader.json`.

## 8. Narrative spine (how a judge experiences it, start→finish)
1. **Cold-open (noir):** neon logo flickers; *"Your AI woke up with no memory of last night… it still thinks the patient is allergic to penicillin."* → **Wake it up**.
2. **Lights-on wipe → clinical dashboard (light):** the sobering moment.
3. **Contrast:** 🥴 Hungover AI says "allergic" (red ⚠) · 🧠 Total Recall says "no — cleared 2026-03-02".
4. **Live heal:** ingest the clue → REDACTED stamp + red string draws → "Context recovered."
5. **The Board (noir):** corkboard + red string = the investigation wall (depth/Cognee graph).
6. **Rewind the night (scrubber):** polaroid-develop reveal of what was true when = the photo-reel payoff.
7. **Why:** the case file explains itself; Cognee agrees.

## 9. Accessibility & taste guardrails
- Neon ≤ ~5% of pixels; base stays clinical. Disclaimer always serious.
- All text passes WCAG AA (neon never used for paragraphs).
- `prefers-reduced-motion` disables flicker/develop; provide static fallback.
- The wink lives in framing/labels, never in clinical answers.

## 10. Where this lands in the build
- **Phase 3:** tokens, fonts, cold-open component, pane labels/treatments, The Board styling, stamps, scrubber label, motion. (See phase-3 "Theme layer" section.)
- **Phase 7:** video framing on the narrative spine + `og-share.png`/favicon. (See phase-7.)
- No other phase changes.

---

## 11. Cinematic / movie-feel layer (the "actual movie" feel)
Borrow the film's *devices*, never its assets. Two signatures make it read as The Hangover; the rest is generic film grammar.

### 11.1 Title sequence (cold-open · ~6s · skippable · once per session)
Beats (the `TitleSequence` component):
1. Black + faint hum → **letterbox bars** slide in to **2.39:1** (0.3s).
2. Studio card (CSS text): *"A WeMakeDevs × Cognee Production"* — small caps, fade (0.8–1.8s).
3. **Neon "TOTAL RECALL"** flickers on (Monoton + magenta glow) (2.0–3.2s).
4. Tagline (Bebas Neue): *"Your AI woke up with no memory of last night."* (3.4s).
5. Sub: *"It still thinks the patient is allergic to penicillin."* (4.4s).
6. **[ Wake it up ▸ ]** → record-scratch → **light-leak wipe** + letterbox retracts → light clinical dashboard ("lights on").
- "Skip intro" top-right; remember via `sessionStorage` so it plays once.

### 11.2 Global cinematic overlay (`CinematicLayer`, fixed, pointer-events:none)
- **Letterbox bars:** full 2.39:1 in cold-open; thin/off in app via a "Cinema mode" toggle.
- **Film grain:** `grain.png` tile OR SVG `feTurbulence`, ~5% opacity, subtle stepped jitter.
- **Vignette:** radial-gradient to near-black edges (stronger on noir surfaces).
- **Chromatic aberration:** ONLY on neon headings (CSS red/cyan `text-shadow` offsets) — never body text.

### 11.3 Film transitions (`FilmTransition`)
Light-leak PNG, `mix-blend-mode: screen`, 500–700ms, on cold-open→dashboard and switch to **The Board**.

### 11.4 Photo-reel reveal (the signature device)
- Reveal/Board fact cards render as **flash-lit polaroids** (`polaroid-frame.png` + `pushpin.png` + slight rotation).
- On scrubber drag, a node becoming active fires a **camera-flash** (`flash-burst.png` overlay) then the card **develops** (CSS `filter` sepia/contrast/blur → normal, 600ms). Dragging the scrubber = the photo reel playing = the Hangover end-credits payoff.
- Supersede heal: **REDACTED** stamp slams onto the old polaroid + **red string** draws.

### 11.5 Sound (optional in-app, ON in the demo video)
Soft hum (cold-open) · neon buzz · record-scratch on "wake up" · camera-flash click per reveal · low beat under the title. Mutable; default muted in-app.

### 11.6 Accessibility / performance
- `prefers-reduced-motion`: disable flicker, grain-jitter, flash, chromatic aberration, film-burn → static title + static grain/vignette/letterbox OK.
- Overlays animate transform/opacity only (GPU); pause when tab hidden; target 60fps on the laptop.

### 11.7 Reference films (study the *look*, copy nothing)
The Hangover (photo-reel + morning-after reveal) · **Memento** (timeline reconstruction — on-theme) · Fear and Loathing / Casino (Vegas neon grade) · Zodiac / True Detective (evidence board) · Mr. Robot (cinematic UI). **Never use real posters, logos, actor faces, or stills.**

### 11.8 New assets for this layer
`title-bg.png`, `lightleak-1.png`, `lightleak-2.png`, `flash-burst.png`, `grain.png`, (opt) `flash-frame-1.png` — prompts in `docs/image-prompts.md` ("CINEMATIC ASSETS"). Letterbox/vignette/chromatic = CSS (no asset).
