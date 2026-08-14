"""Shared pytest fixtures for the knowledge-ops-agent test suite.

All tests in this suite run fully offline: no real LLM endpoints are called.
The fixtures below keep path handling consistent when tests run from the
repository root (pytest default working directory).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure repository root is importable when pytest is invoked from anywhere.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture()
def repo_root() -> Path:
    """Return the repository root path for tests that read local data files."""
    return REPO_ROOT
