# PickerQuant Design System

> **LOGIC:** Before building or modifying a page, check `design-system/pages/[page-name].md`.
>
> When a page-specific file exists, its rules override this Master file.
>
> When no page-specific file exists, follow this Master file strictly.
>
> Existing financial calculations, workflows, API contracts, and useful functionality must not be removed solely to simplify the visual design.

---

**Project:** PickerQuant
**Version:** 2.0
**Updated:** 2026-06-30
**Category:** Financial Analytics Dashboard
**Design Direction:** Robinhood readability combined with Linear-style organization
**Default Theme:** Dark
**Supported Themes:** Dark and Light

---

# 1. Product Design Principles

PickerQuant is an operational financial dashboard, not a marketing website.

The interface must feel:

* Trustworthy
* Compact
* Modern
* Data-focused
* Technically capable
* Easy to scan
* Consistent across pages
* Readable during long analytical sessions

The design must prioritize financial information and decision support over decorative presentation.

## Primary principles

### 1. Information first

Important financial data must be visible without requiring unnecessary clicks.

Avoid hiding:

* Buy, Hold, and Sell percentages
* Confidence values
* Data freshness
* Risk indicators
* Portfolio exposure
* Ranking information
* Supporting evidence
* Experiment results

### 2. Compact, not crowded

PickerQuant should display a useful amount of information per screen while preserving clear hierarchy and readable spacing.

Use tighter spacing inside related groups and larger spacing between separate concepts.

### 3. Color has meaning

Do not use green, amber, or red decoratively.

These colors are reserved for financial meaning:

* Green: positive movement or Buy
* Amber: Hold, caution, or incomplete confidence
* Red: negative movement, Sell, warning, or destructive action

McLaren papaya orange is used for normal interactions, navigation, selected states, and informational emphasis.

**PickerQuant brand palette (2026):** McLaren papaya orange (`--color-primary`) for UI chrome; Robinhood-style green (`--color-buy`, `.btn-action`) for Run scan, Run daily decision, Buy signals, and positive movement.

### 4. Preserve functionality

A visual redesign must not remove useful functionality.

When a page feels scattered, reorganize and consolidate its content instead of deleting information.

### 5. Progressive complexity

Show the most important information first.

Advanced details should remain accessible through:

* Expandable sections
* Drawers
* Inspectors
* Tooltips
* Secondary tabs
* Advanced chart controls

---

# 2. Theme System

PickerQuant supports both dark and light themes.

Dark mode is the default.

Theme values must be implemented through semantic CSS variables. Components must not contain scattered hardcoded theme colors.

---

## 2.1 Dark theme

```css
:root,
[data-theme="dark"] {
  color-scheme: dark;

  --color-background: #090A0C;
  --color-background-subtle: #0D0F12;

  --color-surface: #111317;
  --color-surface-raised: #16191E;
  --color-surface-hover: #1A1E24;
  --color-surface-selected: #172033;

  --color-foreground: #F4F6F8;
  --color-foreground-secondary: #C7CDD6;
  --color-foreground-muted: #8E98A7;
  --color-foreground-disabled: #5D6571;

  --color-border: #262B33;
  --color-border-strong: #353C47;
  --color-divider: #20242B;

  --color-primary: #3B82F6;
  --color-primary-hover: #60A5FA;
  --color-primary-active: #2563EB;
  --color-primary-subtle: rgba(59, 130, 246, 0.14);
  --color-on-primary: #FFFFFF;

  --color-buy: #22C55E;
  --color-buy-hover: #4ADE80;
  --color-buy-subtle: rgba(34, 197, 94, 0.14);

  --color-hold: #F59E0B;
  --color-hold-hover: #FBBF24;
  --color-hold-subtle: rgba(245, 158, 11, 0.14);

  --color-sell: #EF4444;
  --color-sell-hover: #F87171;
  --color-sell-subtle: rgba(239, 68, 68, 0.14);

  --color-info: #38BDF8;
  --color-info-subtle: rgba(56, 189, 248, 0.14);

  --color-ring: #60A5FA;
  --color-overlay: rgba(0, 0, 0, 0.72);
}
```

---

## 2.2 Light theme

