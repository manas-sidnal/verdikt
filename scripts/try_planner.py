"""Dev script: create a verification plan for a sample claim and inspect results."""
import sys
from pathlib import Path

# Allow running from the project root or scripts/ directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from pprint import pprint
from planner import create_verification_plan

claim = "I fixed the login bug and deployed the fix."

try:
    plan = create_verification_plan(claim)
    pprint(plan)
except Exception as error:
    print(f"Planner failed: {error}")