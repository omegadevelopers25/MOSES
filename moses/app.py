"""MOSES Personal Assistant - Mobile App Entry Point for BeeWare"""
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from moses_gui import main

if __name__ == "__main__":
    main()
