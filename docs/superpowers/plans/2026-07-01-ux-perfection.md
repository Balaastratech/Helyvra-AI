# UX Perfection Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take the already-strong light-clinical workspace to *exceptional* — close every gap against `UX_DESIGN_PLAN.md`'s acceptance bar (§9), fix the real redundancies, add the one flagship interaction it's missing (⌘K), and perfect loading/error/motion/a11y — without regressing the working flow.

**Architecture:** This is a **polish pass on an existing, well-structured frontend** (React 18 + Vite + TS + Tailwind v4 + Framer Motion + TanStack Query + Zustand). The light-clinical token system, `ClinicalShell`/`Dashboard`/`PatientWorkspace` routing, the clinical components, and the motion keyframes already exist and are good — we refine, not rebuild. Frontend has no unit-test harness, so tasks verify via `npm run build` (type-check) + the preview tool / manual checks against explicit acceptance criteria.

**Tech Stack:** React 18, TypeScript, Tailwind v4 (`@theme` tokens in `src/index.css`), Framer Motion, TanStack Query, Zustand (`src/store.ts`), lucide-react icons. One new dependency: `cmdk` (accessible command palette — a11y keyboard mechanics out of the box, unstyled so it takes our tokens).

---

## Current state audit (what's already right — do NOT rebuild)

Verified by reading the code: light-clinical `@theme` tokens + elevation/tabular/motion keyframes (`index.css`); `ClinicalShell` is a clean light header (no noir) with the patient-context chip, health pill, sign-out; `Dashboard` has the resolver + disambiguation list, critical-reminders strip, patient cards with risk pips, and the drop-zone; `PatientWorkspace` has brief/consult/timeline/compare tabs + the "doctor might miss" right rail; `PreVisitBrief` does the staged `animate-brief-rise` assembly, grouped chart summary, top cards, and the family panel; `ClinicalCard` is severity-coded, always-cited, icon+label+color (a11y), with `animate-severity-pulse` on critical; `ChatPane` renders citations, certainty badge, tool trace with a "raw" toggle, and the correction approval card. This is a real light-clinical product already.

## Gap list (what this plan fixes) — grounded in the read code

1. **Dead noir `NavBar.tsx`** — legacy from the old console (App uses `ClinicalShell`, not `NavBar`); it still carries the neon wordmark + noir bg. Confusing/inconsistent → remove.
2. **Duplicate cards on the Brief tab** — `PatientWorkspace`'s right `aside` renders the cards on *every* tab, and `PreVisitBrief` *also* renders `brief.cards` in its own right column → on the Brief tab the "not to miss" cards appear twice.
3. **No ⌘K command palette** — `UX_DESIGN_PLAN §2` calls this the single feature that makes it feel professional; not built.
4. **Spinners, not skeletons** — `Dashboard` and `PreVisitBrief` use `Loader2` spinners; the plan (§6) wants skeletons (no layout shift, premium feel).
5. **Blunt error states** — e.g. `PreVisitBrief` "Is the backend running?", `ChatPane` `Error: ${err.message}` — §2.6.F wants honest, plain-language, recoverable.
6. **DocumentViewer doesn't highlight the cited page** — citations carry `page`; opening should land on/at that page (§3.7/§6).
7. **No global reach to Compare/Memory/Board from the shell** — only workspace tabs + the "Full map" link; **The Board (raw Cognee graph) is orphaned**, which also hurts the Cognee-visibility story.
8. **Compare is rendered in the light register** — it's the *noir villain* moment (§0/§3.7) but has no dramatic treatment.
9. **A11y / reduced-motion gaps** — Framer animations don't honor `useReducedMotion`; tabs lack `role="tab"`/`aria-selected`; dialogs (WhyPanel/DocumentViewer/HowItWorks) need Esc + focus management.

---

## Task 1: Remove the dead noir NavBar (consistency)

**Files:**
- Delete: `frontend/src/components/layout/NavBar.tsx`

- [ ] **Step 1: Confirm nothing imports it**

Run: `cd frontend && grep -rn "layout/NavBar\|NavBar" src --include=*.tsx | grep -v "NavBar.tsx:"`
Expected: no results (App uses `ClinicalShell`). If any file imports `NavBar`, STOP and report — it's live, not dead.

