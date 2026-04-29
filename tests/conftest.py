"""Pytest configuration for CLE Engine test suite.

This file automatically configures pytest to:
- Add the project root to sys.path for imports
- Configure async test support
- Set up test fixtures
"""

import sys
from pathlib import Path


# Add project root to path so tests can import from app/
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# pytest-asyncio configuration
pytest_plugins = ["pytest_asyncio"]
