from typing import Any, Dict

def calculate_confidence(eligibility_result: Dict[str, Any], validator_result: Dict[str, Any]) -> str:
    """
    Deterministically computes assessment confidence level.
    Rules:
      - LOW: Customer validation failed, errors exist, or not eligible.
      - MODERATE: Customer conditionally eligible.
      - HIGH: Customer fully eligible with zero validation errors.
    """
    if not validator_result.get("valid", False) or len(validator_result.get("errors", [])) > 0:
        return "LOW"
    
    verdict = eligibility_result.get("eligibility", "Not Eligible")
    if verdict == "Eligible":
        return "HIGH"
    elif verdict == "Conditionally Eligible":
        return "MODERATE"
    else:
        return "LOW"
