import re
from typing import Any, Dict
from config import settings

# Mandatory disclaimer to append if missing or customized incorrectly
MANDATORY_DISCLAIMER = (
    "This is an AI-generated informational assessment for decision-support purposes only. "
    "It does not constitute a final credit approval. All decisions must be verified by "
    "an authorized banking officer in accordance with institutional policy."
)

# Block phrases offering false guarantees
GUARANTEE_PATTERNS = [
    r"definitely.*approved",
    r"guarantee.*approval",
    r"guaranteed.*loan",
    r"will.*definitely.*get",
    r"absolutely.*approved"
]

def sanitize_and_check_output(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitizes orchestrator output to enforce BFSI compliance.
    Ensures:
    1. Mandatory keys are present: decision, reasoning, disclaimer.
    2. Over-optimistic guarantees are softened.
    3. Proper disclaimer is appended.
    """
    if not settings.ENABLE_GUARDRAILS:
        return result

    # 1. Enforce existence of keys
    if "decision" not in result:
        result["decision"] = "Not Eligible"
    if "reasoning" not in result:
        result["reasoning"] = "System generated report unavailable."
    if "disclaimer" not in result or not result["disclaimer"]:
        result["disclaimer"] = MANDATORY_DISCLAIMER

    # 2. Check and soften reasoning/text for guarantees
    reasoning = result.get("reasoning", "")
    for pattern in GUARANTEE_PATTERNS:
        if re.search(pattern, reasoning, re.IGNORECASE):
            # Replace guarantee phrasing with compliant BFS terminology
            reasoning = re.sub(
                pattern, 
                "subject to credit verification and formal approval", 
                reasoning, 
                flags=re.IGNORECASE
            )
            result["reasoning"] = reasoning
            result["guardrail_status"] = "Sanitized"

    # Always overwrite or append standard disclaimer to be 100% compliant
    if MANDATORY_DISCLAIMER not in result["disclaimer"]:
        result["disclaimer"] = MANDATORY_DISCLAIMER

    return result
