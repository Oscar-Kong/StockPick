# Settings — Configuration & Ops

> **Route:** `/settings?section=`  
> **Component:** `app/settings/page.tsx` + panels (language, quant-health, API, ops)  
> **Audit:** `docs/UI_AUDIT_REVISED.md` §12.6, §7.2, §15 Phase 4 (#7 Settings polish), §16  
> **Implementation phase:** Phase 1 (focus, nav cleanup) · Phase 5 (theme toggle) — **minimal Phase 4 visual churn**  
> **Parent:** `design-system/MASTER.md`  
> **ui-ux-pro-max pattern:** Real-Time Operations / clinical config — trust signals, status colors, scannable health indicators

---

## Audit alignment (June 2026 revised audit)

> **Do not redesign Settings merely for visual consistency** (§12.6). Reuse its patterns elsewhere; keep structural layout intact.

| Audit finding | Severity | This page response |
|---------------|----------|-------------------|
| Strongest responsive pattern in app | Strength | Export side-nav + mobile `<select>` as template for Portfolio Research (§12.6) |
| Settings in primary nav | Moderate | Phase 1/4: move to gear menu only (§7.2, Master §8) |
| Missing focus on shared controls | Blocking | Phase 1: focus rings on side nav + form controls (§8.1) |
| Light theme not implemented | Major (Phase 5) | Theme toggle lives here after dark tokens stable (§5.3, §15 Phase 5) |
| Async inconsistency | Moderate | Ops panel remains reference; extend skeleton to other sections (§12.6) |

**Phase 5 theme order (audit §5.3):** semantic tokens → dark stable → shared components → **then** theme toggle here → validate all pages in light mode. Do not polish light+dark simultaneously during early migration.

---

## Page purpose

Settings is the **utility configuration surface**: locale, quant stack health, API keys, and operational tools (morning scan email, etc.).

**Preserve:** All four sections, API key masking, quant health diagnostics, language toggle, morning scan panel, escape-to-close, URL-synced section.

---

## Makeover vision

Settings is already the **template** for other pages. Extend it, don’t reinvent:

```text
Page header + Close
├── Mobile: section <select> (keep)
├── Desktop: side nav 220px (keep)
└── Section panel
    ├── Section title (h2, aria-labelledby)
    ├── Description paragraph
    └── Form groups / status cards
```

ui-ux-pro-max: **Operations dashboard** — health status as labeled metrics (green/amber/red), not decorative color.

---

## Layout changes

| Area | Current | Makeover | Priority |
|------|---------|----------|----------|
| Nav placement | Settings in **primary top nav** (violates Master §8) | Remove from top nav; access via gear menu + command palette only | Major |
| Side nav width | Default | Tokenize `--settings-nav-width: 220px` | Minor |
| Section panels | Mixed card styles | Light token alignment only — **no layout redesign** (§12.6) | Minor |
| Close button | Ghost in header | Keep; add mobile full-width “Done” at bottom for thumb reach | Minor |
| Suspense fallback | Plain loading text | `LoadingSkeleton` lines matching form layout | Moderate |

---

## Section-specific upgrades

### Language
- Radio or segmented control with instant preview hint
- Show current locale badge in nav header when not on this section

### Quant health (`QuantHealthCard`)
- ui-ux-pro-max: status as **text + icon** rows (Healthy / Degraded / Down)
- Expandable detail for each subsystem — not all expanded by default
- Link to relevant ops docs (external `Link`, opens new tab)

### API settings
- Masked keys with reveal toggle (`aria-pressed`)
- Test connection button: loading disabled state
- Success/error toast or inline `ErrorState` — not silent failure

### Ops (`MorningScanEmailPanel`)
- Already uses skeleton + ErrorState — **promote as reference implementation**
- Schedule picker: native inputs with visible labels

---

## States (reference for app-wide)

Settings should remain the **canonical async UI example**:

| State | Component |
|-------|-----------|
| Loading | `LoadingSkeleton` |
| Empty | `EmptyState` with configure CTA |
| Error | `ErrorState` + retry |
| Success | Inline green **text label** “Saved” (not green button) |

Other pages should import this pattern from Settings ops panels.

---

## Responsive (keep current behavior)

| Breakpoint | Behavior |
|------------|----------|
| <768px | Full-width select; single column forms |
| 768px+ | Side nav + content |
| Touch | 44px min tap targets on selects and buttons |

---

## Accessibility (already strong — extend)

- Keep `sr-only` on mobile select label
- Keep `aria-current="page"` on side nav
- Keep `aria-labelledby` on sections
- Add focus-visible to side nav links
- Escape to close (keep) — announce to screen readers via focus return to gear menu

---

## Navigation policy (Master §8)

After makeover:
- Top nav: Home, Scan, Analyze, Portfolio, Quant Lab only
- Settings: gear button (matches search trigger styling) opens a quick menu:
  - **All settings** → `/settings` (primary CTA with page subtitle)
  - **Language** — EN / 中文 segmented toggle (instant apply)
  - **Quick links** — Appearance, API integrations, Quant health
- Desktop (768px+): gear + “Settings” label on the trigger; mobile: icon-only
- Command palette: keep settings entry

---

## Anti-patterns

- Treating Settings as a primary product destination in marketing nav
- Destructive red on “Save” buttons
- Plain-text loading for panels that have known form shape

---

## Implementation checklist

### Phase 1
- [ ] Remove Settings from primary `Nav` links (§7.2)
- [ ] Focus-visible on side nav links and all form controls (§8.1)
- [ ] Icon-only controls: `aria-label` audit in API/ops panels (§8.2)

### Phase 4 — minimal polish only
- [ ] `LoadingSkeleton` fallbacks for language/API sections (match ops panel)
- [ ] Token alignment on cards — no structural changes

### Phase 5 — theme
- [ ] Theme preference control + persistence (§15 Phase 5)
- [ ] Validate quant-health status colors in light mode
- [ ] Contrast check all four sections

### Do not
- [ ] Rebuild Settings layout for consistency with other pages (§12.6)
- [ ] Change API key handling or health check logic (§16)
