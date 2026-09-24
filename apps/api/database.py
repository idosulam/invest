"""Database session and engine management."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from typing import AsyncGenerator

from apps.api.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.api_env == "development",
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields a database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def _stamp_alembic_to_head() -> None:
    """Mark Alembic at 'head' to match the create_all schema (dev convenience).

    `create_all` builds the schema from the *current* models, which already
    include anything the additive migrations add (e.g. strategy_performance,
    signals.target_price). Without this, `alembic upgrade head` re-creates those
    tables/columns and fails with DuplicateTable. Stamping reconciles the two.
    """
    try:
        import os
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        from sqlalchemy import text as _text

        root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        cfg = Config(os.path.join(root, "alembic.ini"))
        cfg.set_main_option("script_location", os.path.join(root, "db", "migrations"))
        head = ScriptDirectory.from_config(cfg).get_current_head()
        if not head:
            return
        async with engine.begin() as conn:
            await conn.execute(_text(
                "CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(64) NOT NULL)"
            ))
            await conn.execute(_text("DELETE FROM alembic_version"))
            await conn.execute(
                _text("INSERT INTO alembic_version (version_num) VALUES (:h)"), {"h": head}
            )
    except Exception as e:  # noqa: BLE001 — dev convenience, never fatal
        logging.getLogger(__name__).warning(f"alembic stamp (dev) failed: {e}")


async def init_db() -> None:
    """Create all tables (for development only, use Alembic in production)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Keep Alembic's version in sync with the create_all schema so
    # `alembic upgrade head` doesn't collide with it (see _stamp_alembic_to_head).
    await _stamp_alembic_to_head()


async def close_db() -> None:
    """Dispose of the engine connection pool."""
    await engine.dispose()