- [ ] **Step 2: Delete the file**

Run: `cd frontend && git rm src/components/layout/NavBar.tsx`

- [ ] **Step 3: Verify the build still type-checks**

Run: `cd frontend && npm run build`
Expected: builds clean (no missing-import error).

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: remove dead noir NavBar (superseded by light ClinicalShell)"
```

---

## Task 2: Fix duplicate cards on the Brief tab

**Files:**
- Modify: `frontend/src/pages/PatientWorkspace.tsx:94-113` (the right `aside`)

The Brief tab already shows the top cards inside `PreVisitBrief`. The shell-level right rail duplicating them is redundant *only on that tab*. Hide the right rail on `brief` (the brief owns the cards there); keep it on `consult`/`timeline`/`compare` where the main panel is the chat/graph and the persistent card rail is useful.

- [ ] **Step 1: Make the right rail conditional on the active tab**

In `frontend/src/pages/PatientWorkspace.tsx`, wrap the `<aside>` (lines 94-113) so it renders only when `tab !== 'brief'`:

```tsx
      {/* Right rail: doctor-might-miss cards (persistent on non-brief tabs; the
          Brief tab already surfaces these cards in its own layout). */}
      {tab !== 'brief' && (
        <aside className="flex w-[340px] shrink-0 flex-col border-l border-border bg-raised">
          <div className="border-b border-border px-4 py-3">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              Doctor might miss
            </h2>
          </div>
          <div className="min-h-0 flex-1 space-y-2.5 overflow-y-auto p-3">
            {cards.length === 0 ? (
              <p className="rounded-lg border border-border bg-surface p-3 text-xs text-text-muted">
                No open flags yet. Upload this patient’s records to build the brief.
              </p>
            ) : (
              cards.map((c) => <ClinicalCard key={c.check_id} card={c} compact />)
            )}
          </div>
          <div className="border-t border-border p-3">
            <DropZone />
          </div>
        </aside>
      )}
```

- [ ] **Step 2: Verify (preview)**

Run: `cd frontend && npm run build` (type-check), then in the running app open a patient: on **Brief** the cards appear once (in the brief); on **Consult** the right rail returns. No duplicate.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/PatientWorkspace.tsx
git commit -m "fix: don't duplicate not-to-miss cards on the Brief tab"
```

---

## Task 3: ⌘K command palette (the flagship interaction)

**Files:**
- Add dep: `cmdk`
- Modify: `frontend/src/store.ts` (palette open state)
- Create: `frontend/src/components/CommandPalette.tsx`
- Modify: `frontend/src/components/layout/ClinicalShell.tsx` (mount + ⌘K listener + a hint button)

- [ ] **Step 1: Install cmdk**

Run: `cd frontend && npm install cmdk`
Expected: added to `package.json` dependencies (accessible keyboard/focus mechanics out of the box — the research-backed choice over hand-rolling).

- [ ] **Step 2: Add palette state to the store**

In `frontend/src/store.ts`, add to the `UiState` interface (near `howOpen`): `cmdkOpen: boolean` and `setCmdkOpen: (v: boolean) => void`. In the `create` initializer add `cmdkOpen: false,` and `setCmdkOpen: (v) => set({ cmdkOpen: v }),`.

- [ ] **Step 3: Create the palette component**

