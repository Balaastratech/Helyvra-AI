# IMAGE PROMPT PACK — "Neon-Noir Clinic" theme

> Production-ready prompts for every visual asset + real references. Works with Gemini
> (Nano-Banana / "Gemini 2.5 Flash Image") or Imagen 4 on Vertex.
> Save outputs to `frontend/public/theme/` with the EXACT filename in each block.

## How to use
1. Paste the **GLOBAL STYLE BLOCK** first, then the asset prompt under it.
2. For props/stamps/mascot: generate on **plain white**, then background-remove (Gemini: add "transparent background"; or use any bg remover).
3. If baked-in **text comes out misspelled**, regenerate or (better) render that word in CSS — see "Text tip" below.
4. Aspect ratio: state it ("16:9", "1:1") and/or use the tool's size control.

### GLOBAL STYLE BLOCK (prepend to every prompt)
```
STYLE: cinematic neon-noir fused with clean, premium medical-tech UI. Mood: mysterious
but trustworthy — "the morning after, clarified." Palette: deep navy-black #0A0E1A base;
neon magenta #FF2D95 and neon cyan #22D3EE as the primary glows; warm gold #FFB020 as a
rare highlight; mint-tinted off-white #E8EEF5 for light. Premium, high contrast, soft
volumetric glow, subtle 35mm film grain, crisp focus on the subject.
AVOID: real celebrities or any actor likeness, copyrighted logos, movie posters/stills,
watermarks, gibberish text, clutter, cheesy clip-art, rainbow oversaturation, heavy lens flare.
```

### Text tip (important)
AI image text is unreliable. For the **wordmark** and **stamps**, you have two options:
- (Recommended for the logo) skip the image — render "TOTAL RECALL" in **CSS** using the
  Monoton/Bebas Neue font + neon `text-shadow` (crisp, scalable, always spelled right). Only
  generate the photoreal neon-sign image if you want a hero shot.
- If generating text, keep words SHORT + UPPERCASE and regenerate until spelling is perfect.

---

## BRAND / IDENTITY

### 1) Neon wordmark (hero sign) — `logo-neon.png` · 1600×900 · black bg
```
A photorealistic neon-tube sign spelling the exact words "TOTAL RECALL" on two stacked
lines, glass-tube lettering glowing hot magenta (#FF2D95) with a thin cyan (#22D3EE) outline
glow, switched ON at night, gentle light bloom and a faint reflection on a dark wet surface
below, small mounting brackets, bold condensed lettering, centered, isolated on a solid pure
black background for easy keying. No other objects.
```

### 2) App icon / favicon — `favicon.png` · 1024×1024
```
A minimal app-icon mark: a stylized brain merged with a rewind/clock arrow, drawn as a single
clean geometric line with a magenta-to-cyan neon gradient stroke, on a deep navy #0A0E1A
rounded-square tile with a soft outer glow, perfectly centered, simple enough to read at 32px,
flat and modern, isolated.
```

### 3) Social/OG share image — `og-share.png` · 1200×630
```
A premium 1200x630 social banner. Deep navy #0A0E1A background with subtle film grain. On the
RIGHT, a realistic neon sign reading "TOTAL RECALL" glowing magenta with cyan underglow. On the
LEFT third, a faint moody corkboard with two instant-photos connected by a single taut red
string — one photo subtly stamped "REDACTED". Cinematic volumetric glow, balanced composition,
generous clear negative space in the lower-left for overlaid tagline text later. High contrast.
```

---

## BACKGROUNDS / TEXTURES

### 4) Cold-open background — `coldopen-bg.png` · 1920×1080 (16:9)
```
Photoreal cinematic wide shot of an upscale hotel suite at dawn the morning after a party —
quiet, empty, no people. Soft cool light through sheer curtains reveals blurred Las-Vegas-style
neon city bokeh outside; faint magenta and cyan reflections on glass; a couple of subtle
out-of-focus foreground hints (an overturned glass). Deep navy shadows #0A0E1A, calm, moody,
premium, shallow depth of field, 35mm film grain. No people, no text, no recognizable brands.
```

