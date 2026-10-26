import sys
from pathlib import Path

# Add backend directory to path so tests can import backend modules directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