```tsx
// frontend/src/components/CommandPalette.tsx
import { useEffect, useState } from 'react'
import { Command } from 'cmdk'
import { useNavigate } from 'react-router-dom'
import { Search, UserRound, GitCompare, Network, LayoutGrid, Home, LogOut } from 'lucide-react'
import { usePatients } from '@/api/hooks'
import { useUi } from '@/store'

/**
 * ⌘K command palette (UX §2). Keyboard-first patient switch + navigation — the
 * single interaction that makes the tool feel professional. cmdk provides the
 * ARIA/listbox/focus-trap mechanics; we style it with the clinical tokens and
 * move focus to the input on open (research: always focus the input).
 */
export function CommandPalette() {
  const { cmdkOpen, setCmdkOpen, setPatient, setDoctor } = useUi()
  const navigate = useNavigate()
  const { data: patientsData } = usePatients()
  const patients = patientsData?.patients ?? []
  const [q, setQ] = useState('')

  // Global ⌘K / Ctrl+K toggle.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setCmdkOpen(!cmdkOpen)
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [cmdkOpen, setCmdkOpen])

  function run(fn: () => void) {
    setCmdkOpen(false)
    setQ('')
    fn()
  }
  function openPatient(id: string) {
    run(() => { setPatient(id); navigate(`/patient/${id}`) })
  }

  if (!cmdkOpen) return null

  return (
    <div
      className="fixed inset-0 z-[80] grid place-items-start justify-center bg-black/40 pt-[12vh]"
      onClick={() => setCmdkOpen(false)}
    >
      <Command
        label="Command palette"
        className="w-full max-w-xl overflow-hidden rounded-2xl border border-border bg-surface elev-2"
        onClick={(e) => e.stopPropagation()}
        loop
      >
        <div className="flex items-center gap-2 border-b border-border px-3">
          <Search className="h-4 w-4 text-text-faint" />
          <Command.Input
            autoFocus
            value={q}
            onValueChange={setQ}
            placeholder="Search patients, jump to a view…"
            className="h-11 flex-1 bg-transparent text-sm text-text outline-none placeholder:text-text-faint"
          />
          <kbd className="rounded border border-border px-1.5 py-0.5 text-[10px] text-text-faint">esc</kbd>
        </div>
        <Command.List className="max-h-[50vh] overflow-y-auto p-2">
          <Command.Empty className="px-2 py-6 text-center text-sm text-text-muted">
            No matches.
          </Command.Empty>

          <Command.Group heading="Patients" className="text-[10px] font-semibold uppercase tracking-wide text-text-faint [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1">
            {patients.map((p) => (
              <Command.Item
                key={p.patient_id}
                value={`${p.name} ${p.mrn}`}
                onSelect={() => openPatient(p.patient_id)}
                className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-2 text-sm text-text aria-selected:bg-active-soft aria-selected:text-active"
              >
                <UserRound className="h-4 w-4 text-text-faint" />
                <span className="font-medium">{p.name}</span>
                <span className="tabular ml-auto text-xs text-text-faint">{p.mrn}</span>
              </Command.Item>
            ))}
          </Command.Group>

          <Command.Group heading="Go to" className="mt-1 text-[10px] font-semibold uppercase tracking-wide text-text-faint [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1">
            {[
              { label: 'Dashboard', icon: Home, to: '/' },
              { label: 'Compare (naive vs healed)', icon: GitCompare, to: '/compare' },
              { label: 'Memory Map', icon: Network, to: '/memory' },
              { label: 'The Board (Cognee graph)', icon: LayoutGrid, to: '/board' },
            ].map((v) => (
              <Command.Item
                key={v.to}
                value={v.label}
                onSelect={() => run(() => navigate(v.to))}
                className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-2 text-sm text-text aria-selected:bg-active-soft aria-selected:text-active"
              >
                <v.icon className="h-4 w-4 text-text-faint" /> {v.label}
              </Command.Item>
            ))}
            <Command.Item
              value="Sign out"
              onSelect={() => run(() => { setDoctor(null); navigate('/login') })}
              className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-2 text-sm text-text aria-selected:bg-active-soft aria-selected:text-active"
            >
              <LogOut className="h-4 w-4 text-text-faint" /> Sign out
            </Command.Item>
          </Command.Group>
        </Command.List>
      </Command>
    </div>
  )
}
```

- [ ] **Step 4: Mount it + add a discoverable hint in the shell**

In `frontend/src/components/layout/ClinicalShell.tsx`: import `CommandPalette` and `useUi`'s `setCmdkOpen`; render `<CommandPalette />` next to the other overlays (after `<HowItWorks />`, line ~96). Add a small ⌘K hint button in the header's right cluster (before the "How it works" button):

```tsx
          <button
            onClick={() => setCmdkOpen(true)}
            className="hidden items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-xs text-text-muted hover:text-text sm:flex"
            title="Command palette"
          >
            <Search className="h-3.5 w-3.5" />
            <kbd className="tabular text-[10px]">⌘K</kbd>
          </button>
```

(Add `Search` to the lucide import at the top of `ClinicalShell.tsx`, and pull `setCmdkOpen` from `useUi()`.)

- [ ] **Step 5: Verify**