```css
[data-theme="light"] {
  color-scheme: light;

  --color-background: #F6F7F9;
  --color-background-subtle: #EEF1F4;

  --color-surface: #FFFFFF;
  --color-surface-raised: #FFFFFF;
  --color-surface-hover: #F6F8FA;
  --color-surface-selected: #EFF6FF;

  --color-foreground: #111318;
  --color-foreground-secondary: #3D4652;
  --color-foreground-muted: #667180;
  --color-foreground-disabled: #9AA3AE;

  --color-border: #DDE2E8;
  --color-border-strong: #C9D0D8;
  --color-divider: #E7EAEE;

  --color-primary: #2563EB;
  --color-primary-hover: #1D4ED8;
  --color-primary-active: #1E40AF;
  --color-primary-subtle: rgba(37, 99, 235, 0.1);
  --color-on-primary: #FFFFFF;

  --color-buy: #15803D;
  --color-buy-hover: #166534;
  --color-buy-subtle: rgba(21, 128, 61, 0.1);

  --color-hold: #B45309;
  --color-hold-hover: #92400E;
  --color-hold-subtle: rgba(180, 83, 9, 0.1);

  --color-sell: #DC2626;
  --color-sell-hover: #B91C1C;
  --color-sell-subtle: rgba(220, 38, 38, 0.1);

  --color-info: #0369A1;
  --color-info-subtle: rgba(3, 105, 161, 0.1);

  --color-ring: #2563EB;
  --color-overlay: rgba(15, 23, 42, 0.55);
}
```

---

# 3. Color Usage Rules

## Neutral-first interface

Most of the interface should use:

* Neutral backgrounds
* Neutral borders
* White or near-white text
* Muted gray secondary text

Financial colors must be applied selectively.

## Primary blue

Use blue for:

* Primary buttons
* Active navigation
* Selected tabs
* Links
* Focus rings
* Informational highlights
* Active filters
* Interactive chart controls

Do not use amber as the normal primary action color.

## Buy, Hold, and Sell

Use light-tinted badges with colored text and icons.

```css
.signal-buy {
  color: var(--color-buy);
  background: var(--color-buy-subtle);
}

.signal-hold {
  color: var(--color-hold);
  background: var(--color-hold-subtle);
}

.signal-sell {
  color: var(--color-sell);
  background: var(--color-sell-subtle);
}
```

Every financial signal must include a text label.

Never communicate a recommendation through color alone.

Correct:

```text
↑ Buy 72%
— Hold 48%
↓ Sell 67%
```

Incorrect:

```text
●
●
●
```

---

# 4. Typography

## Font family

* **Primary UI font:** Geist Sans
* **Secondary data font:** Geist Mono
* **Numbers:** Geist Sans with tabular number formatting
* **Tickers and technical identifiers:** Geist Mono where appropriate

Avoid using monospace typography for all headings.

## Font import

For Next.js, use `next/font` instead of a CSS `@import` when possible.

```tsx
import { Geist, Geist_Mono } from "next/font/google";

export const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

export const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});
```

## CSS typography variables

```css
:root {
  --font-sans: var(--font-geist-sans), Inter, system-ui, sans-serif;
  --font-mono: var(--font-geist-mono), "SFMono-Regular", monospace;

  --text-xs: 0.75rem;
  --text-sm: 0.8125rem;
  --text-base: 0.875rem;
  --text-md: 1rem;
  --text-lg: 1.125rem;
  --text-xl: 1.375rem;
  --text-2xl: 1.75rem;
  --text-3xl: 2.125rem;
}
```

## Type hierarchy

| Role           |    Size |  Weight | Line Height |
| -------------- | ------: | ------: | ----------: |
| Page title     |    28px |     600 |        36px |
| Section title  |    18px |     600 |        26px |
| Card title     |    15px |     600 |        22px |
| Body           |    14px |     400 |        21px |
| Secondary text |    13px |     400 |        19px |
| Table text     |    13px | 400–500 |        18px |
| Label          |    12px |     500 |        16px |
| Large metric   | 24–32px |     600 |        1.15 |

Do not use oversized marketing-style headings within dashboard pages.

## Number formatting

