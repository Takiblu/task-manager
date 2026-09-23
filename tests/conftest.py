"""Shared pytest fixtures / path setup."""

import sys
from pathlib import Path

# Ensure the project root is on sys.path so `import src....` works
# regardless of how pytest is invoked (from repo root or elsewhere).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
