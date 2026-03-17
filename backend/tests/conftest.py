"""
Global test configuration — shared fixtures for sys.modules isolation.

Only core.logging and core.config are handled here (autouse).
Other modules (db.session, google.genai, etc.) stay in individual
test files until their batch migration.
"""

import sys
from unittest.mock import MagicMock

import pytest

# ─────────────────────────────────────────────────────────────────
# AUTOUSE FIXTURES — core.logging + core.config only
# ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _mock_core_logging(monkeypatch):
    """Fresh core.logging mock for each test."""
    mock_log = MagicMock()
    mock_log.get_logger = MagicMock(return_value=MagicMock())
    monkeypatch.setitem(sys.modules, "core.logging", mock_log)
    return mock_log


@pytest.fixture(autouse=True)
def _mock_core_config(monkeypatch):
    """Fresh core.config mock for each test."""
    mock_config = MagicMock()
    mock_config.settings = MagicMock()
    monkeypatch.setitem(sys.modules, "core.config", mock_config)
    return mock_config


# ─────────────────────────────────────────────────────────────────
# OPT-IN FIXTURES
# ─────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_core_logging(_mock_core_logging):
    """Public accessor for tests that need to configure the logging mock."""
    return _mock_core_logging


@pytest.fixture
def mock_core_config(_mock_core_config):
    """Public accessor for tests that need to configure settings."""
    return _mock_core_config