### 5) Evidence corkboard — `board-cork.png` · 1920×1080 · tileable-friendly
```
Top-down photoreal dark cork board surface under a warm investigative spotlight from above,
rich brown cork with fine natural texture, gentle vignette darkening the edges toward near-black,
completely empty (no pins, no paper, no string), moody neo-noir, seamless-friendly, premium.
```

### 6) (Optional) Subtle noir hero backdrop — `noir-bg.png` · 1920×1080
```
An almost-black deep navy #0A0E1A gradient field with a faint diagonal sweep of magenta and cyan
glow in two corners, very subtle film grain and a soft scanline hint, mostly empty for UI on top,
premium and minimal. No objects, no text.
```

---

## UI PROPS (generate on white → background-remove)

### 7) REDACTED stamp — `stamp-redacted.png` · 1000×500 · white bg
```
A single distressed rubber-ink stamp impression of the word "REDACTED" in bold uppercase,
rotated about -8 degrees, imperfect worn red ink (#E11D48) with realistic gaps and texture,
isolated on a pure white background, no border, no drop shadow, crisp edges for easy removal.
```

### 7b) ENTERED IN ERROR stamp — `stamp-error.png` · 1000×500 · white bg
```
A distressed red rubber-ink stamp reading "ENTERED IN ERROR" in bold uppercase, worn ink
texture (#E11D48), slight rotation, isolated on pure white, no border, no shadow.
```

### 7c) SUPERSEDED stamp — `stamp-superseded.png` · 1000×500 · white bg
```
A distressed rubber-ink stamp reading "SUPERSEDED" in bold uppercase, muted slate-red worn ink,
slight rotation, isolated on pure white, no border, no shadow.
```

### 8) Empty polaroid frame — `polaroid-frame.png` · 800×960 · white bg
```
A single empty instant-photo (polaroid-style) frame, classic white border with a larger bottom
margin, soft realistic drop shadow, the inner photo window is a flat neutral light-grey
placeholder, straight-on top view, isolated on pure white, clean and high-res.
```

### 9) Red pushpin — `pushpin.png` · 512×512 · white bg
```
A single glossy red push-pin (thumbtack) seen from a three-quarter front-top angle, realistic
plastic head with a small specular highlight, soft contact shadow, isolated on pure white,
centered, product-shot quality.
```

---

## CHARACTER / ILLUSTRATION

### 10) Groggy AI mascot — `mascot-groggy.png` · 1024×1024 · white bg
```
A minimal, friendly robot mascot just waking up and groggy: simple rounded head, one optical
"eye" half-open and dim, a tiny floating question mark, a faint magenta glow, flat modern vector
illustration with clean lines, navy #0A0E1A + magenta #FF2D95 accents on white, centered,
isolated on white, charming but professional — not childish or cartoonish.
```

### 11) Alert AI mascot (the "sobered up" state) — `mascot-alert.png` · 1024×1024 · white bg
```
The same minimal robot mascot now fully awake and clear-headed: both optical eyes bright cyan
#22D3EE, confident upright posture, a small teal check mark beside it, calm and capable, flat
modern vector, navy + teal accents on white, isolated.
```

### 12) "Hungover vs Total Recall" concept split (blog / video thumb) — `concept-split.png` · 1600×900
```
A clean conceptual split illustration in two halves. LEFT "hungover" half: dim, desaturated,
magenta neon haze, a confused robot holding a medical chart with a wrong/struck-out line.
RIGHT "clarified" half: bright, clean, clinical white, the same robot now alert holding a
corrected chart with a teal check. A thin vertical neon divider between them. Modern flat-vector
with subtle depth, premium, palette navy/magenta/cyan/teal, clear space at the top for a headline.
```

---

