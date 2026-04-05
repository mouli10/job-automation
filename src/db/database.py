from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from src.shared_constants import DATABASE_URL, DATA_DIR

# Ensure DB directory exists if sqlite
if DATABASE_URL.startswith("sqlite"):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

# Engine Creation - No longer depends on src.config 🦾🏗️
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # Optimized for Cloud Postgres (Supabase)
    engine = create_engine(DATABASE_URL, pool_size=10, max_overflow=20)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
