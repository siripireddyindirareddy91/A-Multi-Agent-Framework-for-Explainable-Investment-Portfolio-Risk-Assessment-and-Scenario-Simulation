import os
from alembic import context
from sqlalchemy import create_engine
from backend.app.main import Base, DB
target_metadata=Base.metadata
if context.is_offline_mode():
 context.configure(url=DB,target_metadata=target_metadata,literal_binds=True)
 with context.begin_transaction():context.run_migrations()
else:
 with create_engine(DB).connect() as connection:
  context.configure(connection=connection,target_metadata=target_metadata,compare_type=True)
  with context.begin_transaction():context.run_migrations()
