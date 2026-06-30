# PickerQuant Token Usage Guide

**Phase:** 2  
**Authority:** `design-system/MASTER.md`  
**Implementation:** `frontend/src/app/globals.css`

---

## Rules

1. **Blue is for interaction** — never use green for primary buttons, nav selection, or tab selection.
2. **Green is for financial positive** — Buy recommendations, positive price movement, positive P&L.
3. **Amber is for Hold and caution** — not for primary actions.
4. **Red is for Sell, negative movement, and destructive actions** — not for ordinary selection.
5. **Use CSS variables** — avoid hardcoded hex in new code.

---

## Neutral tokens

| Role | Token | Correct usage | Incorrect usage |
|------|-------|---------------|-----------------|
| Page background | `--color-background` | `body`, page shell | Buy badge background |
| Surface | `--color-surface` | Cards, panels, inputs | — |
| Raised surface | `--color-surface-raised` | Modals, elevated cards | — |
| Hover surface | `--color-surface-hover` | Table row hover | — |
| Selected surface | `--color-surface-selected` | Selected table rows (blue tint) | Buy signal highlight |
| Primary text | `--color-foreground` | Headings, table values | — |
| Secondary text | `--color-foreground-secondary` | Descriptions, hints | — |
| Muted text | `--color-foreground-muted` | Labels, timestamps | Body copy |
| Border | `--color-border` | Card borders, dividers | — |
| Overlay | `--color-overlay` | Modal backdrop | — |

---

## Interaction tokens (blue)

| Role | Token | Correct usage | Incorrect usage |
|------|-------|---------------|-----------------|
| Primary action | `--color-primary` | `.btn-primary`, run scan | Buy badge |
| Primary hover | `--color-primary-hover` | Button hover | — |
| Primary active | `--color-primary-active` | Button pressed | — |
| Primary subtle | `--color-primary-subtle` | Selected tab bg, command palette row | Success toast |
| On primary | `--color-on-primary` | Text on primary buttons | — |
| Focus ring | `--color-ring` | `:focus-visible` outlines | — |
| Links | `.text-primary` | Navigation links, symbol links | Positive P&L |

**Migration example:**

```tsx
// Before (wrong — green used for link)
<Link className="text-brand hover:underline" href="/scan">Scan</Link>

// After
<Link className="text-primary hover:underline" href="/scan">Scan</Link>
```

---

## Financial tokens

| Role | Token | Correct usage | Incorrect usage |
|------|-------|---------------|-----------------|
| Buy | `--color-buy` | Buy badge, positive chart line | Primary button |
| Buy subtle | `--color-buy-subtle` | Buy badge background | Nav selection |
| Hold | `--color-hold` | Hold badge, stale caution | Primary button |
| Sell | `--color-sell` | Sell badge, negative P&L | Row selection |
| Positive text | `.text-positive` | +3.5%, fresh data OK | Navigation |
| Negative text | `.text-negative` | -2.1%, errors | — |

**Signal badge example:**

```tsx
<span className="chip signal-buy px-2 py-0.5 text-xs font-semibold">↑ Buy 72%</span>
```

---

## Tailwind integration

Registered in `@theme inline`:

- `text-primary`, `bg-primary`, `border-primary` → interaction blue
- `text-buy`, `bg-buy`, `border-buy` → financial green
- `text-brand` → **deprecated alias** to buy green (Phase 6 removal)

---

## Chart colors

| Series | Color | Meaning |
|--------|-------|---------|
| Price close | `#22c55e` / `--color-buy` | Price line (default) |
| Positive change | `--color-buy` | Period return ≥ 0 |
| Negative change | `--color-sell` | Period return < 0 |
| MA lines | Fixed palette | Technical indicators (not semantic) |

Use `PRICE_CHART_SERIES` from `@/lib/chartSeries` for price charts.

---

## Deprecated aliases (Phase 6 removal)

| Alias | Points to | Do not use for |
|-------|-----------|----------------|
| `--brand` | `--color-buy` | New interaction code |
| `--brand-text` | `--color-buy` | Links |
| `--brand-soft` | `--color-buy-subtle` | Selection states |
| `.text-brand` | buy green | Links (use `.text-primary`) |

---

## Theme modes

- **Default:** dark (`:root` / `[data-theme="dark"]`)
- **Light:** `[data-theme="light"]` — values defined; toggle in Phase 5
- Components must reference semantic tokens only — no duplicate light/dark implementations per component.