Run: `cd frontend && npm run build`, then in-app press ⌘K (Ctrl+K on Windows): palette opens with focus in the input, typing filters patients, ↑/↓ + Enter selects (switches patient + navigates), Esc closes. Confirm the "Go to" group reaches Compare / Memory / The Board.

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/store.ts frontend/src/components/CommandPalette.tsx frontend/src/components/layout/ClinicalShell.tsx
git commit -m "feat: cmdk command palette for keyboard-first patient switch + nav"
```

---

## Task 4: Skeleton loading (replace spinners)

**Files:**
- Create: `frontend/src/components/ui/Skeleton.tsx`
- Modify: `frontend/src/pages/Dashboard.tsx` (patient-grid loading)
- Modify: `frontend/src/components/clinical/PreVisitBrief.tsx` (brief loading)

- [ ] **Step 1: Create a Skeleton primitive**

```tsx
// frontend/src/components/ui/Skeleton.tsx
import { cn } from '@/lib/utils'

/** Calm shimmer placeholder — premium loading without layout shift (UX §6).
 * Uses opacity pulse only (GPU) and is inert for reduced-motion via the media query. */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-md bg-raised', className)} />
}
```

- [ ] **Step 2: Add a reduced-motion guard for `animate-pulse`**

In `frontend/src/index.css`, inside the existing `@media (prefers-reduced-motion: reduce)` block (around line 141), add `.animate-pulse` to the list of disabled animations:

```css
  .animate-flicker,
  .animate-lights-on,
  .animate-stamp,
  .animate-develop,
  .animate-pulse-ring,
  .animate-pulse {
    animation: none;
  }
