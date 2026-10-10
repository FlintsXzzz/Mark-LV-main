"""Put the project root on sys.path so tests can import core/ and memory/.

Strictly speaking `tests/__init__.py` already gets pytest to do this: with a
package-style tests directory, pytest walks up to the first parent without an
__init__.py and inserts that. This file is belt-and-braces so the suite still
imports correctly if tests/__init__.py is ever removed, a test file is moved
to the repo root, or the suite is run from an unrelated working directory —
all of which otherwise fail with a bare `ModuleNotFoundError: No module named
'core'`.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))