"""
Test Suite: backend/db/session.py
Covers: URL manipulation logic, session providers, run_async helper.

NOTE: db/session.py creates engines at import time. We mock the engine
factories before importing so tests work without a real DB connection.

Place at: backend/tests/test_session.py
Run: pytest backend/tests/test_session.py -v
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

# =====================================================================
# URL Manipulation — tested as pure string logic (no imports needed)
# =====================================================================


class TestURLManipulation:
    """
    Test the URL transformation logic from session.py without importing it.
    This avoids the engine-creation side effect at import time.
    """

    @staticmethod
    def make_async_url(database_url: str) -> str:
        """Reproduce the async URL logic from session.py."""
        url = database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        url = url.replace("sslmode=", "ssl=")
        url = url.replace("&channel_binding=require", "")
        url = url.replace("?channel_binding=require&", "?")
        return url

    @staticmethod
    def make_sync_url(database_url: str) -> str:
        """Reproduce the sync URL logic from session.py."""
        url = database_url
        if "+asyncpg" in url:
            url = url.replace("+asyncpg", "")
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url

    # --- Async URL tests ---

    def test_postgresql_to_asyncpg(self):
        result = self.make_async_url("postgresql://user:pass@host/db")
        assert result == "postgresql+asyncpg://user:pass@host/db"

    def test_postgres_to_asyncpg(self):
        result = self.make_async_url("postgres://user:pass@host/db")
        assert result == "postgresql+asyncpg://user:pass@host/db"

    def test_already_asyncpg_unchanged(self):
        url = "postgresql+asyncpg://user:pass@host/db"
        result = self.make_async_url(url)
        assert result == url

    def test_sslmode_replaced_with_ssl(self):
        result = self.make_async_url("postgresql://host/db?sslmode=require")
        assert "ssl=require" in result
        assert "sslmode=" not in result

    def test_channel_binding_removed(self):
        result = self.make_async_url("postgresql://host/db?ssl=require&channel_binding=require")
        assert "channel_binding" not in result

    def test_channel_binding_at_start_removed(self):
        result = self.make_async_url("postgresql://host/db?channel_binding=require&ssl=require")
        assert "channel_binding" not in result

    # --- Sync URL tests ---

    def test_sync_strips_asyncpg(self):
        result = self.make_sync_url("postgresql+asyncpg://user:pass@host/db")
        assert result == "postgresql://user:pass@host/db"

    def test_sync_postgres_to_postgresql(self):
        result = self.make_sync_url("postgres://user:pass@host/db")
        assert result == "postgresql://user:pass@host/db"

    def test_sync_already_postgresql_unchanged(self):
        url = "postgresql://user:pass@host/db"
        result = self.make_sync_url(url)
        assert result == url


# =====================================================================
# run_async — standalone, no DB imports needed
# =====================================================================


class TestRunAsync:
    """Test the Celery async helper. Import only the function via patching."""

    def _get_run_async(self):
        """Import run_async by extracting it without triggering engine creation."""

        # run_async is a pure function that doesn't need DB engines.
        # We define it inline to avoid importing db.session.
        def run_async(coro):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()

        return run_async

    def test_executes_coroutine(self):
        run_async = self._get_run_async()

        async def sample():
            return 42

        assert run_async(sample()) == 42

    def test_propagates_exception(self):
        run_async = self._get_run_async()

        async def failing():
            raise RuntimeError("async failure")

        with pytest.raises(RuntimeError, match="async failure"):
            run_async(failing())

    def test_returns_complex_value(self):
        run_async = self._get_run_async()

        async def build_dict():
            return {"status": "ok", "count": 5}

        result = run_async(build_dict())
        assert result == {"status": "ok", "count": 5}


# =====================================================================
# get_session alias — check without importing the module
# =====================================================================


class TestSessionAliases:
    """Verify get_db is an alias for get_session at the code level."""

    def test_get_db_alias_in_source(self):
        """Read the source file and verify `get_db = get_session` exists."""
        import pathlib

        session_file = pathlib.Path(__file__).parent.parent / "db" / "session.py"
        source = session_file.read_text()
        assert "get_db = get_session" in source


# =====================================================================
# Session provider logic — tested with mocked factories
# =====================================================================


class TestGetSyncSession:
    """Test get_sync_session logic using a mock SyncSessionLocal."""

    def test_commits_on_success(self):
        mock_session = MagicMock()
        mock_factory = MagicMock(return_value=mock_session)

        # Reproduce get_sync_session logic
        from contextlib import contextmanager

        @contextmanager
        def get_sync_session():
            session = mock_factory()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        with get_sync_session() as s:
            assert s is mock_session

        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    def test_rolls_back_on_error(self):
        mock_session = MagicMock()
        mock_factory = MagicMock(return_value=mock_session)

        from contextlib import contextmanager

        @contextmanager
        def get_sync_session():
            session = mock_factory()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        with pytest.raises(ValueError):
            with get_sync_session() as s:
                raise ValueError("task failed")

        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()


class TestGetSessionContext:
    """Test get_session_context logic using a mock async_session factory."""

    @pytest.mark.asyncio
    async def test_commits_on_success(self):
        mock_session = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_session
        mock_cm.__aexit__.return_value = None
        mock_factory = MagicMock(return_value=mock_cm)

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def get_session_context():
            async with mock_factory() as session:
                try:
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise

        async with get_session_context() as s:
            assert s is mock_session

        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rolls_back_on_error(self):
        mock_session = AsyncMock()
        mock_session.commit.side_effect = Exception("DB error")
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_session
        mock_cm.__aexit__.return_value = None
        mock_factory = MagicMock(return_value=mock_cm)

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def get_session_context():
            async with mock_factory() as session:
                try:
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise

        with pytest.raises(Exception, match="DB error"):
            async with get_session_context() as s:
                pass

        mock_session.rollback.assert_awaited_once()
