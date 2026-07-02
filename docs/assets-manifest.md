# ASSET MANIFEST — where every image lives & is used

## Locations
- **Raw generated originals:** `D:\Balaastra\ideas\total-recall\images\` (keep as backup).
- **Processed, build-ready (USE THESE):** `D:\Balaastra\ideas\total-recall\assets\theme\`
  — 7 props have **transparent backgrounds** (cut out); 13 scene/overlay assets copied as-is.
- **At Phase 3:** copy `assets/theme/*` → `frontend/public/theme/`. In code reference as `/theme/<name>.png`.

## Background-removal status
- **Transparent (cut out):** `stamp-redacted`, `stamp-error`, `stamp-superseded`, `pushpin`,
  `polaroid-frame`, `mascot-groggy`, `mascot-alert`.
- **No cutout needed:** `logo-neon`, `favicon`, `og-share`, `coldopen-bg`, `title-bg`, `noir-bg`,
  `board-cork`, `lightleak-1`, `lightleak-2`, `flash-burst`, `grain`, `flash-frame-1`, `concept-split`.
  (light-leaks + flash-burst sit on black → use CSS `mix-blend-mode: screen`, no transparency required.)

## Usage map (filename → where → component → phase)
| File | Transparent | Used for | Component / location | Phase |
|---|---|---|---|---|
| `logo-neon.png` | no | Cold-open hero sign + video thumbnail (NOT the header — header wordmark is CSS) | `TitleSequence` | 3 §L |
| `favicon.png` | no | Browser tab + PWA icon | `index.html` / manifest | 3 (or 6) |
| `og-share.png` | no | Social/OG meta image + README hero | `<meta og:image>` + README | 7 |
| `concept-split.png` | no | Blog / social / video thumbnail (not in-app) | marketing | 7 |
| `coldopen-bg.png` | no | Cold-open background scene | `TitleSequence` | 3 §L |
| `title-bg.png` | no | Title-card backdrop / section dividers | `TitleSequence` | 3 §L |
| `noir-bg.png` | no | Noir surface backdrop (header band, The Board page) | `AppShell` / Board | 3 §K |
| `board-cork.png` | no | "The Board" tab background (Cognee Knowledge) | `GraphTabs` → Board view | 3 §K |
| `lightleak-1.png` | no (screen) | Warm film-burn wipe transition | `FilmTransition` | 3 §L |
| `lightleak-2.png` | no (screen) | Cool film-burn wipe transition | `FilmTransition` | 3 §L |
| `flash-burst.png` | no (screen) | Camera-flash on photo-reel reveal | `TimeScrubber` / `GraphView` | 3 §L |
| `grain.png` | no | Global film-grain overlay (~5% opacity) | `CinematicLayer` | 3 §L |
| `flash-frame-1.png` | no | (opt) cold-open montage / empty-board decor | `TitleSequence` / Board | 3 §L (opt) |
| `stamp-redacted.png` | YES | Superseded-fact overlay stamp | `GraphView` fact card | 3 §K |
| `stamp-superseded.png` | YES | Alt supersede stamp | fact card | 3 §K |
| `stamp-error.png` | YES | "Entered in error" → on `forget`/retract | `ScenarioControls` / toast | 3 §K |
| `polaroid-frame.png` | YES | Fact card frame on The Board + reveal | `GraphView` card / Board | 3 §K/§L |
| `pushpin.png` | YES | Pin on board evidence cards | Board card | 3 §K |
| `mascot-groggy.png` | YES | Cold-open + 🥴 Hungover-AI pane empty state | `TitleSequence` / `ChatPane` | 3 §K/§L |
| `mascot-alert.png` | YES | 🧠 Total-Recall pane / success states | `ChatPane` / toasts | 3 §K |

## Quality verdict (checked)
All 20 are production-grade. `logo-neon` uses the chosen wide-reflection style; `og-share` is the
standout hero (sign + corkboard + red string + REDACTED polaroid + clinical panel). No regenerations needed.
