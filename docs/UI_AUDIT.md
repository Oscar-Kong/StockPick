# PickerQuant Frontend UI/UX Audit 

**Date:** June 30, 2026
**Scope:** Application shell, navigation, shared components, Portfolio/Home, Scan, Analyze/Workspace, Quant Lab, Library, Settings
**Primary design reference:** PickerQuant Design System Master
**Implementation constraint:** UI work must not change business logic, financial calculations, recommendation logic, API contracts, data-processing behavior, or existing useful functionality.

---

# 1. Audit Method

This audit combines:

1. Code-level frontend review
2. Design-system comparison
3. Component architecture review
4. Accessibility review
5. Responsive-design inspection
6. Identification of findings that still require browser validation

Each finding is labeled using one of the following evidence categories.

| Evidence label                  | Meaning                                                                                              |
| ------------------------------- | ---------------------------------------------------------------------------------------------------- |
| **Code verified**               | The issue can be confirmed directly from the implementation                                          |
| **Specification mismatch**      | The implementation conflicts with the PickerQuant design system                                      |
| **Browser validation required** | The code suggests a likely visual issue, but the running interface must be inspected before redesign |
| **Architecture finding**        | The issue relates to duplication, maintainability, or inconsistent component contracts               |

Visual findings must not be treated as confirmed until the relevant page has been inspected in the browser at the required breakpoints.

---

# 2. Severity Definitions

## Blocking

A problem that prevents essential use, creates a serious accessibility barrier, or makes a core flow unusable.

Blocking issues must be fixed before release.

## Major

A problem that materially damages usability, consistency, accessibility, reliability, or design-system integrity.

Major issues should be fixed before broader visual polish.

## Moderate

A problem that creates inconsistency, friction, crowding, or maintainability concerns but does not prevent core use.

## Minor

A cosmetic, naming, cleanup, or lower-impact consistency issue.

---

# 3. Executive Assessment

PickerQuant already has a strong functional frontend foundation.

Notable strengths include:

* URL-persisted page and tab state
* Strong financial recommendation badges
* Existing internationalization support
* Useful shared table and page primitives
* A functional Command Palette
* Good data-freshness handling in Portfolio and Scan
* Progressive-disclosure patterns in Quant Lab
* Good responsive navigation patterns inside Settings
* Tabular number formatting in financial components
* Existing loading, error, stale, and empty-state components

The primary frontend problems are not caused by a lack of components. They are caused by **multiple overlapping component systems and inconsistent use of design tokens**.

The highest-priority issues are:

1. Missing visible keyboard focus on important controls
2. No discoverable primary navigation below 768px
3. Conflict between green financial semantics and green interaction styling
4. Fragmented loading, empty, error, and refresh behavior
5. Missing accessible chart summaries
6. Color-only correlation display
7. Silent Library request failures
8. Design-system path mismatch
9. Unverified visual assumptions about crowding and whitespace
10. Component duplication that should be consolidated gradually

---

# 4. Current Frontend Architecture

## 4.1 Technology

| Layer                | Implementation                               |
| -------------------- | -------------------------------------------- |
| Framework            | Next.js App Router                           |
| Styling              | Tailwind CSS v4 and a large global CSS layer |
| Fonts                | Geist Sans and Geist Mono                    |
| Internationalization | Client-side i18n provider                    |
| Charts               | Recharts and custom data visualizations      |
| API layer            | Typed frontend request wrappers              |
| State persistence    | URL parameters and route state               |

## 4.2 Application shell

```text
Root Layout
├── Sticky top navigation
├── Public/demo environment banner
├── Main page content
└── Footer API status
```

The application uses two broad page layouts:

1. Standard pages using a page container and page header
2. Full-height workspace pages for Analyze

This is an appropriate architectural distinction and should be preserved.

## 4.3 Route structure

| Destination             | Route           |
| ----------------------- | --------------- |
| Portfolio/Home          | `/`             |
| Scan                    | `/scan`         |
| Analyze workspace       | `/workspace`    |
| Analyze legacy redirect | `/analyze`      |
| Quant Lab               | `/quant-lab`    |
| Library                 | `/library`      |
| Settings                | `/settings`     |
| Trader Intel            | `/trader-intel` |

### Finding: Portfolio/Home naming inconsistency

**Evidence:** Code verified
**Severity:** Minor

