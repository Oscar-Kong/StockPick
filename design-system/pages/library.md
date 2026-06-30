# Library — Saved Scans & Reports

> **Route:** `/library?tab=` (`scans` · `reports` · `snapshots`)  
> **Component:** `LibraryPage.tsx`  
> **Audit:** `docs/UI_AUDIT.md` §12.5, §11.1, §15 Phase 4 (#6 Library), §16  
> **Implementation phase:** Phase 4 — **fix reliability in Phase 1 before visual work**  
> **Parent:** `design-system/MASTER.md`  
> **ui-ux-pro-max pattern:** List-detail library — neutral surfaces, clear empty/error differentiation

---

## Audit alignment (June 2026 revised audit)

| Audit finding | Severity | This page response |
|---------------|----------|-------------------|
| **Errors silently swallowed** | **Major** | Phase 1: `ErrorState` + retry — `.catch(() => undefined)` must go (§11.1) |
| Plain loading text | Moderate | `LoadingSkeleton` for list + detail panes (§11.2) |
| List-detail layout appropriate | Strength | Keep split layout — validate mobile behavior in browser (§12.5) |
| Empty detail panel whitespace | Browser validation required | Test preview state vs stacked list/detail on mobile (§12.5, §13.3) |
| Hardcoded `#00c805` selection borders | Moderate | Phase 2: interaction token for selected list item (§5.2) |

**Audit objective (§15):** Fix reliability first, then improve list/detail behavior.

---

## Page purpose

Library is the **saved artifact browser**: persisted scans, research reports, and analysis snapshots.

**Preserve:** All three tabs, list selection, report edit/save/delete, scan delete, snapshot listing, deep links from Scan header.

---

## Makeover vision (after error handling fixed)

```text
Page header + tab bar (match Scan/Quant Lab placement)
├── Tab: Scans | Reports | Snapshots
└── List-detail workspace
    ┌─────────────┬──────────────────────────────┐
    │ List pane   │ Detail / preview pane         │
    │ (scroll)    │  — selected item content      │
    │             │  — empty: preview hint + CTA  │
    └─────────────┴──────────────────────────────┘
```

On mobile (<768px): **browser-validate** either:
- Stacked list above detail (current), or
- Full-screen list → tap → full-screen detail with back (Settings-style flow)

Do not choose until Phase 0 screenshots confirm friction.

---

## Reliability (Phase 1 — required first)

Current anti-pattern (§11.1):

```text
Promise.all([...]).catch(() => undefined)
```

Required behavior:

| Outcome | UI |
|---------|-----|
| Network failure | `ErrorState` with retry per tab load |
| Empty list | `EmptyState` — “No saved scans” + link to `/scan` |
| Partial tab failure | Show successful tabs; error banner on failed tab only |
| Saving report | Button disabled + loading; inline error on failure |

Use shared async shell states: `loading` · `error` · `empty` · `success` · `refreshing` (§6.4).

---

## Layout changes (Phase 4)

| Area | Current | Makeover | Priority |
|------|---------|----------|----------|
| Error handling | Swallowed | Per-tab `ErrorState` | **Major — Phase 1** |
| Loading | Plain text | List skeleton + detail skeleton | Moderate |
| Selected item styling | `#00c805` border | `--color-primary` selection (Phase 2) | Moderate |
| Empty detail | Dashed placeholder card | Contextual preview: last selected metadata or “Select an item” | Moderate |
| Tabs | In page body | Below header — consistent with Scan (coordinate with Home tab move) | Minor |

---

## States

| State | Target |
|-------|--------|
| Loading | Skeleton list rows (6) + detail block |
| Empty list | Tab-specific `EmptyState` + navigation CTA |
| Empty selection | Detail pane hint — not blank whitespace |
| Error | `ErrorState` — never indistinguishable from empty |
| Delete confirm | Destructive button styling; preserve item until API confirms |

---

## Responsive

| Breakpoint | Behavior |
|------------|----------|
| 390px | Browser-test list/detail vs navigate pattern (§12.5) |
| 768px+ | Side-by-side list-detail |
| Touch | 44px min row tap targets |

---

## Accessibility

- List items: accessible name includes title + date
- Delete actions: confirm dialog with focus trap
- Selected state: `aria-current="true"` on active list item
- Report editor: labeled title/notes fields

---

## Anti-patterns

- Swallowing fetch errors (§11.1)
- Showing empty list when API failed
- Removing report edit capability
- Card layout replacing list when list scannability is better

---

## Implementation checklist

### Phase 1 (blocking for Library UX)
- [ ] Replace silent `.catch()` with per-tab error handling (§11.1)
- [ ] Differentiate empty vs error in UI copy and visuals

### Phase 0
- [ ] Screenshot Library at 390/768/1024/1440 for list/detail whitespace (§13.1)

### Phase 4 — Library
- [ ] `LoadingSkeleton` for list + detail
- [ ] Mobile list/detail pattern (after browser validation)
- [ ] Selection styling via semantic tokens (Phase 2)
- [ ] Tab placement aligned with other pages
- [ ] No change to save/delete API contracts (§16)
