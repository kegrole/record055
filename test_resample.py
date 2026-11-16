"""Root shim so python -m unittest test_resample -v works from the repo
root; the real test suite lives in tests/test_resample.py."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tests.test_resample import *  # noqa: F401,F403