The root route functions as Portfolio, while parts of the product and design documentation refer to Home.

This does not require architectural change, but product naming should be standardized.

Recommended resolution:

* Use **Portfolio** when the page is primarily holdings and decision management.
* Use **Home** only when the page becomes a broader daily overview.
* Update labels and documentation consistently.

---

# 5. Design-System Integration

## 5.1 Design-system path mismatch

**Evidence:** Code verified
**Severity:** Major

The Cursor rule expects:

```text
design-system/MASTER.md
design-system/pages/
```

The repository currently uses:

```text
design-system/pickerquant/MASTER.md
```

Page-specific override files now exist at:

```text
design-system/pages/
├── home.md        # Today / daily cockpit (/) 
├── portfolio.md   # Research + Activity tabs
├── scan.md
├── analyze.md     # Same scope as audit "workspace" 
├── quant-lab.md
├── library.md
└── settings.md
```

Canonical Master path migration (`design-system/MASTER.md` vs `pickerquant/MASTER.md`) is still pending per Phase 0 task 1.

This can cause Cursor to:

* Miss the actual Master file
* Apply generic skill defaults
* Ignore page-specific requirements
* Create a second competing design system

### Required correction

Choose one canonical structure:

```text
design-system/
├── MASTER.md
└── pages/
    ├── portfolio.md
    ├── scan.md
    ├── workspace.md
    ├── quant-lab.md
    ├── library.md
    └── settings.md
```

Do not keep two Master files.

---

## 5.2 Design-system and implementation token drift

**Evidence:** Specification mismatch
**Severity:** Major

The PickerQuant design system defines:

* Blue for interaction and selection
* Green for Buy and positive financial meaning
* Amber for Hold and caution
* Red for Sell, negative movement, and destructive states

The frontend currently uses Robinhood green for several unrelated meanings, including:

* Primary actions
* Active navigation
* Active tabs
* Buy recommendations
* Positive financial movement
* Success states

This weakens visual meaning.

### Required semantic classification

Before changing colors, classify each use into one of these roles:

```text
Interaction
Selection
Buy recommendation
Positive price movement
Success confirmation
Hold or caution
Sell recommendation
Negative price movement
Destructive action
Information
Neutral surface
Neutral text
Border
```

### Migration rule

Do not globally replace:

```text
#00c805
emerald-*
green-*
```

A blind replacement may incorrectly change financial signals.

Migrate component by component.

---

## 5.3 Light-theme support

**Evidence:** Specification mismatch
**Severity:** Major relative to the design system, but not an immediate implementation priority

The Master file defines both dark and light themes, with dark mode as default.

The current implementation is effectively dark-only.

### Recommended order

1. Define semantic tokens for both themes.
2. Stabilize the dark theme.
3. Consolidate shared components.
4. Implement the theme toggle.
5. Validate every primary page in light mode.

Do not double the page-level redesign workload by polishing dark and light modes simultaneously during early component migration.

---

# 6. Shared Component Architecture

## 6.1 Existing strengths

The frontend already includes useful reusable components:

* Page container
* Page header
* Dense table
* Recommendation badges
* Primary, secondary, and ghost buttons
* Collapsible sections
* Command Palette
* Empty state
* Error state
* Loading skeleton
* Freshness indicators

These should be improved and consolidated rather than replaced with a new component library.

---

## 6.2 Metric component duplication

**Evidence:** Architecture finding
**Severity:** Moderate

Overlapping components include:

* `MetricCard`
* `StatTile`
* `SummaryStrip`
* `SummaryStripItem`
* Local metric-card implementations

These components all represent some variation of:

```text
Label
Value
Optional change
Optional status
Optional tooltip
Optional trend
```

### Recommended migration

Create a unified `MetricTile` primitive with controlled variants.

Example variants:

```text
compact
summary
card
inline
emphasized
```

Do not immediately delete existing components.

Use this migration process:

1. Add `MetricTile`.
2. Refactor existing components to wrap it.
3. Migrate page call sites gradually.
4. Remove wrappers only after all usages are stable.

---

## 6.3 Card and surface duplication

**Evidence:** Architecture finding
**Severity:** Moderate

Current variants include:

* `AppCard`
* `.app-card`
* `.surface-card`
* `.data-panel`
* Page-specific bordered panels

### Recommendation

Create one surface primitive with explicit variants:

