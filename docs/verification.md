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

The test suite is backend/API integration coverage, not Playwright browser end-to-end coverage or a regulatory/security certification.
