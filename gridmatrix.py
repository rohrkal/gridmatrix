#!/usr/bin/env python3
"""Repository entrypoint; canonical implementation ships inside the skill."""
import runpy
from pathlib import Path

if __name__ == '__main__':
    runpy.run_path(str(Path(__file__).resolve().parent / 'skills/gridmatrix/scripts/gridmatrix.py'), run_name='__main__')
