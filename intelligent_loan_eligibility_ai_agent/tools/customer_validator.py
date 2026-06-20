from typing import Any, Dict, List

def validate_customer_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates mandatory customer fields for loan assessment.
    Checks:
    - name
    - age
    - monthly_income
    - employment_type
    - loan_amount_requested
    - credit_score

    Returns:
        Dict: {"valid": bool, "missing_fields": List[str], "errors": List[str]}
    """
    missing_fields = []
    errors = []

    required_keys = [
        ("name", "Full Name"),
        ("age", "Age"),
        ("monthly_income", "Monthly Income"),
        ("employment_type", "Employment Type"),
        ("loan_amount_requested", "Loan Amount Requested"),
        ("credit_score", "Credit Score")
    ]

    for key, label in required_keys:
        val = data.get(key)
        if val is None or str(val).strip() == "" or val == 0:
            # Special check: age or income or credit score or loan requested shouldn't be zero/empty
            if key != "name" and key != "employment_type" and val == 0:
                # 0 is missing or invalid for age/income/requested/credit
                missing_fields.append(label)
            elif val is None or str(val).strip() == "":
                missing_fields.append(label)

    # If existing loan is Yes, make sure monthly loan payment is checked
    if data.get("existing_loan") == "Yes":
        emi = data.get("monthly_loan_payment")
        if emi is None or str(emi).strip() == "":
            missing_fields.append("Monthly Loan Payment (EMI)")

    # Data type & range validations if fields are present
    if "Age" not in missing_fields:
        try:
            age = int(data.get("age", 0))
            if age < 18 or age > 100:
                errors.append("Age must be between 18 and 100.")
        except (ValueError, TypeError):
            errors.append("Age must be a valid number.")

    if "Monthly Income" not in missing_fields:
        try:
            income = float(data.get("monthly_income", 0))
            if income < 0:
                errors.append("Monthly income cannot be negative.")
        except (ValueError, TypeError):
            errors.append("Monthly income must be a valid number.")

    if "Credit Score" not in missing_fields:
        try:
            score = int(data.get("credit_score", 0))
            if score < 300 or score > 900:
                errors.append("Credit score must be between 300 and 900.")
        except (ValueError, TypeError):
            errors.append("Credit score must be a valid number.")

    if "Loan Amount Requested" not in missing_fields:
        try:
            amt = float(data.get("loan_amount_requested", 0))
            if amt <= 0:
                errors.append("Loan amount requested must be positive.")
        except (ValueError, TypeError):
            errors.append("Loan amount requested must be a valid number.")

    valid = len(missing_fields) == 0 and len(errors) == 0

    return {
        "valid": valid,
        "missing_fields": missing_fields,
        "errors": errors
    }