```text
default
raised
interactive
data
inset
overlay
```

Do not make all cards clickable.

Do not apply hover movement to non-interactive surfaces.

---

## 6.4 Async state fragmentation

**Evidence:** Code verified and architecture finding
**Severity:** Major

The application uses:

* `AsyncSection`
* `LoadingSkeleton`
* `EmptyState`
* `ErrorState`
* Plain loading text
* Custom loading blocks
* Silently swallowed errors
* Page-specific refresh indicators

This creates inconsistent behavior across Portfolio, Scan, Analyze, Quant Lab, Library, and Settings.

### Recommended contract

Create a shared async-state shell supporting:

```text
idle
loading
refreshing
success
empty
error
stale
partial
```

Required behavior:

* Preserve existing data during refresh when possible
* Use skeletons matching the final structure
* Show retry actions for recoverable failures
* Display stale timestamps
* Use i18n strings by default
* Avoid full-page spinners when partial content is available

### Safe migration

1. Upgrade `AsyncSection`.
2. Make it compose the existing loading, empty, and error components.
3. Migrate one page at a time.
4. Do not replace all async states in one commit.

---

## 6.5 Tab and navigation primitives

**Evidence:** Architecture finding
**Severity:** Moderate

PickerQuant contains several visually similar control types:

* Route navigation links
* Page tabs
* Content-panel tabs
* Filters
* Segmented controls
* Settings section links

These should not all receive `role="tab"`.

### Accessibility rule

Use WAI-ARIA tab semantics only when controls switch between content panels within the same interface.

Use:

* `<a>` and `aria-current` for route navigation
* `<button>` and `aria-pressed` for filters
* `role="tablist"` and `role="tab"` for true tab panels
* Native `<select>` when it is the most usable mobile control

---

# 7. Navigation

## 7.1 Mobile primary navigation

**Evidence:** Code verified
**Severity:** Major for current local use; Blocking before public release

Primary desktop navigation is hidden below 768px.

There is no equally discoverable replacement.

Although the Command Palette can navigate, it is not sufficient as the only mobile navigation mechanism.

### First-pass recommendation

Do not initially build a complex mobile navigation system.

Implement one of these:

* Compact mobile menu button with a navigation drawer
* Four-item bottom navigation plus overflow
* Compact top bar with visible page switcher

Recommended initial structure:

```text
Portfolio
Scan
Analyze
Quant Lab
More
```

The More menu may contain:

```text
Library
Settings
Trader Intel
Theme
Language
```

---

## 7.2 Settings placement

**Evidence:** Specification mismatch
**Severity:** Moderate

Settings currently appears in primary navigation and a utility menu.

The design system places Settings in the utility area.

Recommended change:

* Remove Settings from the primary destination group.
* Keep it in the account or utility menu.
* Preserve direct route access.

This should happen after the mobile navigation structure is established.

---

## 7.3 Command Palette accessibility

**Evidence:** Code verified
**Severity:** Major

The Command Palette already supports useful keyboard behaviors, but it needs:

* Focus containment
* Focus restoration after closing
* Clear active-result semantics
* `aria-activedescendant` or equivalent active-item announcement
* Visible mobile access

Do not remove or replace the Command Palette. Improve its accessibility contract.

---

# 8. Keyboard Accessibility

## 8.1 Missing visible focus states

**Evidence:** Code verified
**Severity:** Blocking

Important shared controls do not consistently show visible `:focus-visible` states.

Affected categories include:

* Primary buttons
* Secondary buttons
* Ghost buttons
* Shared tabs
* Command rows
* Some icon buttons

This creates a serious keyboard-navigation barrier.

### Required implementation

Add a shared focus-ring token and apply it to all interactive primitives.

```css
:focus-visible {
  outline: 2px solid var(--color-ring);
  outline-offset: 2px;
}
```

Do not use `outline: none` without a visible replacement.

---

## 8.2 Icon-only controls

**Evidence:** Code spot check
**Severity:** Moderate

Some icon-only controls may not have accessible labels.

Required rule:

```text
Every icon-only button must include:
- aria-label, or
- visually hidden readable text
```

This must be verified page by page.

---

# 9. Charts and Financial Visualizations

## 9.1 Chart text alternatives

**Evidence:** Code verified
**Severity:** Major

Several charts communicate information visually without providing an accessible text summary.

This affects:

