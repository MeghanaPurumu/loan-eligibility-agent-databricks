from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from core.utils import parse_number, normalize_employment

@dataclass
class EvaluationResult:
    eligibility: str
    score: int
    key_factors: Dict[str, Any]
    reasons: list[str]
    next_steps: list[str]
    scoring_breakdown: Dict[str, int]
    estimated_terms: Dict[str, Any]
    required_income_for_eligibility: float = 0.0


class LoanRuleEngine:
    def __init__(self, rules_path: str | Path):
        self.rules_path = Path(rules_path)
        self.rules = json.loads(self.rules_path.read_text(encoding="utf-8"))

    def estimate_loan_terms(self, score: int, requested_amount: float) -> Dict[str, Any]:
        """Estimates interest rate and tenure based on the engine score."""
        if score >= 90:
            rate = "8.25% - 8.75%"
            tenure = "Up to 30 years"
            risk = "Very Low"
        elif score >= 75:
            rate = "8.75% - 9.50%"
            tenure = "Up to 25 years"
            risk = "Low"
        elif score >= 50:
            rate = "9.50% - 11.00%"
            tenure = "Up to 20 years"
            risk = "Moderate"
        elif score >= 30:
            rate = "11.00% - 14.50%"
            tenure = "Up to 15 years"
            risk = "High"
        else:
            rate = "N/A"
            tenure = "N/A"
            risk = "Very High"

        return {
            "estimated_interest_rate": rate,
            "maximum_tenure": tenure,
            "risk_category": risk,
            "processing_fee": "0.5% - 1.0%" if score >= 80 else "1.0% - 2.0%"
        }

    def validate_inputs(self, customer: Dict[str, Any]) -> list[str]:
        """Performs sanity checks on inputs to ensure they follow banking domain logic."""
        errors = []
        
        age = parse_number(customer.get("age"))
        if age is not None and (age < 18 or age > 100):
            errors.append("Age must be between 18 and 100.")
            
        income = parse_number(customer.get("monthly_income"))
        if income is not None and income < 0:
            errors.append("Monthly income cannot be negative.")
            
        credit = parse_number(customer.get("credit_score"))
        if credit is not None and (credit < 300 or credit > 900):
            errors.append("Credit score must be between 300 and 900.")
            
        requested = parse_number(customer.get("loan_amount_requested"))
        if requested is not None and requested <= 0:
            errors.append("Loan amount requested must be a positive value.")

        return errors

    def _compute_eligibility_for_income(self, customer: Dict[str, Any], test_income: float) -> str:
        """
        Lightweight eligibility check used ONLY by _calculate_needed_income.
        Uses a cloned customer dict with a substituted income.
        Does NOT call _calculate_needed_income — prevents infinite recursion.
        """
        t = self.rules["thresholds"]

        credit = parse_number(customer.get("credit_score"))
        liabilities = parse_number(
            customer.get("existing_liabilities") or customer.get("monthly_loan_payment"), 0
        ) or 0
        requested = parse_number(customer.get("loan_amount_requested"))
        employment = normalize_employment(customer.get("employment_type") or "")
        age = parse_number(customer.get("age"))

        # Hard stops that income cannot fix
        if age is None or credit is None or requested is None:
            return "Not Eligible"
        if age < t["min_age"] or age > t["max_age"]:
            return "Not Eligible"
        if credit < t["minimum_credit_score"]:
            return "Not Eligible"

        income = test_income

        # Scores mirror the main engine exactly
        breakdown = {
            "Income": 0,
            "Credit Score": 0,
            "Liabilities": 0,
            "Employment": 0,
            "Loan Request": 0,
        }

        # Income
        if income >= t["eligible_min_income_monthly"]:
            breakdown["Income"] = 2
        elif income >= t["conditional_min_income_monthly"]:
            breakdown["Income"] = 1
        else:
            return "Not Eligible"

        # Credit
        if credit >= t["excellent_credit_score"]:
            breakdown["Credit Score"] = 2
        elif credit >= t["minimum_credit_score"]:
            breakdown["Credit Score"] = 1

        # Liabilities — ratio recalculated with new income
        liability_ratio = liabilities / income if income else 1
        if liability_ratio <= t["conditional_liability_ratio"]:
            breakdown["Liabilities"] = 2
        elif liability_ratio <= t["high_liability_ratio"]:
            breakdown["Liabilities"] = 1
        else:
            return "Not Eligible"

        # Employment
        if employment == "Salaried":
            breakdown["Employment"] = 2
        elif employment in {"Self-employed", "Business"}:
            breakdown["Employment"] = 1
        elif employment in {"Student", "Unemployed"}:
            breakdown["Employment"] = -1

        # Loan request
        income_multiplier = requested / income if income else 999
        if income_multiplier <= t["max_loan_to_income_ratio"]:
            breakdown["Loan Request"] = 1

        total = sum(breakdown.values())
        if total >= 7:
            return "Eligible"
        elif total >= 4:
            return "Conditionally Eligible"
        return "Not Eligible"

    def _calculate_needed_income(self, customer: Dict[str, Any]) -> float:
        """
        Binary search (up to Rs. 10,00,000 cap) to find the minimum monthly income
        that would make the applicant Eligible.
        Uses _compute_eligibility_for_income to avoid recursion.
        Returns 0.0 if income alone cannot make them eligible.
        """
        income_cap = 1_000_000  # Rs. 10 lakh/month cap

        # Quick check: even at cap, are they eligible?
        if self._compute_eligibility_for_income(customer, income_cap) != "Eligible":
            return 0.0  # Cannot become eligible by income alone (e.g. bad credit)

        low = int(parse_number(customer.get("monthly_income"), 0) or 0)
        high = income_cap
        ans = float(income_cap)

        while low <= high:
            mid = (low + high) // 2
            if self._compute_eligibility_for_income(customer, mid) == "Eligible":
                ans = float(mid)
                high = mid - 1
            else:
                low = mid + 1

        return ans

    def evaluate(self, customer: Dict[str, Any]) -> EvaluationResult:
        t = self.rules["thresholds"]
        reasons = []
        next_steps = []
        
        # Step 0: Logical Validation
        validation_errors = self.validate_inputs(customer)
        if validation_errors:
            return EvaluationResult(
                eligibility="Not Eligible",
                score=0,
                key_factors=self._key_factors(customer),
                reasons=validation_errors,
                next_steps=["Please provide valid banking information."],
                scoring_breakdown={},
                estimated_terms={"risk_category": "Invalid Input"},
                required_income_for_eligibility=0.0
            )

        # Track individual points
        breakdown = {
            "Income": 0,
            "Credit Score": 0,
            "Liabilities": 0,
            "Employment": 0,
            "Loan Request": 0
        }

        age = parse_number(customer.get("age"))
        income = parse_number(customer.get("monthly_income"))
        credit = parse_number(customer.get("credit_score"))
        liabilities = parse_number(customer.get("existing_liabilities") or customer.get("monthly_loan_payment"), 0) or 0
        requested = parse_number(customer.get("loan_amount_requested"))
        employment = normalize_employment(customer.get("employment_type") or "")

        if age is None or income is None or credit is None or requested is None:
            return EvaluationResult(
                eligibility="Not Eligible",
                score=0,
                key_factors=self._key_factors(customer),
                reasons=["Required data is missing or invalid format."],
                next_steps=["Provide all required details."],
                scoring_breakdown=breakdown,
                estimated_terms={"risk_category": "Very High"},
                required_income_for_eligibility=0.0
            )

        # Age
        if age < t["min_age"] or age > t["max_age"]:
            reasons.append(self.rules["reasons_map"]["age_out_of_range"])
            return EvaluationResult(
                eligibility="Not Eligible",
                score=0,
                key_factors=self._key_factors(customer),
                reasons=reasons,
                next_steps=["Check age eligibility."],
                scoring_breakdown=breakdown,
                estimated_terms={"risk_category": "Very High"},
                required_income_for_eligibility=0.0  # Age cannot be fixed by income
            )

        # Income
        if income >= t["eligible_min_income_monthly"]:
            breakdown["Income"] = 2
        elif income >= t["conditional_min_income_monthly"]:
            breakdown["Income"] = 1
            reasons.append(self.rules["reasons_map"]["low_income"])
        else:
            reasons.append(self.rules["reasons_map"]["low_income"])
            needed = self._calculate_needed_income(customer)
            return EvaluationResult(
                eligibility="Not Eligible",
                score=0,
                key_factors=self._key_factors(customer),
                reasons=reasons,
                next_steps=["Income below baseline."],
                scoring_breakdown=breakdown,
                estimated_terms={"risk_category": "Very High"},
                required_income_for_eligibility=needed
            )

        # Credit score
        if credit >= t["excellent_credit_score"]:
            breakdown["Credit Score"] = 2
        elif credit >= t["minimum_credit_score"]:
            breakdown["Credit Score"] = 1
        else:
            reasons.append(self.rules["reasons_map"]["low_credit"])
            return EvaluationResult(
                eligibility="Not Eligible",
                score=0,
                key_factors=self._key_factors(customer),
                reasons=reasons,
                next_steps=["Improve credit score."],
                scoring_breakdown=breakdown,
                estimated_terms={"risk_category": "Very High"},
                required_income_for_eligibility=0.0  # Credit cannot be fixed by income
            )

        # Liabilities
        liability_ratio = liabilities / income if income else 1
        if liability_ratio <= t["conditional_liability_ratio"]:
            breakdown["Liabilities"] = 2
        elif liability_ratio <= t["high_liability_ratio"]:
            breakdown["Liabilities"] = 1
            reasons.append(self.rules["reasons_map"]["high_liabilities"])
        else:
            reasons.append(self.rules["reasons_map"]["high_liabilities"])
            needed = self._calculate_needed_income(customer)
            return EvaluationResult(
                eligibility="Not Eligible",
                score=0,
                key_factors=self._key_factors(customer),
                reasons=reasons,
                next_steps=["Reduce debt ratio."],
                scoring_breakdown=breakdown,
                estimated_terms={"risk_category": "Very High"},
                required_income_for_eligibility=needed
            )

        # Employment
        if employment == "Salaried":
            breakdown["Employment"] = 2
        elif employment in {"Self-employed", "Business"}:
            breakdown["Employment"] = 1
        elif employment in {"Student", "Unemployed"}:
            breakdown["Employment"] = -1
        else:
            breakdown["Employment"] = 0

        # Requested loan amount
        income_multiplier = requested / income if income else 999
        if income_multiplier <= t["max_loan_to_income_ratio"]:
            breakdown["Loan Request"] = 1
        else:
            reasons.append(self.rules["reasons_map"]["requested_amount_high"])

        # Total points
        total_points = sum(breakdown.values())
        normalized_score = min(100, max(0, int((total_points / 9) * 100)))

        if total_points >= 7:
            eligibility = "Eligible"
        elif total_points >= 4:
            eligibility = "Conditionally Eligible"
        else:
            eligibility = "Not Eligible"

        # Estimate Terms
        terms = self.estimate_loan_terms(normalized_score, requested)

        if eligibility == "Eligible":
            reasons.append(self.rules["reasons_map"]["positive_profile"])
            next_steps = ["Submit standard KYC."]
        elif eligibility == "Conditionally Eligible" and not next_steps:
            next_steps = ["Provide additional documents."]

        # Calculate needed income only for non-eligible results (no recursion risk)
        needed_income = 0.0
        if eligibility != "Eligible":
            needed_income = self._calculate_needed_income(customer)

        return EvaluationResult(
            eligibility=eligibility,
            score=normalized_score,
            key_factors=self._key_factors(customer),
            reasons=reasons,
            next_steps=next_steps,
            scoring_breakdown=breakdown,
            estimated_terms=terms,
            required_income_for_eligibility=needed_income
        )

    def _key_factors(self, customer: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "name": customer.get("name", ""),
            "age": parse_number(customer.get("age")),
            "monthly_income": parse_number(customer.get("monthly_income")),
            "employment_type": normalize_employment(customer.get("employment_type") or ""),
            "credit_score": parse_number(customer.get("credit_score")),
            "existing_liabilities": parse_number(customer.get("existing_liabilities") or customer.get("monthly_loan_payment"), 0) or 0,
            "loan_amount_requested": parse_number(customer.get("loan_amount_requested")),
            "loan_purpose": customer.get("loan_purpose", "Not Specified")
        }