All financial numbers must use tabular numerals.

```css
.numeric {
  font-variant-numeric: tabular-nums lining-nums;
}
```

Use consistent formatting:

```text
$124.52
+$4.28
+3.56%
72%
1.24×
Jun 30, 2026
```

Align numbers to the right inside tables.

---

# 5. Spacing and Density

PickerQuant uses a compact density level.

```css
:root {
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-10: 40px;
  --space-12: 48px;
}
```

## Standard spacing rules

* Inline icon gap: 6–8px
* Form control gap: 8–12px
* Card internal padding: 16–20px
* Page horizontal padding: 20–32px
* Related section gap: 12–16px
* Separate section gap: 24–32px
* Table row height: 44px
* Compact toolbar height: 40–44px
* Top navigation height: 56–60px

Avoid using 48px or 64px spacing inside normal application pages unless a major layout separation requires it.

---

# 6. Border Radius

Use restrained rounding.

```css
:root {
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 10px;
  --radius-xl: 12px;
  --radius-full: 9999px;
}
```

Recommended usage:

* Buttons: 8px
* Inputs: 8px
* Cards: 8px
* Tables and panels: 8px
* Modals and drawers: 10–12px
* Badges: full radius or 6px

Avoid excessively rounded cards.

---

# 7. Shadows and Surface Hierarchy

Use a mixed surface system.

Data-heavy areas should primarily use borders.

Shadows are reserved for:

* Important summary cards
* Dropdowns
* Floating menus
* Drawers
* Modals
* Temporary overlays

```css
:root {
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.18);
  --shadow-md: 0 6px 18px rgba(0, 0, 0, 0.22);
  --shadow-lg: 0 18px 44px rgba(0, 0, 0, 0.32);
}
```

Do not apply large shadows to every card.

---

# 8. Navigation

## Desktop navigation

Use a top navigation bar.

The top navigation should include the primary product destinations, such as:

* Home
* Scan
* Analyze
* Portfolio
* Quant Lab

Settings should not appear as a normal primary navigation destination.

Place Settings inside:

* User menu
* Utility menu
* Account dropdown
* Top-right control area

## Top navigation behavior

```css
.app-header {
  height: 58px;
  background: color-mix(
    in srgb,
    var(--color-background) 92%,
    transparent
  );
  border-bottom: 1px solid var(--color-border);
  backdrop-filter: blur(12px);
}
```

The navigation must:

* Remain readable at all supported widths
* Clearly indicate the active page
* Avoid overly wide navigation gaps
* Avoid unnecessary icons beside every text label
* Support keyboard navigation
* Collapse responsibly at smaller widths

## Mobile navigation

Mobile navigation may use one of these patterns based on the page structure:

* Compact top navigation with overflow menu
* Bottom navigation for the most frequent destinations
* Drawer navigation for secondary destinations

Do not force a desktop navigation layout onto mobile.

---

# 9. Page Layout System

PickerQuant does not use one universal hero or bento-grid pattern.

Choose the layout based on the purpose of each page.

## Standard page shell

```text
Top Navigation
Page Header
Optional Summary Strip
Primary Workspace
Secondary Details
```

## Page header

A page header should usually contain:

* Page title
* Short context or freshness status
* Primary page-level action
* Optional compact secondary controls

The header should not consume excessive vertical space.

## Content width

Data-heavy pages may use the available viewport width.

Avoid placing tables or charts inside unnecessarily narrow centered containers.

```css
.page-container {
  width: 100%;
  max-width: 1600px;
  margin: 0 auto;
  padding: 20px 24px 32px;
}
```

---

# 10. Component Specifications

## 10.1 Buttons

### Primary button

Use blue for normal primary actions.

```css
.btn-primary {
  min-height: 38px;
  padding: 0 14px;
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  background: var(--color-primary);
  color: var(--color-on-primary);
  font-family: var(--font-sans);
  font-size: var(--text-sm);
  font-weight: 600;
  cursor: pointer;
  transition:
    background-color 180ms ease,
    border-color 180ms ease,
    box-shadow 180ms ease;
}

.btn-primary:hover {
  background: var(--color-primary-hover);
}

.btn-primary:active {
  background: var(--color-primary-active);
}

.btn-primary:focus-visible {
  outline: 2px solid var(--color-ring);
  outline-offset: 2px;
}
```

