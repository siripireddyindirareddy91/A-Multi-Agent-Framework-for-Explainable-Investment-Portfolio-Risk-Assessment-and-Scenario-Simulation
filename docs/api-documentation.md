# API

Interactive OpenAPI documentation is available at `/docs` on the FastAPI server. APIs use JSON with Bearer JWT authorization. Public demo mode falls back to a shared analyst only when no token is supplied. Invalid tokens return 401. Review decisions require reviewer/administrator roles; registration creates analysts only.

Primary endpoints:

| Method | Path | Purpose |
| --- | --- | --- |
| GET | /api/health | Runtime and persistence status |
| POST | /api/auth/register, /api/auth/login | Account creation or session token |
| GET | /api/auth/me | Current identity |
| GET, POST | /api/portfolios | List/create portfolios |
| GET, PUT, DELETE | /api/portfolios/{id} | Read/edit/delete |
| GET, POST | /api/portfolios/{id}/holdings | List/add holdings |
| PUT, DELETE | /api/portfolios/{id}/holdings/{holding_id} | Edit/remove |
| POST | /api/portfolios/{id}/upload-csv | Validated replacement upload |
| GET | /api/portfolios/{id}/analytics | Compute metrics with query configuration |
| POST | /api/agents/run-analysis | Execute and persist workflow |
| GET | /api/portfolios/{id}/analyses | Stored analysis snapshots and traces |
| GET | /api/scenarios | Economic templates |
| POST | /api/portfolios/{id}/simulate | Calculate and save shocks |
| GET | /api/portfolios/{id}/scenarios | Saved outcomes |
| POST | /api/portfolios/{id}/counterfactual | Compare explicit allocations |
| POST | /api/portfolios/{id}/chat | Rule-based evidence retrieval |
| GET | /api/portfolios/{id}/recommendations | Evidence-backed suggestions |
| POST | /api/recommendations/{id}/submit-review | Create idempotent review case |
| GET | /api/reviews | Role-filtered review queue |
| POST | /api/reviews/{id}/decision | Approve/reject/request revision |
| GET | /api/audit | Current user's recorded actions |
| GET, PUT | /api/settings | Persist calculation preferences |
| GET | /api/portfolios/{id}/export/{kind} | pdf, holdings, metrics, scenarios |

Invalid numeric data is rejected; CSV size is bounded at 1 MB and 100 holdings. Process-local rate limiting bounds requests per client/minute; distributed production rate limiting is not implemented.
