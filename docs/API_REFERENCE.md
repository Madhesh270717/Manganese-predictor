# API Reference — Spotter AI (Phase 22)

All endpoints are versioned under **`/api/v1`**. Read-only GET endpoints are
open for the demo; **mutating POST endpoints require the `X-API-Key` header**
(value: `spotter-demo`, env-configurable — a production system would use
OAuth2/JWT with the PRD §4 roles). Documented security scope decision.

## Response format

Two formats are used, deliberately:

1. **Plain payloads** — most endpoints return the data object directly.
2. **Error envelope** — all error responses (404/422/500) use
   `{success: false, data: null, error: {code, message}}`.
3. **GeoJSON exception** — `/zones` endpoints return raw GeoJSON
   (FeatureCollection/Feature) so they remain valid for map libraries;
   they are NOT wrapped in an envelope. Documented exception.

Confidence tagging (PRD §39): every dataset-touching response carries the
Phase 3 confidence metadata (`source_type`, `confidence_level`,
`source_name`) or a `data_type` disclaimer field.

## Module map

| Module | Endpoints |
| --- | --- |
| Health | `GET /health`, `GET /health/ready` |
| Data confidence (P3) | `GET /data-confidence`, `GET /data-confidence/{dataset}` |
| Zones grid (P4) | `GET /zones`, `GET /zones/{zone_id}` |
| Geological (P5) | `GET /zones/{zone_id}/geological` |
| Drilling (P6) | `GET /zones/{zone_id}/drilling`, `GET /zones/{zone_id}/drilling/{drill_id}` |
| Satellite (P7) | `GET /zones/{zone_id}/satellite`, `GET /zones/{zone_id}/satellite/latest` |
| Weather (P8) | `GET /zones/{zone_id}/weather`, `GET /zones/{zone_id}/weather/current`, `GET /weather/risk-alert` |
| Equipment & blasting (P9) | `GET /equipment`, `GET /equipment/{id}`, `GET /equipment/{id}/history`, `GET /equipment/by-zone/{zone}`, `GET /zones/{zone_id}/blasting` |
| Schedule (P10) | `GET /schedule/current`, `GET /schedule/current/by-equipment/{id}`, `GET /production/history`, `GET /production/current-target` |
| Features (P11) | `GET /features/reserve/{zone_id}` |
| Prospectivity (P12) | `GET /reserve/prospectivity`, `GET /reserve/prospectivity/{zone_id}` |
| Resource estimate (P13) | `GET /reserve/resource-estimate`, `GET /reserve/resource-estimate/{zone_id}` |
| Mineability (P14) | `GET /mineability`, `GET /mineability/{zone_id}` |
| Production prediction (P15) | `GET /production/predict/current`, `POST /production/predict/scenario` 🔑 |
| Shortfall (P16) | `GET /production/shortfall/current`, `POST /production/shortfall/scenario` 🔑 |
| Explainability (P17) | `GET /production/shortfall/current/explain`, `POST /production/shortfall/scenario/explain` 🔑 |
| Optimization foundation (P18) | `POST /optimization/validate-schedule` 🔑 |
| Alternative zones (P19) | `GET /optimization/risks`, `GET /optimization/alternatives/{equipment_id}` |
| Recommendations (P20) | `GET /recommendations`, `GET /recommendations/{equipment_id}`, `GET /recommendations/{equipment_id}/schedule-comparison` |
| Recalculation (P21) | `POST /recalculation/trigger` 🔑, `GET /recalculation/history`, `GET /recalculation/status` |
| AI Assistant (P29) | `POST /assistant/chat`, `GET /assistant/audit` |

🔑 = requires `X-API-Key: spotter-demo`.

## AI Assistant (Module 5, Phase 29)

`POST /api/v1/assistant/chat` — natural-language query over the real backend
modules (PRD Sections 26–27, 37).

```json
{
  "message": "Why should we leave Zone A?",
  "conversation_history": [
    { "role": "user", "content": "Why is production expected to fall?" },
    { "role": "assistant", "content": "Production is expected to fall short." }
  ]
}
```

Response (always grounded in real model/service calls):

```json
{
  "response": "Regarding why A1 was postponed: A1 currently has a HIGH risk trigger ...",
  "functions_called": ["schedule_risks", "recommendations", "mineability"],
  "data_sources_used": ["Optimization Engine", "Weather Data", "Production Model", "Mineability", "Equipment Data"]
}
```

Design notes:
- The LLM (Anthropic tool-use, `LLM_API_KEY` / `LLM_MODEL`) only classifies
  which backend function(s) the question maps to and formats the raw results
  into plain language — it never invents figures (PRD Section 27). With no
  key configured, a deterministic fallback formatter answers from the same
  real tool results.
- Every turn is appended to `ml/data/processed/assistant_audit.jsonl`
  (question, functions called, data sources, grounded flag) — viewable via
  `GET /api/v1/assistant/audit`.
- `functions_called` / `data_sources_used` let the frontend show
  "this answer is based on: ..." transparency.

## Breaking changes in Phase 22

- Phase 1 placeholder ping endpoints (`/reserve/ping`, `/mineability/ping`,
  `/production/ping`, `/optimization/ping`, `/assistant/ping`) were removed —
  their module functionality is served by the real routers above.
- Error responses now use the consistent envelope (previously plain
  `{"detail": ...}`).
- Mutating POST endpoints now return 401 without the API key.

## Auth key configuration

Set the demo key via environment variable `SPOTTER_API_KEY` (default
`spotter-demo`). Read-only GETs remain open — documented prototype scope.