Do not use movement or scale transforms for normal button hover states.

### Secondary button

```css
.btn-secondary {
  min-height: 38px;
  padding: 0 14px;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  color: var(--color-foreground);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition:
    background-color 180ms ease,
    border-color 180ms ease;
}

.btn-secondary:hover {
  background: var(--color-surface-hover);
  border-color: var(--color-foreground-muted);
}
```

### Destructive button

Destructive red must only be used for destructive actions such as:

* Delete
* Remove
* Reset
* Disconnect
* Clear permanent data

Do not use destructive red for normal financial Sell recommendations unless the component is explicitly displaying a recommendation.

---

## 10.2 Cards and panels

Cards are not automatically clickable.

```css
.card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-4);
}
```

### Interactive cards

Only add hover behavior when the entire card performs an action.

```css
.card-interactive {
  cursor: pointer;
  transition:
    background-color 180ms ease,
    border-color 180ms ease,
    box-shadow 180ms ease;
}

.card-interactive:hover {
  background: var(--color-surface-hover);
  border-color: var(--color-border-strong);
}
```

Do not lift every card with a transform.

### Summary cards

Important top-level metric cards may use a subtle shadow.

```css
.summary-card {
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 16px;
  box-shadow: var(--shadow-sm);
}
```

---

## 10.3 Inputs

```css
.input {
  width: 100%;
  min-height: 38px;
  padding: 0 12px;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  color: var(--color-foreground);
  font-family: var(--font-sans);
  font-size: var(--text-sm);
  transition:
    border-color 180ms ease,
    box-shadow 180ms ease,
    background-color 180ms ease;
}

.input::placeholder {
  color: var(--color-foreground-muted);
}

.input:hover {
  border-color: var(--color-foreground-muted);
}

.input:focus {
  border-color: var(--color-primary);
  outline: none;
  box-shadow: 0 0 0 3px var(--color-primary-subtle);
}
```

Inputs should not default to 16px vertical padding in dense analytical toolbars.

---

## 10.4 Tables

Tables are a primary component in PickerQuant.

```css
.data-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  font-size: var(--text-sm);
}

.data-table th {
  height: 38px;
  padding: 0 12px;
  color: var(--color-foreground-muted);
  font-size: var(--text-xs);
  font-weight: 600;
  text-align: left;
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
}

.data-table td {
  height: 44px;
  padding: 0 12px;
  color: var(--color-foreground);
  border-bottom: 1px solid var(--color-divider);
}

.data-table tbody tr:hover {
  background: var(--color-surface-hover);
}
```

Table rules:

* Row height should normally be 44px
* Keep tickers and names visually distinct
* Align financial numbers to the right
* Use tabular numerals
* Use sticky headers where useful
* Do not color every value
* Highlight only meaningful changes
* Use clear sorting indicators
* Preserve keyboard-accessible row actions
* Avoid placing every action directly inside the row

Use a menu or detail inspector for secondary row actions.

---

## 10.5 Tabs

```css
.tabs {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid var(--color-border);
}

.tab {
  min-height: 38px;
  padding: 0 10px;
  border-bottom: 2px solid transparent;
  color: var(--color-foreground-muted);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition:
    color 180ms ease,
    border-color 180ms ease,
    background-color 180ms ease;
}

.tab:hover {
  color: var(--color-foreground);
}

.tab[aria-selected="true"] {
  color: var(--color-foreground);
  border-bottom-color: var(--color-primary);
}
```

Avoid duplicate tab systems on the same page.

Tabs must represent genuinely different views.

---

## 10.6 Badges and status indicators

```css
.badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-height: 24px;
  padding: 3px 8px;
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  font-weight: 600;
  white-space: nowrap;
}
```

Use:

* Buy badge
* Hold badge
* Sell badge
* Fresh data badge
* Stale data badge
* Running badge
* Completed badge
* Failed badge

Status indicators should always contain readable text.

---

## 10.7 Modals and drawers

