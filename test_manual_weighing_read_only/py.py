#!/usr/bin/env python3
"""
Compatibility runner for command:
  python -m test_manual_weighing_read_only.py

This delegates execution to the top-level script file.
"""

from __future__ import annotations

import runpy
from pathlib import Path


if __name__ == "__main__":
    script_path = Path(__file__).resolve().parent.parent / "test_manual_weighing_read_only.py"
    runpy.run_path(str(script_path), run_name="__main__")
