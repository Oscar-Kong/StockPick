# Factor Discovery — factor registry (Phase 9A)

## API

| Method | Path |
|--------|------|
| GET | `/api/v2/research/factor-discovery/factors` |
| GET | `/api/v2/research/factor-discovery/factors/{factor_id}` |
| GET | `/api/v2/research/factor-discovery/factors/{factor_id}/versions/{version}` |

List filters: `search`, `lifecycle_status`, `direction`, `promising_only`, `has_validation`.

## UI

Quant Lab **Factors** tab uses `FactorRegistryPanel` (persisted definitions, not LLM candidate list).

Distinct labels:

- **Lifecycle** — compile/draft state of the definition
- **Latest research gate** — acceptance rule outcome from closed artifact
- **Promising review** — human-review policy result (not investment approval)

No production activation controls.
