import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from backend.verification_plan import validate_plan, validate_bug_fix_plan

load_dotenv()

client = OpenAI(
    base_url="https://api.tokenfactory.nebius.com/v1/",
    api_key=os.getenv("NEBIUS_API_KEY"),
)

MODEL = os.getenv("NEBIUS_MODEL")

def create_verification_plan(claim):
    if not isinstance(claim, str) or not claim.strip():
        raise ValueError("Claim must not be empty")

    if not MODEL:
        raise ValueError("NEBIUS_MODEL is missing from your .env file")

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": """

You create verification plans for claims made by AI agents.

Your job is to identify what independent evidence would
actually establish whether the claim is true.

Return ONLY a valid JSON object in this format:
{
  "claim": "the original claim",
  "checks": [
    {
      "id": "deployment_status",
      "description": "what evidence to collect"
    }
  ]
}

Allowed check IDs:
- deployment_status
- bug_reproduction
- expected_behavior

Rules:

1. Preserve the meaning of the original claim.

2. For claims about fixing a bug, distinguish between:
   - Evidence that the bug existed before the fix.
   - A current test that checks whether the bug still occurs.
   - Evidence that the intended behavior now works.

3. For claims about deployment, check deployment status
   independently of whether the application behaves correctly.

4. Prefer checks that can produce observable evidence,
   such as test results, deployment records, or logs.

5. Do not treat an agent's own statement that a task
   succeeded as independent proof.

6. Never claim a check has passed. Describe what needs
   to be checked, not its result.

7. Include all relevant checks, using only the allowed IDs.

8. Return valid JSON only. Do not include Markdown fences
   or explanatory text outside the JSON object.

""",
            },
            {
                "role": "user",
                "content": f"Create a verification plan for this claim:\n{claim}",
            },
        ],
        temperature=0,
    )

    content = response.choices[0].message.content
    if not content:
        raise ValueError("Nemotron returned an empty response")
    try:
        plan = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        raise ValueError("Nemotron did not return valid JSON")

    validate_bug_fix_plan(plan)

    return plan
