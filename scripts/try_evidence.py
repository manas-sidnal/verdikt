"""Dev script: run the evidence collector and inspect results."""
import sys
from pathlib import Path

# Allow running from the project root or scripts/ directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from pprint import pprint
from evidence_collector import run_login_test

evidence = run_login_test()
pprint(evidence)