```css
.modal-overlay {
  background: var(--color-overlay);
  backdrop-filter: blur(4px);
}

.modal,
.drawer {
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border-strong);
  box-shadow: var(--shadow-lg);
}

.modal {
  width: min(520px, calc(100vw - 32px));
  border-radius: var(--radius-xl);
  padding: 24px;
}
```

For data-heavy details, prefer a side drawer or inspector over a centered modal.

---

# 11. Chart System

Charts should be simple by default and expandable for deeper analysis.

## Default chart behavior

The default view should show:

* Price line or candle data
* Date range
* Current value
* Percentage change
* Clear tooltip
* Latest available date
* Data freshness status

Advanced controls may reveal:

* Comparison symbols
* Technical indicators
* Volume
* Moving averages
* Benchmark comparison
* Drawdown
* Correlation
* Event markers

## Price movement colors

Use:

* Green for positive movement
* Red for negative movement
* Neutral gray when direction is not meaningful

Recommendation colors and price movement colors may overlap, but they must use different shapes, labels, and contexts.

## Chart accessibility

Charts must include:

* Readable axes
* Clear tooltip values
* Text summaries
* Keyboard-accessible controls
* Non-color indicators where practical
* Loading state
* Empty state
* Error state
* Stale-data state

## Chart density

Avoid unnecessary gridlines and legends.

Show only controls relevant to the current analytical context.

---

# 12. Motion and Interaction

Use moderate motion.

Motion may be used for:

* Drawer opening and closing
* Tab transitions
* Dropdowns
* Loading states
* Skeleton transitions
* Chart updates
* Important metric changes
* Page-level transitions
* Expandable details

Avoid animation that distracts from financial data.

## Financial value changes

When a value changes, use a brief directional highlight.

Examples:

* Green flash for positive updates
* Red flash for negative updates
* Neutral flash for non-directional updates

Do not use animated counting numbers for frequently updating market data.

## Timing

```css
:root {
  --duration-fast: 150ms;
  --duration-normal: 200ms;
  --duration-slow: 280ms;
  --ease-standard: cubic-bezier(0.2, 0, 0, 1);
}
```

## Reduced motion