* Result charts
* Backtest charts
* Equity curves
* Some analytical visualizations

### Required pattern

Every important chart should include a concise textual summary.

Example:

```text
AAPL gained 8.4% over the selected 3-month period.
Maximum drawdown was 5.2%.
The latest available price is from June 29, 2026.
```

For complex analytical charts, provide either:

* Expandable data table
* Downloadable data
* Screen-reader-only summary
* Key-value summary below the chart

---

## 9.2 Correlation heatmap color-only encoding

**Evidence:** Code verified
**Severity:** Major

The portfolio correlation heatmap communicates magnitude primarily through color.

This creates accessibility and interpretation problems.

### Required change

Every cell should include:

* Numeric value
* Accessible label
* Tooltip or detail description
* Color as secondary reinforcement

Example:

```text
AAPL / MSFT
Correlation: 0.74
Strong positive correlation
```

---

## 9.3 Chart mounting and resize behavior

**Evidence:** Code verified
**Severity:** Moderate

`PriceChart` uses a chart-mount wrapper to avoid zero-size initial renders, but not all Recharts components use the same behavior.

Create a shared chart wrapper supporting:

* Responsive mounting
* Loading state
* Empty state
* Error state
* Text summary slot
* Latest-data timestamp
* Resize handling

Do not rewrite chart calculations.

---

# 10. Tables

## 10.1 Dense table inconsistency

**Evidence:** Code verified
**Severity:** Moderate

Some tables use the shared dense-table system, while others use local raw table implementations.

This produces inconsistent:

* Spacing
* Headers
* Numeric alignment
* Mobile overflow
* Row hover behavior
* Loading states

### Recommendation

Adopt the shared table wrapper gradually.

Required features:

* Sticky header option
* Numeric alignment
* Tabular numerals
* Optional caption
* Loading rows
* Empty rows
* Row selection
* Detail drawer support
* Responsive column priority

---

## 10.2 Mobile table behavior

**Evidence:** Browser validation required
**Severity:** Moderate

The Scan table currently relies heavily on horizontal scrolling.

This may be acceptable for comparison-heavy workflows.

Do not automatically convert Scan rows into cards.

Test the following approaches in the browser:

1. Essential columns plus detail drawer
2. Horizontal scroll with sticky symbol column
3. Column priority selector
4. Compact card rows only if comprehension improves

Use page-specific behavior rather than one universal mobile table rule.

---

# 11. Loading, Empty, Error, and Stale States

## 11.1 Library errors are silently swallowed

**Evidence:** Code verified
**Severity:** Major

Some Library request failures are converted into empty results.

This can cause the user to interpret an error as an empty Library.

### Required change

Differentiate:

```text
Empty library
Request failed
Offline
Unauthorized
Partial data
```

Show an error state with retry when data cannot be loaded.

---

## 11.2 Plain loading text

**Evidence:** Code verified
**Severity:** Moderate

Several areas use plain text such as:

```text
Loading…
No data.
No chart data.
```

Problems include:

* Inconsistent presentation
* Hardcoded English
* Poor layout stability
* Weak visual feedback

Use structured skeletons for operations expected to take more than approximately 300 milliseconds.

---

## 11.3 Stale data

**Evidence:** Code verified
**Severity:** Moderate

Portfolio and Scan already contain useful data-freshness patterns.

These patterns should become reusable rather than being recreated independently.

Each major financial dataset should expose:

* Last updated time
* Fresh, stale, or unavailable status
* Refresh action
* Refresh-in-progress state
* Whether calculations are using stale data

Do not show stale financial information without an explicit freshness indicator.

---

# 12. Page-Specific Findings

# 12.1 Portfolio/Home

## Assessment

The current Portfolio page is functionally valuable and should not be rebuilt from scratch.

The primary goal should be:

* Better grouping
* Reduced scattering
* Clearer hierarchy
* Fewer competing banners
* More consistent metric presentation

## Code-verified findings

### Tabs inside the page-header action area

**Severity:** Moderate

This creates a different pattern from Scan and Quant Lab and may compete with page actions.

Recommended structure:

```text
Page title and utilities
Summary metrics
Portfolio tabs
Primary holdings workspace
Secondary allocation and risk panels
```

### Multiple banner types

**Severity:** Moderate, subject to browser confirmation

Potentially overlapping banners include:

