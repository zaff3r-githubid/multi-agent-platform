# conftest.py
"""
Pytest configuration file.
Adding the project root to sys.path allows all test files
to import from agents/, utils/, orchestrator/, etc.
without needing to install the project as a package.
"""
import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))