```css
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    scroll-behavior: auto !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

# 13. Responsive Behavior

Validate at:

* 375px
* 390px
* 768px
* 1024px
* 1440px

## Desktop

* Use full-width analytical workspaces
* Preserve important columns
* Allow side inspectors
* Keep navigation visible
* Avoid oversized empty margins

## Tablet

* Reduce page padding
* Collapse secondary controls
* Stack secondary panels when necessary
* Preserve chart readability
* Keep primary actions accessible

## Mobile

Use different behavior depending on the data and task.

For large tables:

* Show essential columns
* Move secondary fields into a row detail drawer
* Use horizontal scrolling only when column comparison is essential
* Convert rows into cards only when the card format improves comprehension

Do not automatically convert every table into cards.

Mobile layouts must preserve:

* Recommendation
* Symbol
* Price
* Percentage movement
* Confidence
* Data freshness
* Primary actions

---

# 14. Portfolio Page Direction

The current Portfolio functionality should be preserved.

The redesign should focus on organization and readability rather than feature removal.

Until `design-system/pages/portfolio.md` exists, use this structure:

```text
Portfolio Header
Portfolio Summary Strip
Holdings Workspace
Allocation and Risk Panel
Recent Activity or Supporting Details
```

## Portfolio header

Include:

* Portfolio title
* Data freshness
* Last synchronization time
* Primary portfolio action
* Compact utility actions

## Summary strip

Group major metrics together:

* Total portfolio value
* Daily gain or loss
* Total return
* Cash balance
* Invested value
* Risk or concentration indicator

Do not scatter these values across unrelated cards.

## Holdings workspace

Use one primary holdings table containing:

* Symbol
* Company
* Position value
* Shares
* Average cost
* Current price
* Gain or loss
* Portfolio weight
* Current recommendation
* Confidence

Allow row selection to open a detail drawer.

## Allocation and risk

Place allocation and risk information in a clear secondary panel.

Possible content:

* Sector exposure
* Position concentration
* Top holdings
* Cash allocation
* Risk warnings
* Recommendation distribution

Do not repeat the same information in multiple cards.

## Existing functionality

Before modifying Portfolio:

1. Inventory every current feature.
2. Record where each feature will move.
3. Preserve all useful actions and metrics.
4. Verify that no portfolio calculation changes.
5. Verify that recommendation data remains visible.
6. Confirm that mobile users can still inspect full holding details.

---

# 15. Loading, Empty, Error, and Stale States

Every major data component must support four states.

## Loading

Use skeletons that resemble the final structure.

Avoid indefinite full-page spinners where partial content can be shown.

## Empty

Explain:

* Why the area is empty
* Whether this is expected
* What the user can do next

## Error

Show:

* Clear error message
* Retry action
* Whether existing cached data is still available

## Stale data

Clearly display:

* Last updated timestamp
* Stale status
* Refresh action
* Whether calculations use the stale dataset

Do not silently display outdated financial information.

---

# 16. Iconography

Use one consistent SVG icon library.

Preferred:

* Lucide
* Heroicons

Do not mix multiple icon styles on the same page.

Rules:

* No emojis as functional icons
* Use 16px or 18px icons in compact controls
* Use 20px icons in primary navigation where needed
* Every icon-only button requires an accessible label
* Decorative icons must not compete with financial information

---

# 17. Accessibility

Minimum requirements:

* Normal text contrast: 4.5:1
* Large text contrast: 3:1
* Visible keyboard focus
* Full keyboard access for controls
* Accessible labels for icon buttons
* Accessible table headers
* Semantic status text
* Reduced motion support
* Color-independent signal communication
* Touch targets of at least 40px where practical

Clickable elements must use the correct semantic element:

* Use `<button>` for actions
* Use `<a>` for navigation
* Do not use clickable `<div>` elements unless unavoidable

---

# 18. Anti-Patterns

Do not use:

* Marketing-style hero sections inside application pages
* Universal bento grids
* Oversized decorative cards
* Large unused whitespace
* Low-contrast muted text
* Monospace headings throughout the interface
* Amber as the normal primary action color
* Green as a generic action color
* Shadows on every panel
* Hover transforms that move layout
* Clickable styling on non-clickable cards
* Duplicate tabs
* Multiple competing navigation systems
* Hidden financial context
* Color-only recommendations
* Animated counting market values
* Excessive gradients
* Decorative chart effects
* Excessively rounded components
* Emojis as icons
* Invisible focus states
* Horizontal page scrolling on mobile
* Removing useful information to create visual simplicity

---

# 19. Pre-Implementation Checklist

Before changing a page:

* [ ] Read this Master file
* [ ] Read the page-specific design file when available
* [ ] Inventory the page’s current functionality
* [ ] Identify current API and data dependencies
* [ ] Identify duplicated components
* [ ] Confirm what information must be preserved
* [ ] Confirm loading, empty, error, and stale states
* [ ] Confirm desktop and mobile behavior
* [ ] Avoid changing business logic during visual work

---

# 20. Pre-Delivery Checklist

Before delivering UI changes:

* [ ] Dark and light themes both render correctly
* [ ] Dark mode remains the default
* [ ] Text contrast meets accessibility requirements
* [ ] Buy, Hold, and Sell use labels in addition to color
* [ ] Normal actions use blue rather than amber or green
* [ ] All numbers use tabular numerals
* [ ] Tables use approximately 44px rows
* [ ] Important financial values remain visible
* [ ] Existing functionality has not been removed
* [ ] No emojis are used as functional icons
* [ ] Iconography uses one consistent library
* [ ] All clickable elements use appropriate cursors
* [ ] All controls have visible hover and focus states
* [ ] No hover interaction causes layout shift
* [ ] Reduced-motion preferences are respected
* [ ] Loading, empty, error, and stale states are implemented
* [ ] Charts show the latest available data date
* [ ] Charts resize correctly
* [ ] No content is hidden behind fixed navigation
* [ ] No horizontal page scrolling occurs on mobile
* [ ] Responsive layouts are validated at 375px, 390px, 768px, 1024px, and 1440px
* [ ] Lint passes
* [ ] Type checking passes
* [ ] Tests pass
* [ ] Production build passes