* Public demo status
* Data freshness
* Demo data
* Dismissible notices

Do not remove their meaning.

Instead:

* Merge compatible environment notices
* Use one reserved notification area
* Collapse secondary notices
* Keep critical stale-data warnings visible

## Browser validation required

Verify:

* Whether summary metrics appear scattered
* Whether header actions wrap
* Whether banners actually stack in normal use
* Whether the holdings table remains primary
* Whether risk and allocation panels repeat information

---

# 12.2 Scan

## Assessment

The Scan page already has a strong dense-table foundation.

The redesign should focus on:

* Faster visual comparison
* Better loading and partial-result states
* Mobile column prioritization
* Cleaner header hierarchy
* Stronger detail inspection

## Code-verified findings

### Loading state inconsistency

**Severity:** Moderate

Scan uses less structured loading feedback than Portfolio and Analyze.

Recommended states:

```text
Preparing universe
Downloading data
Filtering candidates
Ranking results
Finalizing evidence
Partial results available
```

This is more informative than a generic spinner.

### Existing horizontal-scroll table

**Severity:** Moderate, browser validation required

Do not convert to cards by default.

Test a sticky symbol column and detail drawer first.

## Browser validation required

Verify whether the page header is actually overcrowded at:

* 390px
* 768px
* 1024px
* 1440px

Do not remove bucket descriptions or freshness information without proving they create measurable clutter.

---

# 12.3 Analyze/Workspace

## Assessment

Analyze is appropriately more complex than the other pages because it serves advanced users.

Its density should be refined, not simplified into a basic consumer dashboard.

## Code-verified findings

### Many controls and views

**Severity:** Moderate

The workspace contains:

* Symbol selection
* Metadata
* Multiple analytical views
* Charts
* Secondary evidence
* Optional side rail

This is acceptable for the page’s role.

Recommended improvements:

* Group related tabs
* Distinguish primary analysis from secondary research
* Keep the price chart and current decision visible
* Show the latest data date prominently
* Use an inspector for secondary evidence on narrower screens

### Mobile symbol selection discoverability

**Severity:** Moderate

A native symbol selector is functional, but users may not understand what to do when no symbol is selected.

Improve the empty state with:

* Prominent symbol search
* Recent symbols
* Watchlist preview
* Suggested starting actions

## Browser validation required

Verify the reported empty right margin between approximately 1024px and 1279px.

Do not change the grid until the running layout confirms the issue.

---

# 12.4 Quant Lab

## Assessment

Quant Lab is inherently information-dense.

The goal should not be to make it visually minimal. The goal should be to make the research workflow understandable.

Recommended workflow hierarchy:

```text
Experiment setup
Validation configuration
Execution status
Results
Evidence
Interpretation
Comparison
Export or save
```

## Likely crowding issue

**Evidence:** Browser validation required
**Severity:** Moderate until confirmed

The combination of:

* Page header
* Research status badge
* Section navigation
* Collapsible evidence
* Product explanation
* Experiment content

may place too much material before the active workspace.

### Recommended browser experiment

Test:

* Sticky section sub-navigation
* Evidence panels collapsed by default
* Product explanation moved to an info drawer
* Last-used experiment section restored automatically

Do not remove experimental capability.

---

# 12.5 Library

## Assessment

Library has one confirmed reliability issue and several consistency opportunities.

### Confirmed issue: swallowed errors

**Severity:** Major

Fix error-state differentiation before visual redesign.

### Layout observation

The list-and-detail layout is appropriate.

Browser validation should determine whether:

* The empty detail panel wastes space
* A preview state would be more useful
* Mobile should navigate between list and detail views instead of stacking both

---

# 12.6 Settings

## Assessment

Settings contains one of the strongest responsive patterns in the application.

It uses:

* Desktop section navigation
* Mobile native selection
* URL-persisted section state
* Appropriate semantic structure

This pattern should be reused elsewhere when appropriate.

Do not redesign Settings merely for visual consistency.

Priorities:

* Theme control
* Navigation cleanup
* Shared input and button focus states
* Accessible section labels
* Consistent async feedback

---

# 13. Responsive Design

## 13.1 Required validation sizes

Every primary page must be inspected at:

```text
390px
768px
1024px
1440px
```

Optional additional checks:

```text
375px
1280px
1536px
```

## 13.2 Confirmed responsive issue

### Primary navigation below 768px

