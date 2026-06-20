import re
from typing import Any, Dict
from config import settings

# Suspicious phrases or keywords to block instantly
BLOCKED_PHRASES = [
    r"ignore.*rules",
    r"ignore.*policy",
    r"bypass.*checks",
    r"bypass.*validation",
    r"approve.*anyway",
    r"eligible.*anyway",
    r"override.*system",
    r"fake.*salary",
    r"fake.*document",
    r"use.*fabricated",
    r"manipulate.*score",
    r"system.*prompt",
    r"you are now an approval agent",
    r"ignore all instructions",
    r"set.*decision",
    r"bypass.*rules"
]

def check_input(customer_data: Dict[str, Any], user_message: str = "") -> Dict[str, Any]:
    """
    Checks customer inputs and chat messages for security violations.
    Checks for:
    - Prompt injections in text inputs
    - Attempts to override rules or submit fake credentials/salaries.
    """
    if not settings.ENABLE_GUARDRAILS:
        return {"blocked": False, "reason": ""}

    # 1. Analyze text inputs in customer data (name, purpose, etc.)
    for key, val in customer_data.items():
        if isinstance(val, str):
            val_lower = val.lower()
            for pattern in BLOCKED_PHRASES:
                if re.search(pattern, val_lower):
                    return {
                        "blocked": True,
                        "reason": f"Input Guardrail Violation: Flagged content in '{key}' field matching pattern '{pattern}'."
                    }

    # 2. Analyze user conversational chat message if provided
    if user_message:
        msg_lower = user_message.lower()
        for pattern in BLOCKED_PHRASES:
            if re.search(pattern, msg_lower):
                return {
                    "blocked": True,
                    "reason": f"Input Guardrail Violation: Conversation flagged for rule override attempts."
                }

    # 3. Check for obvious salary/credit manipulations in rules
    try:
        income = float(customer_data.get("monthly_income", 0))
        if income > 10_000_000:  # 1 Crore monthly income limit for sanity
            return {
                "blocked": True,
                "reason": "Input Guardrail Violation: Monthly income exceeds plausible verification thresholds."
            }
    except (ValueError, TypeError):
        pass

    return {"blocked": False, "reason": ""}
