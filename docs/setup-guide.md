# Setup and deployment

See the root README for commands and environment variables. Install Python requirements, run Uvicorn on port 8000 and run Next on port 3000 with BACKEND_URL configured. Seed data is inserted on first import when DEMO_MODE=true. Use a new database for a fresh seed.

For production use a managed PostgreSQL URL using the psycopg SQLAlchemy dialect. PostgreSQL schema version 1 is initialized with SQLAlchemy `create_all`. Schema changes need an explicitly reviewed migration; no destructive automatic migration runs. Configure a stable 32+ character JWT_SECRET. Disable DEMO_MODE for private deployments and provision a reviewer account using a controlled administrative process.

Vercel's combined deployment uses `api/index.py` and the root requirements.txt. Avoid putting secrets in source or client-visible variables. The CLI or Vercel project settings can supply runtime environment variables. Set database connection limits appropriately for serverless workloads.

The local Docker Compose stack includes PostgreSQL, FastAPI and Next.js. Frontend BACKEND_URL is a build argument because Next.js proxy configuration is evaluated at build time.