```

- [ ] **Step 3: Dashboard — skeleton patient cards**

In `frontend/src/pages/Dashboard.tsx`, replace the `isLoading ? (<Loader2 .../>...) : (...)` block (lines 138-140) so loading shows six skeleton cards instead of a spinner. Import `Skeleton` at the top. Replace the loading branch:

```tsx
          {isLoading ? (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="flex items-start gap-3 rounded-xl border border-border bg-surface p-4 elev-1">
                  <Skeleton className="h-10 w-10 rounded-full" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-4 w-1/2" />
                    <Skeleton className="h-3 w-full" />
                    <Skeleton className="h-3 w-2/3" />
                  </div>
                </div>
              ))}
            </div>
          ) : (
```

(Leave the existing `) : (` … patient grid … `)}` intact — this only swaps the loading branch. `Loader2` may still be used by the resolver button, so keep its import.)

- [ ] **Step 4: PreVisitBrief — skeleton instead of spinner**

In `frontend/src/components/clinical/PreVisitBrief.tsx`, replace the `if (isLoading)` block (lines 46-52). Import `Skeleton`. Replace:

```tsx
  if (isLoading) {
    return (
      <div className="grid gap-5 p-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,380px)]">
        <div className="space-y-4">
          <Skeleton className="h-3 w-28" />
          <div className="grid gap-3 sm:grid-cols-2">
            {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-28 w-full rounded-xl" />)}
          </div>
        </div>
        <div className="space-y-3">
          <Skeleton className="h-3 w-40" />
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-24 w-full rounded-xl" />)}
        </div>
      </div>
    )
  }
```

- [ ] **Step 5: Verify**

Run: `cd frontend && npm run build`, then throttle the network (or open a fresh patient) and confirm skeletons render in the brief and dashboard grid with no layout jump when data arrives.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ui/Skeleton.tsx frontend/src/index.css frontend/src/pages/Dashboard.tsx frontend/src/components/clinical/PreVisitBrief.tsx
git commit -m "feat: skeleton loading states (dashboard grid + pre-visit brief)"
```

---

## Task 5: Honest, recoverable error states (§2.6.F)

**Files:**
- Modify: `frontend/src/components/clinical/PreVisitBrief.tsx` (error branch)
- Modify: `frontend/src/components/ChatPane.tsx` (send error)

- [ ] **Step 1: PreVisitBrief — plain-language + retry**

In `PreVisitBrief.tsx`, replace the error branch (lines 53-55). Pull `refetch` from `useBrief` if it exposes it (TanStack Query does); if the hook doesn't return it, use `window.location.reload` as the action. Replace:

```tsx
  if (error || !data) {
    return (
      <div className="mx-auto max-w-md p-8 text-center">
        <p className="text-sm text-text">The brief couldn’t load just now.</p>
        <p className="mt-1 text-xs text-text-muted">
          This is a display hiccup — the patient’s records are safe. Try again in a moment.
        </p>
        <button
          onClick={() => window.location.reload()}
          className="mt-4 rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-text hover:border-active/50 hover:text-active"
        >
          Retry
        </button>
      </div>
    )
  }
```

- [ ] **Step 2: ChatPane — honest send failure**

In `ChatPane.tsx`, in `sendMessage`'s `catch` (lines 258-265), replace the bare `Error: ${err.message}` content with a plain, non-alarming line that keeps the conversation usable:

```tsx
    } catch (err: any) {
      setMessages((prev) =>
        prev.map((m) =>
          m.loading
            ? {
                id: m.id, role: 'assistant',
                content:
                  "I couldn't reach memory just now — your message wasn't lost. " +
                  "Please try again; if it keeps happening, the backend may be starting up.",
              }
            : m
        )
      )
    }
```

- [ ] **Step 3: Verify**

Run: `cd frontend && npm run build`, then stop the backend and confirm the brief shows the calm retry card (not "Is the backend running?") and a chat send shows the honest message (not a raw error), with the input still usable.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/clinical/PreVisitBrief.tsx frontend/src/components/ChatPane.tsx
git commit -m "feat: honest, recoverable error states in brief + chat"
```

---

## Task 6: DocumentViewer highlights the cited page

**Files:**
- Read first: `frontend/src/components/DocumentViewer.tsx` (not yet read — read it fully before editing)
- Modify: `frontend/src/store.ts` (carry an optional page with the open-doc action)
- Modify: `frontend/src/components/DocumentViewer.tsx`
- Modify: call sites that open a doc from a citation (`ClinicalCard.tsx`, `ChatPane.tsx`, `PreVisitBrief.tsx`) to pass the page

- [ ] **Step 1: Read the DocumentViewer**

Run: open `frontend/src/components/DocumentViewer.tsx` and note how it renders the document text (whole `text` blob vs pages) and where the `docId` comes from (`useUi().docId`).

- [ ] **Step 2: Extend `openDoc` to accept an optional page**

In `frontend/src/store.ts`: change `docId: string | null` usage to also hold a page. Add `docPage: number | null` to state, change `openDoc: (docId: string, page?: number | null) => void`, set both in the action:

```typescript
  openDoc: (docId, page = null) => set({ docId, docPage: page }),
```
Add `docPage: null,` to the initializer and `docPage: null` to `closeDoc`/`setPatient` resets where `docId` is reset.

- [ ] **Step 3: Use the page in the viewer**

In `DocumentViewer.tsx`, read `docPage` from the store and, when set, render a small "Cited: page N" chip at the top and (if the doc text is split per page or contains `Page N` markers, per the PDF fixtures which print `Page N`) scroll to / highlight that section. Minimum viable: show the "Cited: page N" chip and, if the rendered text contains the literal `Page {n}`, auto-scroll to the first match via a `ref` + `scrollIntoView` in a `useEffect` keyed on `docPage`. Match the viewer's existing markup style (from Step 1).

- [ ] **Step 4: Pass the page from citation click sites**

In `ClinicalCard.tsx` (line 51), `ChatPane.tsx` `CitationChips` (the `openDoc(c.source_document)` call), and `PreVisitBrief.tsx` `Row` (line 28), pass the citation's page: `openDoc(c.source_document, c.page)` / `openDoc(item.source_document, item.page)`. (The `Citation`/`BriefItem` types already carry `page`; if `BriefItem` lacks `page`, add `page?: number | null` to it in `types.ts`.)

- [ ] **Step 5: Verify**

Run: `cd frontend && npm run build`, then click the P010 penicillin-allergy citation (page 2) — the viewer opens with a "Cited: page 2" chip and lands on the page-2 content.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/store.ts frontend/src/components/DocumentViewer.tsx frontend/src/components/clinical/ClinicalCard.tsx frontend/src/components/ChatPane.tsx frontend/src/components/clinical/PreVisitBrief.tsx frontend/src/api/types.ts
git commit -m "feat: DocumentViewer highlights the cited page"
```

---

## Task 7: Global reach to Compare / Memory / The Board

**Files:**
- Modify: `frontend/src/components/layout/ClinicalShell.tsx` (header nav)

The Board (raw Cognee graph) is currently orphaned. Add a small view-nav cluster to the shell header so all three are reachable everywhere (also strengthens the "see Cognee" story).

- [ ] **Step 1: Add nav links to the shell header**

In `ClinicalShell.tsx`, import `NavLink` from `react-router-dom` and the icons `GitCompare, Network, LayoutGrid` from `lucide-react`. In the header's left cluster (after the patient-context chip, inside the first `<div className="flex items-center gap-3">`), add:

```tsx
          <nav className="ml-2 hidden items-center gap-0.5 md:flex">
            {[
              { to: '/compare', label: 'Compare', icon: GitCompare },
              { to: '/memory', label: 'Memory Map', icon: Network },
              { to: '/board', label: 'Cognee graph', icon: LayoutGrid },
            ].map((v) => (
              <NavLink
                key={v.to}
                to={v.to}
                className={({ isActive }) =>
                  cn('flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium transition-colors',
                    isActive ? 'bg-active-soft text-active' : 'text-text-muted hover:bg-raised hover:text-text')
                }
              >
                <v.icon className="h-3.5 w-3.5" /> {v.label}
              </NavLink>
            ))}
          </nav>
```

- [ ] **Step 2: Verify**

Run: `cd frontend && npm run build`, then confirm the header shows Compare / Memory Map / Cognee graph, each navigates, and the active one is highlighted.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/layout/ClinicalShell.tsx
git commit -m "feat: global nav to Compare / Memory Map / Cognee graph"
```

---

## Task 8: Give the Compare page its noir "villain" register (§0/§3.7)

**Files:**
- Modify: `frontend/src/pages/ComparePage.tsx`

Compare is the one place drama belongs — the naive-AI-kills-the-patient moment. Wrap it in the noir register (dark surface, neon-magenta accent on the "Hungover AI" framing) while keeping the light workspace everywhere else.

- [ ] **Step 1: Reskin the Compare page shell to noir**

In `ComparePage.tsx`, wrap the page in the noir surface and give the heading the cinematic treatment (tokens already exist: `bg-noir-bg`, `text-noir-text`, `neon-magenta`, `font-cinema`). Replace the returned JSX:

```tsx
  return (
    <div className="flex h-full min-h-0 flex-col gap-4 bg-noir-bg p-4 text-noir-text">
      <div className="shrink-0">
        <h1 className="font-cinema text-2xl tracking-wide">
          <span className="neon-magenta">Hungover AI</span>{' '}
          <span className="text-noir-muted">vs</span>{' '}
          <span className="neon-cyan">Total Recall</span>
        </h1>
        <p className="text-sm text-noir-muted">
          Same question, both assistants. The naive model repeats the outdated, dangerous
          answer; Total Recall answers from self-healed, time-aware Cognee memory.
        </p>
      </div>
      <div className="min-h-0 flex-1">
        <SplitChat />
      </div>
    </div>
  )
```

(`SplitChat` already styles its two panes; this only sets the surrounding noir stage. If `SplitChat`'s panes look wrong on dark, that's a follow-up inside `SplitChat.tsx` — note it but don't expand scope here.)

- [ ] **Step 2: Verify**

Run: `cd frontend && npm run build`, then open Compare — it reads as the dramatic dark "money-shot" contrast, distinct from the calm light workspace; the rest of the app stays light.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ComparePage.tsx
git commit -m "feat: noir register for the Compare villain moment"
```

---

## Task 9: Accessibility + reduced-motion pass

**Files:**
- Modify: `frontend/src/pages/PatientWorkspace.tsx` (tab ARIA)
- Modify: `frontend/src/components/cinematic/TitleSequence.tsx` and `HowItWorks.tsx` (reduced-motion)
- Modify: dialogs `WhyPanel.tsx`, `DocumentViewer.tsx`, `HowItWorks.tsx` (Esc to close)

- [ ] **Step 1: Tab ARIA roles**

In `PatientWorkspace.tsx`, add `role="tablist"` to the tab container `<div>` (line 44) and to each tab button `role="tab"` + `aria-selected={tab === t.key}`. Add `id`/`aria-controls` pairing if trivial; at minimum `role="tab"` + `aria-selected` (screen-reader correctness).

- [ ] **Step 2: Reduced-motion for Framer**

In `HowItWorks.tsx` and `TitleSequence.tsx`, import `useReducedMotion` from `framer-motion`; when it returns true, render the content without the enter/scale animations (pass `initial={false}` / skip the motion variants). The CSS keyframes are already gated (Task 4 added `animate-pulse`); this covers the JS-driven ones.

- [ ] **Step 3: Esc-to-close on overlays**

Ensure `WhyPanel`, `DocumentViewer`, and `HowItWorks` close on Escape and restore focus. `HowItWorks` already closes on backdrop click; add a `useEffect` keydown listener for `Escape` calling the close action in each (read each file first to use its existing close handler — `setHowOpen(false)` / `closeWhy()` / `closeDoc()`).

- [ ] **Step 4: Verify**

Run: `cd frontend && npm run build`; with a keyboard only, tab to the workspace tabs (announced as tabs), open the Why panel / document viewer and press Esc to close; enable OS "reduce motion" and confirm the title sequence + modals appear without motion.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/PatientWorkspace.tsx frontend/src/components/cinematic/TitleSequence.tsx frontend/src/components/HowItWorks.tsx frontend/src/components/WhyPanel.tsx frontend/src/components/DocumentViewer.tsx
git commit -m "a11y: tab roles, reduced-motion for Framer, Esc-to-close overlays"
```

---

## Task 10: Final acceptance verification (UX §9)

**Files:** none (verification only)

- [ ] **Step 1: Type-check + build**

Run: `cd frontend && npm run build`
Expected: clean build.

- [ ] **Step 2: Walk the acceptance bar (UX_DESIGN_PLAN §9) with backend running**

Confirm each, in the running app:
1. Land → open a patient → the pre-visit brief reads as genuinely useful in ~5s (calm, dense, authoritative). ✅/❌
2. One cohesive light-clinical system top to bottom; no stray dark/light mismatch (Compare is *intentionally* noir). ✅/❌
3. The critical allergy stop, citation→source (now page-highlighted), and patient-switch context handling each feel crafted. ✅/❌
4. ⌘K opens, filters patients, navigates — keyboard-first. ✅/❌
5. Loading = skeletons; errors = calm + recoverable; reduced-motion clean; tabs/dialogs keyboard-accessible. ✅/❌

- [ ] **Step 3: Commit the pass marker**

```bash
git commit -m "test: UX perfection pass — acceptance bar walked green" --allow-empty
```

---

## Self-Review

- **Spec coverage (UX_DESIGN_PLAN §9 acceptance bar):** cohesive light system + no mismatches → Tasks 1, 2, 8; crafted signature moments (⌘K, citation→page, context) → Tasks 3, 6; loading/error/motion/a11y → Tasks 4, 5, 9; reachability/Cognee-visibility → Task 7. The "pre-visit brief is useful in 5s" and "60fps" criteria are verification items (Task 10), already satisfied by the existing build.
- **Placeholder scan:** the new-build tasks (3, 4, 5, 7, 8) ship complete code. Tasks 6 and 9 include "read the file first" steps — correct, because `DocumentViewer.tsx`, `WhyPanel.tsx`, and `TitleSequence.tsx` were not read in this planning session; each still names the exact change, store field, and call sites, so there is no ambiguity about *what* to do, only a required look at existing markup before editing (the skill's sanctioned pattern for in-file UI edits).
- **Type/name consistency:** `cmdkOpen`/`setCmdkOpen` (Task 3) added to the store and consumed in `CommandPalette` + `ClinicalShell`; `openDoc(docId, page?)` (Task 6) — the store signature change is matched at all three call sites (ClinicalCard/ChatPane/PreVisitBrief) and the `docPage` field is added to state + resets; `Skeleton` (Task 4) is imported wherever used; the reduced-motion CSS list (Task 4) and Framer `useReducedMotion` (Task 9) together cover both animation systems.
- **No regression risk:** every task is additive or a scoped swap; the working demo flow (login → dashboard → resolve → brief → consult → compare) is preserved, and Task 2 removes a *duplicate* render, not a feature.