## REAL REFERENCES (for direction / mood — not to copy)
- **Evidence board aesthetic:** Framer "Evidence Board" component · Figma community "Conspiracy Board" · Pinterest "detective cork board".
- **Neon-noir palettes (hex):** devpalettes.com/neon-color-palettes · coloruxlab.com/colors/neon-colors.
- **Neon CSS technique:** css-tricks.com "How to Create Neon Text With CSS" · csstools.io neon text effect.
- **Fonts (free):** Google Fonts — Monoton (neon logo), Bebas Neue (marquee), Inter (UI).
- **Motion (grab, don't generate):** lottiefiles.com — search "neon loader", "developing polaroid", "flicker".

## CINEMATIC ASSETS (the "movie feel" — light-leaks, grain, flash, title-card)
> All blend overlays are designed for `mix-blend-mode: screen` on a PURE BLACK frame.
> Letterbox bars, vignette, and chromatic aberration are done in CSS — no image needed.

### C1) Title-card background — `title-bg.png` · 1920×1080 (16:9)
```
A cinematic anamorphic title-card background: near-black deep navy #0A0E1A field with a single
faint shaft of magenta-and-cyan neon light raking diagonally from the upper right, heavy 35mm
film grain, strong vignette falling to black at the edges, a hint of out-of-focus Vegas neon
bokeh low in the frame, a vast empty dark center for a title to sit. Moody, premium, anamorphic.
No text, no people, no logos.
```

### C2) Light-leak overlay (warm) — `lightleak-1.png` · 1920×1080 · PURE BLACK bg (screen blend)
```
A photographic analog light-leak / film-burn overlay: warm gold and magenta streaks of bloomed
light bleeding in from the right edge across a PURE BLACK background, organic 35mm film burn,
soft smoky glow, high contrast, intended for "screen" blend mode. Only the light leak on solid
black — no subject, no text.
```

### C3) Light-leak overlay (cool) — `lightleak-2.png` · 1920×1080 · PURE BLACK bg (screen blend)
```
A cyan-and-white analog light-leak streak blooming diagonally across a PURE BLACK frame, grainy
35mm film burn, soft glow, for "screen" blend mode. Solid black background only, no objects, no text.
```

### C4) Camera-flash burst — `flash-burst.png` · 1024×1024 · PURE BLACK bg (screen blend)
```
A single photographic camera-flash burst: an intense white circular bloom with a faint
magenta/cyan fringe and subtle hexagonal aperture ghosting, centered on a PURE BLACK background,
for "screen" blend / overlay. No lens body, no text, no people.
```

### C5) Film grain tile — `grain.png` · 1024×1024 · seamless tileable
```
A fine 35mm monochrome film-grain texture, seamless and tileable, neutral mid-grey with subtle
evenly-distributed black-and-white noise, for low-opacity overlay. No banding, no pattern, no text.
```
(Alternative: skip this and use an inline SVG `feTurbulence` filter — cheaper, infinitely scalable.)

### C6) (Optional) Establishing flash-photo frame — `flash-frame-1.png` · 1200×1200 (1:1)
```
An overexposed harsh-direct-flash night-snapshot aesthetic, ABSTRACT: an empty neon-lit hotel
corridor / empty Vegas street at night shot with a hard on-camera flash, blown highlights, deep
shadows, slight motion blur, grainy snapshot/polaroid feel, magenta and cyan neon. Absolutely
NO people, NO faces, no readable text, no brand logos.
```

### Text-as-CSS (do NOT generate): studio card, taglines, "directed by / cast" gag cards, and the
"TOTAL RECALL" wordmark — render in Monoton/Bebas Neue + neon `text-shadow` for crisp, correct text.

## Asset checklist (drop into `frontend/public/theme/`)
`logo-neon.png` · `favicon.png` · `og-share.png` · `coldopen-bg.png` · `board-cork.png` ·
`noir-bg.png` (opt) · `stamp-redacted.png` · `stamp-error.png` · `stamp-superseded.png` ·
`polaroid-frame.png` · `pushpin.png` · `mascot-groggy.png` · `mascot-alert.png` (opt) ·
`concept-split.png` (opt) ·
**cinematic →** `title-bg.png` · `lightleak-1.png` · `lightleak-2.png` · `flash-burst.png` ·
`grain.png` · `flash-frame-1.png` (opt)

Send these back (or just drop them in) and tell me — I'll wire each into the Phase-3 components.