**Evidence:** Code verified
**Severity:** Major now; Blocking for public release

Implement a discoverable mobile navigation alternative.

## 13.3 Findings requiring browser confirmation

* Portfolio tabs wrapping
* Analyze side-panel empty space
* Quant Lab vertical crowding
* Scan header crowding
* Footer consuming excessive mobile height
* Library detail-panel whitespace

No major page restructuring should be approved before these are visually confirmed.

---

# 14. Motion

## Current direction

PickerQuant supports moderate motion.

Appropriate motion includes:

* Drawers
* Dropdowns
* Tabs
* Data refresh indicators
* Chart transitions
* Expandable sections
* Brief financial value highlights

Avoid:

* Animated counting values
* Card-lift movement
* Large page-entry animations
* Repeated decorative motion

## Reduced motion

**Evidence:** Code verified
**Severity:** Moderate

Reduced-motion support exists in parts of the CSS, but skeleton pulse animations may not fully respect it.

Update shared skeletons to disable pulsing when reduced motion is requested.

---

# 15. Revised Implementation Plan

# Phase 0 — Baseline and Verification

Complete before editing shared UI architecture.

## Tasks

1. Correct the design-system path.
2. Create page-specific override files.
3. Run the current frontend.
4. Capture screenshots at required breakpoints.
5. Label visual findings as confirmed or rejected.
6. Inventory current page functionality.
7. Record current lint, type-check, test, and build status.
8. Record all current Portfolio actions and metrics.
9. Record all current Scan columns and filters.
10. Record all Analyze views and controls.
11. Record all Quant Lab experiment capabilities.

## Required output

```text
docs/ui-baseline/
docs/UI_AUDIT_REVISED.md
design-system/pages/
```

---

# Phase 1 — Accessibility and Navigation Safety

## Tasks

1. Add visible focus rings to all shared controls.
2. Audit icon-only buttons for labels.
3. Add discoverable mobile navigation.
4. Improve Command Palette focus handling.
5. Add numeric correlation values.
6. Add textual summaries to important charts.
7. Ensure reduced-motion support covers skeletons.

## Guardrails

* Do not redesign page layouts in this phase.
* Do not change recommendation colors.
* Do not change chart calculations.
* Do not change navigation routes.

---

# Phase 2 — Semantic Token Foundation

## Tasks

1. Introduce semantic tokens matching the Master file.
2. Separate interaction blue from financial green.
3. Map existing surfaces and text colors.
4. Define dark and light token sets.
5. Apply dark tokens to shared primitives first.
6. Create a semantic-color linting or review rule.

## Required migration order

```text
Buttons
Navigation
Tabs
Inputs
Badges
Tables
Cards
Charts
Page-specific components
```

## Guardrails

* No global color replacement.
* Every green use must be classified.
* Financial badges must retain their existing meaning.
* Dark theme remains the validated default.

---

# Phase 3 — Shared Component Consolidation

## Priority order

1. Async state shell
2. Button focus and interaction states
3. Card and panel primitive
4. Metric tile system
5. Tab and segmented-control contracts
6. Chart wrapper
7. Dense table wrapper

## Compatibility rule

Existing components should temporarily wrap new primitives.

Do not delete old components until:

* All call sites are migrated
* Tests pass
* Visual comparison passes
* No information has disappeared

---

# Phase 4 — Page-Level Redesign

## Recommended order

1. Application shell and navigation
2. Portfolio
3. Scan
4. Analyze
5. Quant Lab
6. Library
7. Settings polish

## Portfolio objective

Reorganize without reducing functionality.

## Scan objective

Improve comparison, partial-result feedback, and detail inspection.

## Analyze objective

Improve hierarchy while preserving advanced analytical depth.

## Quant Lab objective

Clarify the experiment workflow and progressively disclose evidence.

## Library objective

Fix reliability first, then improve list/detail behavior.

## Settings objective

Add theme control and preserve its strong responsive structure.

---

# Phase 5 — Light Theme

Implement after dark-theme components are stable.

## Tasks

1. Add theme preference control.
2. Persist theme selection.
3. Validate all shared components.
4. Validate charts and financial badges.
5. Run contrast checks.
6. Confirm stale, loading, empty, and error states.
7. Validate all primary pages.

---

# Phase 6 — Cleanup and Removal

Only after all migrations are complete.

## Tasks

