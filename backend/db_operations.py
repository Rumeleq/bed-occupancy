import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()


def get_session() -> Session:
    """
    Create a SQLAlchemy engine for connecting to the PostgreSQL database.
    The connection parameters are read from environment variables.
    If the environment variables are not set, default values are used.
    :return:
    """
    try:
        DB_USER = os.getenv("POSTGRES_USERNAME", "postgres")
        DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
        DB_NAME = os.getenv("POSTGRES_NAME", "postgres")
        DB_HOST = os.getenv("POSTGRES_HOST", "db")
        DB_PORT = os.getenv("POSTGRES_PORT", "5432")
        DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(bind=engine, autoflush=True, autocommit=False, future=True)
        return SessionLocal()
    except Exception as e:
        print(f"Failed to connect: {e}")
        raise
