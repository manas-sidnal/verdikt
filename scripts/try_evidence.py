"""Dev script: run the evidence collector and inspect results."""
import sys
from pathlib import Path

# Allow running from the project root or scripts/ directory
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pprint import pprint
from backend.evidence_collector import run_login_test

evidence = run_login_test()
pprint(evidence)