1. Remove compatibility wrappers that are no longer used.
2. Delete obsolete card and metric implementations.
3. Remove unused CSS classes.
4. Remove hardcoded legacy colors.
5. Consolidate duplicate loading and error components.
6. Standardize product naming.
7. Update design-system documentation.
8. Update the audit with resolved findings.

---

# 16. Migration Guardrails

Cursor must follow these rules throughout implementation.

## Business-logic protection

Do not change:

* Recommendation calculations
* Ranking logic
* Portfolio calculations
* Buy/Hold/Sell percentages
* Backtest results
* Scan filters
* API contracts
* Data-refresh logic
* Experiment definitions
* Risk calculations
* Market-data transformations

## Visual migration safety

Do not:

* Implement all audit findings in one task
* Run a blind color codemod
* Delete existing shared components immediately
* Convert every table to cards
* Apply tab ARIA semantics to route links
* Remove content to create simplicity
* Build light and dark page polish simultaneously
* Rewrite page layouts before browser validation
* Replace functional native mobile controls without evidence

## Commit strategy

Use one commit for each stable unit.

Example:

```text
fix(ui): restore visible keyboard focus
feat(nav): add compact mobile navigation
refactor(ui): introduce semantic interaction tokens
refactor(ui): unify async state handling
refactor(ui): add metric tile compatibility layer
feat(portfolio): reorganize portfolio workspace
feat(scan): improve scan result hierarchy
feat(workspace): refine analysis layout
feat(quant-lab): clarify experiment workflow
feat(theme): add validated light theme
```

---

# 17. Validation Requirements

After every phase:

## Automated validation

* Lint
* Type checking
* Unit tests
* Component tests where available
* Production build

## Visual validation

Inspect at:

* 390px
* 768px
* 1024px
* 1440px

## Functional validation

Confirm:

* All routes still work
* URL-persisted state still works
* Portfolio data is unchanged
* Scan results are unchanged
* Analyze chart data is unchanged
* Quant Lab experiment behavior is unchanged
* Buy/Hold/Sell percentages remain visible
* Data freshness remains visible
* Refresh behavior still works
* Settings persist correctly

## Accessibility validation

Confirm:

* Keyboard-only navigation
* Visible focus states
* Tab order
* Accessible names for icon buttons
* Chart summaries
* Correlation values readable without color
* Reduced-motion behavior
* Screen-reader-friendly status messages

---

# 18. Updated Priority Summary

## Blocking

1. Missing visible keyboard focus on shared primary controls

## Major

1. Mobile navigation absent below 768px
2. Design-system path mismatch
3. Interaction and financial color semantics conflict
4. Fragmented async-state handling
5. Library errors presented as empty data
6. Charts missing text alternatives
7. Correlation heatmap relies on color
8. Command Palette focus handling incomplete
9. Light theme promised but not implemented

## Moderate

1. Metric component duplication
2. Card abstraction duplication
3. Inconsistent table primitives
4. Inconsistent tab/control semantics
5. Portfolio tab placement
6. Potential notice stacking
7. Scan loading feedback
8. Analyze empty-state discoverability
9. Quant Lab information hierarchy
10. Reduced-motion gaps
11. Inconsistent hardcoded secondary text
12. Settings duplication in navigation
13. Mobile table strategy
14. Icon-button labeling audit
15. Chart wrapper inconsistency

## Minor

1. PickerQuant versus Picker Daily naming
2. Root route described as Home versus Portfolio
3. Minor typography scale differences
4. Some hardcoded English strings
5. Button active scaling
6. Redundant local component implementations
7. Footer mobile density
8. Legacy styling classes after migration

---

# 19. Final Assessment

PickerQuant does not need a complete visual rebuild.

It needs a controlled frontend-system consolidation followed by page-specific organization improvements.

The correct implementation strategy is:

```text
Verify
Protect
Fix accessibility
Establish semantic tokens
Consolidate shared components
Redesign pages individually
Implement light mode
Remove obsolete code
```

The greatest implementation risk is not under-design.

The greatest risk is allowing Cursor to:

* Change too many systems simultaneously
* Remove useful information
* Perform a global color replacement
* Delete compatibility components too early
* Treat every navigation control as a tab
* Redesign pages before visually validating the reported problems

No code should be modified until Phase 0 is complete and the design-system path has been corrected.

**End of revised audit.**
