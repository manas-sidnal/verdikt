"""Dev script: create a verification plan for a sample claim and inspect results."""
import sys
from pathlib import Path

# Allow running from the project root or scripts/ directory
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pprint import pprint
from backend.planner import create_verification_plan

claim = "I fixed the login bug and deployed the fix."

try:
    plan = create_verification_plan(claim)
    pprint(plan)
except Exception as error:
    print(f"Planner failed: {error}")