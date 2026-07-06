# Factor Discovery — universe PIT policy

Policy ID: `universe_pit_membership_v1`

## Meaning

`universe_pit` rows represent historical eligibility at each score date (`as_of_date`, `symbol`, `is_active`).

## Requirements

- No backward application of current active-symbol lists
- Interval imports expanded deterministically to daily membership
- Exit dates preserved where provided
- Constant membership across long windows flagged as survivorship risk

## Staging blockers

- Empty `universe_pit`
- Constant membership without documented reason
- Duplicate membership rows
- Insufficient date coverage
