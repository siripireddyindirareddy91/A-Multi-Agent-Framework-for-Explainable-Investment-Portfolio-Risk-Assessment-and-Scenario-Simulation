# Architecture decisions

Next.js serves a responsive single-page workspace with ten navigation views, Recharts visualizations and Lucide icons. FastAPI owns validation, financial tools, authorization, persistence, orchestration and downloads. The frontend does not generate risk metrics.

LangGraph uses eight specialist nodes. The first six compute structured findings, then human review creates a required decision gate. The report node is not executed while review is pending; the UI shows its awaiting-approval state. Reports can be explicitly exported as analytical drafts. In-memory checkpointing supports execution, while SQLAlchemy stores final snapshots and traces. Durable checkpoint recovery and post-approval graph continuation remain future work.

For rapid deployment, a relational user table and indexed typed-record table store the application's domain objects as JSON. This provides transactional writes and PostgreSQL compatibility without claiming the brief's fully normalized enterprise schema. All accounts have ownership-scoped records. Demo portfolios are deliberately shared, and reviewers can inspect submitted cases.

The numerical engine is independent of API/database code and uses seeded synthetic samples. Rule-based explanations consume computed results; no provider can invent financial values. Scenario outcomes preserve inputs. Human review stores original recommendation evidence and each explicit signed-in decision with timestamps and rationale.
