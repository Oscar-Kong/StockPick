# Architecture Decision Records

ADRs capture **hard-to-reverse** decisions with enough context that future engineers and agents do not re-litigate them.

Format follows Matt Pocock `domain-modeling` conventions: `NNNN-short-slug.md`, often a single paragraph. Optional status frontmatter when decisions are revisited.

## When to add an ADR

All three must be true:

1. Hard to reverse
2. Surprising without context
3. Result of a real trade-off

Otherwise update the relevant doc in `docs/` or a code comment — do not add noise here.

## Index

| ADR | Summary |
|-----|---------|
| [0001-product-surface-boundaries.md](./0001-product-surface-boundaries.md) | Scan vs Quant Lab vs Portfolio responsibilities |

## Broader architecture (not duplicated here)

Detailed module layout, formulas, and roadmaps live in existing docs:

- [ARCHITECTURE.md](../ARCHITECTURE.md)
- [INSTITUTIONAL_QUANT_ARCHITECTURE.md](../INSTITUTIONAL_QUANT_ARCHITECTURE.md)
- [QUANT_LAB.md](../QUANT_LAB.md)
- [SCAN_EVALUATION.md](../SCAN_EVALUATION.md)
