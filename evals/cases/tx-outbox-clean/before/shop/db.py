"""Engine and session factory. Production: PostgreSQL 16 (psycopg 3), READ COMMITTED."""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(os.environ.get("DATABASE_URL", "sqlite://"), pool_size=20) if os.environ.get("DATABASE_URL") \
    else create_engine("sqlite://")
Session = sessionmaker(engine, expire_on_commit=False)
