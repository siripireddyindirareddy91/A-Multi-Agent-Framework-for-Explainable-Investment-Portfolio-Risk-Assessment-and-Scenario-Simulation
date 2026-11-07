# Verification — 7 November 2026

- `python -m pytest backend/tests -q`: **5 passed**. Covers financial invariants and reproducibility, invalid inputs, exact scenario losses, account and holding CRUD, CSV rejection, persisted settings, ownership isolation, real LangGraph execution, reviewer authorization and explicit approval, saved simulations, evidence answers, counterfactuals, PDF signatures and CSV exports.
- `npm run build`: **passed** (Next.js production compilation, TypeScript checks, prerender and bundle generation).
- `npm run typecheck`: **passed**.
- `npm audit`: **0 vulnerabilities** after overriding PostCSS with a patched version.
- First Vercel deployment: **Ready**, frontend plus Python ASGI function. Live `/api/health`, portfolio listing and analytical metrics returned successfully. Combined rewrite correctly reaches FastAPI.
- A NumPy-scalar checkpoint serialization failure found by the integration test was fixed by normalizing metrics to JSON-native types before graph execution. Full suite passed afterward.
- Browser preview: in-app browser initialization timed out. Visual UI and click-through browser QA are not claimed. HTTP/API checks and the production build were completed.
- PostgreSQL-specific integration was not run. Local tests use isolated file-backed SQLite. Hosted SQLite is temporary; no managed database credentials were available.
- Vercel's automatic GitHub integration could not connect because its integration lacked repository write access. Direct Git push and CLI deployments use separate authentication.
- Final deployment `dpl_3nx7xNgyeg45cBPHhe9eCdGusT4u`: **READY** at https://aegis-risk-intelligence.vercel.app. A live POST analysis returned eight agent statuses and two recommendations; a saved equity crash simulation returned a calculated 24.7787% loss; the live PDF endpoint returned HTTP 200, `application/pdf`, 3,771 bytes. A stable production JWT_SECRET was configured in Vercel.
- Source was pushed to the requested GitHub repository on `main`, preserving its initial commit. GitHub auto-deployment integration remains disconnected; deployments were performed successfully through the authenticated Vercel CLI.

The test suite is backend/API integration coverage, not Playwright browser end-to-end coverage or a regulatory/security certification.

## Enterprise follow-up

- Free Neon PostgreSQL resource `aegis-production-db` provisioned in iad1 and connected to Vercel production. Live health reports `database=postgresql`, `durable=true`.
- Production `REQUIRE_AUTH=true`; protected APIs require login. Cookie authentication verified live with the analyst account. Cookies are HttpOnly, SameSite=Strict and Secure on Vercel; logout clears the browser cookie.
- Left navigation now scrolls independently with a fixed-height sidebar and thin visible scrollbar.
- Constrained long-only SLSQP optimizer added, persisted and exposed in Recommendations. Live solver returned 12 positions with Pending Review status. Tests validate full investment, asset bounds, sector caps and infeasible inputs.
- Seven backend test groups passed; production build passed. Alembic baseline upgrade passed locally.
- Shared sample portfolio writes are restricted to their owning demo account; other signed-in users can read samples and create/edit their own portfolios. Cross-site cookie mutations are rejected.
- GitHub auto-link retried and still refused by Vercel due to GitHub App repository permissions. This account-level authorization remains unresolved; authenticated Git push and CLI deployment continue to work.
- Remaining enterprise scope: fifteen fully normalized domain tables, durable resumable job/checkpoint execution, paid LLM/live market adapters, password recovery, tenant administration, browser automation coverage and independent security/financial model validation are not completed.

## Website regression pass

- Nine backend/API test groups pass, including all workspace service reads, portfolio/holding create-edit-delete, valid/invalid CSV uploads, review approval/rejection/revision, idempotent review submission, ownership and cross-site protections, login/logout, optimization and all report types.
- Fixed exports and counterfactual comparisons ignoring the selected confidence, historical window, simulation count and seed. Regression tests compare exported VaR to the dashboard calculation under a non-default configuration.
- Portfolio refresh now applies results atomically and discards superseded responses. Comparison components reset when switching portfolios/settings.
- Production build and TypeScript checks pass. `scripts/smoke.py` provides live cookie-authenticated API checks for all ten workspace services and four downloads.
- In-app browser navigation timed out again. No claim is made that every visible button was clicked, that visual layout was verified in this pass, or that browser-level coverage is complete.
