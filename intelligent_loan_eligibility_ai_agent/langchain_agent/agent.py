"""
langchain_agent/agent.py

TRUE LangChain Agent with:
  - Conversational data collection via agent system prompt (no Python-level field gates)
  - ZERO_SHOT_REACT_DESCRIPTION agent (LLM autonomously calls the tool when ready)
  - ConversationBufferMemory for multi-turn context (persists within Streamlit session)
  - Output detection: question vs. full 5-section report
  - 2-tier fallback: LCEL chain → deterministic report
"""
from __future__ import annotations
import json
from typing import Any, Dict

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_classic.agents import initialize_agent, AgentType
from langchain_classic.memory import ConversationBufferMemory

from core.rule_engine import LoanRuleEngine, EvaluationResult

# ── Required fields the agent must verify before calling the tool ──────────────
REQUIRED_FIELDS = [
    "name", "age", "monthly_income", "employment_type",
    "credit_score", "loan_amount_requested", "loan_purpose",
]

# ── System / Agent Prefix Prompt ───────────────────────────────────────────────
AGENT_PREFIX = """
You are a senior banking underwriter AI agent for an Intelligent Loan Eligibility System.

════════════════════════════════════════════════
  AGENT DECISION FLOW — FOLLOW STRICTLY
════════════════════════════════════════════════
Step 1 — ANALYZE the input and check if ALL required fields are present.
Step 2 — IDENTIFY missing fields from this list:
         [name, age, monthly_income, employment_type, credit_score,
          loan_amount_requested, loan_purpose]
         Also check monthly_loan_payment if existing_loan is "Yes".
Step 3 — IF any field is missing:
         → DO NOT call the evaluate_loan_eligibility tool.
         → ASK the user for the missing field(s) conversationally and professionally.
         → Example: "To complete your assessment, could you please share your monthly income?"
         → Wait for the user to provide the information before proceeding.
Step 4 — IF all required fields are present:
         → You MUST call the evaluate_loan_eligibility tool immediately.
         → Pass ALL customer fields as a JSON string.
         → Do NOT skip this step under any circumstances.
Step 5 — INTERPRET the exact tool result — use the numbers and verdict as-is.
Step 6 — GENERATE the complete 5-section underwriting report using this structure:

### 1. Eligibility Result
   - State the verdict and Rule Engine Score (e.g., Score: 78/100).
   - State the Risk Category and what it implies for the bank.

### 2. Key Evaluation Factors
   - For each factor, state Pass/Review Required and the actual value:
     * Monthly Income (INR) — vs. Rs.30,000 minimum / Rs.50,000 preferred
     * Credit Score — vs. minimum (600) and excellent (750)
     * Employment Type — impact on risk scoring
     * Existing Liabilities — DTI ratio vs. 40% cap
     * Loan Amount Requested — vs. income multiples

### 3. Reasoning Summary
   - 3-5 bullet points explaining WHY this decision was reached.
   - If Not Eligible and required_income_for_eligibility > 0:
     Include EXACTLY: "If your income increases to Rs. X, you become eligible"

### 4. Suggested Next Steps
   - 2-3 actionable steps for the Loan Officer.

### 5. Disclaimer
   - Include verbatim: "This is an AI-generated informational assessment for
     decision-support purposes only. It does not constitute a final credit approval.
     All decisions must be verified by an authorized banking officer in accordance
     with institutional policy."

════════════════════════════════════════════════
  ABSOLUTE RULES — NO EXCEPTIONS
════════════════════════════════════════════════
✗ YOU MUST NOT generate any eligibility verdict without first calling the tool.
✗ YOU MUST NOT skip the tool call when all required fields are available.
✗ YOU MUST NOT fabricate scores, verdicts, or income figures.
✗ YOU MUST NOT call the tool when any required field is missing.
✓ YOU MUST call evaluate_loan_eligibility when all required data is present.
✓ YOU MUST ask conversational follow-up questions when data is incomplete.
✓ YOU MUST base your entire report ONLY on the tool's returned JSON.
✓ YOUR ONLY SOURCE OF TRUTH for eligibility is the tool output.
"""

AGENT_SUFFIX = """
REMEMBER:
- If fields are missing → ask for them. Do NOT call the tool.
- If all fields are present → call the tool, then write the report.

Conversation History:
{chat_history}

Current Input: {input}
Agent Scratchpad: {agent_scratchpad}
"""

# ── Fallback LLM Prompt (LCEL chain) ──────────────────────────────────────────
LCEL_SYSTEM_PROMPT = (
    "You are a senior banking underwriter generating an internal loan eligibility report.\n"
    "The tool result is provided below. Use ONLY it — do NOT invent eligibility data.\n"
    "If the applicant is NOT Eligible and required_income_for_eligibility > 0, "
    "include EXACTLY: 'If your income increases to Rs. X, you become eligible'.\n\n"
    "### REQUIRED STRUCTURE:\n"
    "### 1. Eligibility Result\n"
    "### 2. Key Evaluation Factors\n"
    "### 3. Reasoning Summary\n"
    "### 4. Suggested Next Steps\n"
    "### 5. Disclaimer\n"
    "Include actual numbers. Use bullet points. Max 450 words."
)

# ── Report detection ───────────────────────────────────────────────────────────
REPORT_MARKER = "### 1. Eligibility Result"


class LoanEligibilityAgent:
    """
    LangChain-orchestrated Loan Eligibility Agent.

    Architecture:
      PRIMARY   — ZERO_SHOT_REACT_DESCRIPTION agent with ConversationBufferMemory.
                  The LLM autonomously decides to ask for missing fields OR call the tool.
      FALLBACK1 — LCEL chain with pre-injected tool result.
      FALLBACK2 — Fully deterministic 5-section report.

    Output detection:
      If agent response contains "### 1. Eligibility Result" → full report (needs_more_info=False)
      Otherwise → conversational follow-up question (needs_more_info=True)
    """

    # Class-level shared memory — persists across Streamlit reruns within the same session
    _shared_memory: ConversationBufferMemory | None = None

    def __init__(self, rules_path: str, model: str = "llama3:latest"):
        self.rules_path = rules_path
        self.engine = LoanRuleEngine(rules_path)
        self.llm = ChatOllama(model=model, temperature=0)

        # ── ConversationBufferMemory ────────────────────────────────────────
        # Class-level singleton ensures memory persists across Streamlit reruns
        # within the same Python process (session).
        if LoanEligibilityAgent._shared_memory is None:
            LoanEligibilityAgent._shared_memory = ConversationBufferMemory(
                memory_key="chat_history",
                input_key="input",
                return_messages=True,
            )
        self.memory = LoanEligibilityAgent._shared_memory

        # ── LangChain Tool (rule engine wrapped) ────────────────────────────
        # The LLM calls this tool ONLY when all required data is available.
        engine_ref = self.engine

        @tool
        def evaluate_loan_eligibility(customer_data: str) -> str:
            """
            Evaluates a loan application using the bank's formal deterministic rule engine.

            The agent MUST call this tool when all required fields are available.
            Required fields: name, age, monthly_income, employment_type, credit_score,
            loan_amount_requested, loan_purpose. Also monthly_loan_payment if existing_loan="Yes".

            Input:  JSON string with all customer fields.
            Output: JSON string containing eligibility verdict, score, key_factors,
                    scoring_breakdown, reasons, next_steps, estimated_terms,
                    and required_income_for_eligibility.
            """
            try:
                data = json.loads(customer_data)
            except (json.JSONDecodeError, TypeError):
                return json.dumps({"error": "Invalid JSON. Please pass customer data as a JSON string."})

            result: EvaluationResult = engine_ref.evaluate(data)
            return json.dumps({
                "eligibility": result.eligibility,
                "score": result.score,
                "key_factors": result.key_factors,
                "scoring_breakdown": result.scoring_breakdown,
                "reasons": result.reasons,
                "next_steps": result.next_steps,
                "estimated_terms": result.estimated_terms,
                "required_income_for_eligibility": result.required_income_for_eligibility,
            }, indent=2)

        self._tool_fn = evaluate_loan_eligibility
        self._tools = [evaluate_loan_eligibility]

        # ── TRUE LangChain ReAct Agent ──────────────────────────────────────
        # LLM autonomously:
        #   - Detects missing fields → asks user (no tool call)
        #   - Detects complete input → calls evaluate_loan_eligibility tool
        #   - Interprets tool result → writes structured report
        self._react_agent = initialize_agent(
            tools=self._tools,
            llm=self.llm,
            agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            memory=self.memory,
            verbose=True,
            handle_parsing_errors=True,
            return_intermediate_steps=True,
            max_iterations=4,
            agent_kwargs={
                "prefix": AGENT_PREFIX,
                "suffix": AGENT_SUFFIX,
                "input_variables": ["input", "agent_scratchpad", "chat_history"],
            },
        )

    # ── Input edge-case validation ──────────────────────────────────────────────
    def _validate_payload(self, payload: Dict[str, Any]) -> list[str]:
        """
        Pre-flight validation of all input fields.
        Returns a list of human-readable error messages.
        An empty list means all inputs are valid.

        Checks:
          - name: non-empty, not numbers-only, at least 2 chars
          - age: >= 18 (bank minimum), not 0
          - monthly_income: not negative; warns if 0
          - credit_score: within 300–900 range
          - loan_amount_requested: > 0 with a reasonable upper cap
          - loan_purpose: non-empty, at least 3 meaningful chars
          - monthly_loan_payment: not negative; < monthly_income if existing_loan=Yes
          - employment_type: one of the accepted values
        """
        errors: list[str] = []

        # ── Name ────────────────────────────────────────────────────────────
        name = str(payload.get("name", "") or "").strip()
        if not name:
            errors.append("Full Name is required. Please enter the applicant's name.")
        elif len(name) < 2:
            errors.append("Full Name must be at least 2 characters long.")
        elif name.replace(" ", "").isdigit():
            errors.append("Full Name cannot consist entirely of numbers. Please enter a valid name.")
        elif all(c in "!@#$%^&*()_+-=[]{}|;':,./<>?" for c in name.replace(" ", "")):
            errors.append("Full Name appears to contain only special characters. Please enter a valid name.")

        # ── Age ─────────────────────────────────────────────────────────────
        age = payload.get("age", 0)
        try:
            age = int(age)
            if age == 0:
                errors.append("Age cannot be 0. Please enter the applicant's actual age.")
            elif age < 18:
                errors.append(f"Age {age} is below the minimum eligibility age of 18 years.")
            elif age > 100:
                errors.append(f"Age {age} exceeds the maximum allowed value of 100.")
        except (TypeError, ValueError):
            errors.append("Age must be a valid whole number.")

        # ── Monthly Income ───────────────────────────────────────────────────
        income = payload.get("monthly_income", 0)
        try:
            income = float(income)
            if income < 0:
                errors.append("Monthly Income cannot be negative.")
            elif income == 0:
                errors.append(
                    "Monthly Income is 0. If the applicant has no income, "
                    "they will not meet the bank's minimum lending requirements."
                )
        except (TypeError, ValueError):
            errors.append("Monthly Income must be a valid number.")

        # ── Credit Score ─────────────────────────────────────────────────────
        credit = payload.get("credit_score", 0)
        try:
            credit = int(credit)
            if credit < 300:
                errors.append(f"Credit Score {credit} is below the valid range (300–900).")
            elif credit > 900:
                errors.append(f"Credit Score {credit} exceeds the valid range (300–900).")
        except (TypeError, ValueError):
            errors.append("Credit Score must be a valid whole number between 300 and 900.")

        # ── Loan Amount Requested ────────────────────────────────────────────
        loan_amount = payload.get("loan_amount_requested", 0)
        try:
            loan_amount = float(loan_amount)
            if loan_amount <= 0:
                errors.append(
                    "Loan Amount Requested must be greater than 0. "
                    "Please enter the amount the applicant wishes to borrow."
                )
            elif loan_amount > 100_000_000:  # 10 crore cap
                errors.append(
                    f"Loan Amount of Rs.{int(loan_amount):,} exceeds the maximum "
                    "supported limit of Rs.10,00,00,000 (10 Crore)."
                )
        except (TypeError, ValueError):
            errors.append("Loan Amount Requested must be a valid number.")

        # ── Loan Purpose ─────────────────────────────────────────────────────
        purpose = str(payload.get("loan_purpose", "") or "").strip()
        if not purpose:
            errors.append("Loan Purpose is required. Please describe the intended use of the loan.")
        elif len(purpose) < 3:
            errors.append(
                f"Loan Purpose '{purpose}' is too short. "
                "Please provide a meaningful description (e.g. 'Home Renovation', 'Education').")

        # ── Employment Type ──────────────────────────────────────────────────
        valid_employment = {"Salaried", "Self-employed", "Business", "Student", "Unemployed", "Retired"}
        emp = str(payload.get("employment_type", "") or "").strip()
        if not emp:
            errors.append("Employment Type is required.")
        elif emp not in valid_employment:
            errors.append(
                f"Employment Type '{emp}' is not recognised. "
                f"Accepted values: {', '.join(sorted(valid_employment))}.")

        # ── Existing Loan / Monthly Payment ──────────────────────────────────
        existing_loan = str(payload.get("existing_loan", "No") or "No").strip()
        emi = payload.get("monthly_loan_payment", 0)
        try:
            emi = float(emi)
            if emi < 0:
                errors.append("Monthly EMI/Loan Payment cannot be negative.")
            elif existing_loan == "Yes" and emi == 0:
                errors.append(
                    "You indicated an existing loan but the monthly EMI/payment is 0. "
                    "Please enter the actual monthly payment amount."
                )
            elif existing_loan == "Yes" and income > 0 and emi >= income:
                errors.append(
                    f"Monthly EMI (Rs.{int(emi):,}) equals or exceeds "
                    f"Monthly Income (Rs.{int(income):,}). Please verify these values."
                )
        except (TypeError, ValueError):
            errors.append("Monthly EMI/Loan Payment must be a valid number.")

        return errors

    # ── Public interface ────────────────────────────────────────────────────────
    def clear_memory(self) -> None:
        """Clears conversation memory. Call this to start a fresh session."""
        LoanEligibilityAgent._shared_memory = None
        self.memory.clear()

    def assess(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point.

        Pre-flight edge case validation runs first (Python-level).
        If inputs are invalid, returns a clear corrective message immediately.
        Otherwise, the LangChain ReAct agent handles all decision-making.

        Output detection:
          - "### 1. Eligibility Result" in response → full report
          - Otherwise → conversational question/follow-up
        """
        # ── Pre-flight: Edge case validation ────────────────────────────────
        # Catches invalid/nonsensical inputs BEFORE they reach the agent or tool.
        validation_errors = self._validate_payload(payload)
        if validation_errors:
            error_lines = "\n".join(f"  • {e}" for e in validation_errors)
            return {
                "needs_more_info": True,
                "message": (
                    f"⚠️ Please correct the following before we can proceed:\n\n"
                    f"{error_lines}\n\n"
                    "Once these are fixed, click **Launch Assessment** again."
                ),
            }

        # ── Build input string for the agent ────────────────────────────────
        agent_input = (
            f"Loan application data:\n{json.dumps(payload, indent=2)}\n\n"
            "If all required fields are present, evaluate this application and write "
            "the full 5-section underwriting report. If any required field is missing, "
            "ask for it conversationally."
        )

        # ── Step 1: Run the ReAct agent ─────────────────────────────────────
        agent_output = ""
        intermediate_steps = []
        try:
            result = self._react_agent.invoke({"input": agent_input})
            agent_output = result.get("output", "").strip()
            intermediate_steps = result.get("intermediate_steps", [])
        except Exception:
            agent_output = ""

        # ── Step 2: Detect output type ──────────────────────────────────────
        is_full_report = REPORT_MARKER in agent_output and len(agent_output.strip()) >= 80

        # ── Step 3: Conversational follow-up (agent asked for missing data) ──
        if not is_full_report and agent_output:
            return {
                "needs_more_info": True,
                "message": agent_output,
            }

        # ── Step 4: Extract evaluation dict from tool's intermediate result ──
        evaluation = {}
        needed_income = 0.0
        for action, observation in intermediate_steps:
            if hasattr(action, "tool") and action.tool == "evaluate_loan_eligibility":
                try:
                    tool_data = json.loads(observation)
                    needed_income = tool_data.get("required_income_for_eligibility", 0.0)
                    evaluation = {
                        "eligibility": tool_data["eligibility"],
                        "score": tool_data["score"],
                        "key_factors": tool_data.get("key_factors", {}),
                        "scoring_breakdown": tool_data.get("scoring_breakdown", {}),
                        "reasons": tool_data.get("reasons", []),
                        "next_steps": tool_data.get("next_steps", []),
                        "estimated_terms": tool_data.get("estimated_terms", {}),
                    }
                except (json.JSONDecodeError, KeyError):
                    pass

        # ── Step 5: Agent produced a valid report ───────────────────────────
        if is_full_report and evaluation:
            return {
                "needs_more_info": False,
                "evaluation": evaluation,
                "explanation": agent_output,
            }

        # ── Step 6: Fallback — call tool directly, then use LCEL chain ──────
        # The rule engine is ALWAYS accessed through the LangChain tool.
        # Never call self.engine.evaluate() directly here.
        fallback_tool_json: str = self._tool_fn.invoke(json.dumps(payload))
        try:
            fallback_tool_data = json.loads(fallback_tool_json)
        except json.JSONDecodeError:
            fallback_tool_data = {}

        fallback_eval = {
            "eligibility": fallback_tool_data.get("eligibility", "Not Eligible"),
            "score": fallback_tool_data.get("score", 0),
            "key_factors": fallback_tool_data.get("key_factors", {}),
            "scoring_breakdown": fallback_tool_data.get("scoring_breakdown", {}),
            "reasons": fallback_tool_data.get("reasons", []),
            "next_steps": fallback_tool_data.get("next_steps", []),
            "estimated_terms": fallback_tool_data.get("estimated_terms", {}),
        }
        needed_income_fallback = fallback_tool_data.get("required_income_for_eligibility", 0.0)

        explanation = ""
        try:
            # _run_lcel_chain already calls the tool internally — pass payload only
            explanation = self._run_lcel_chain(payload)
        except Exception:
            explanation = ""

        if not explanation or len(explanation.strip()) < 80:
            explanation = self._build_fallback_explanation(fallback_eval, needed_income_fallback)

        return {
            "needs_more_info": False,
            "evaluation": fallback_eval,
            "explanation": explanation,
        }


    # ── LCEL fallback chain ─────────────────────────────────────────────────────
    def _run_lcel_chain(self, payload: Dict[str, Any]) -> str:
        """
        LCEL fallback chain.
        Calls the LangChain tool directly (via self._tool_fn) to get the
        rule engine result, then feeds it to the plain LLM to write the report.
        The rule engine is NEVER accessed directly — always through the tool.
        """
        # Always go through the LangChain tool — never call engine directly
        tool_result_json: str = self._tool_fn.invoke(json.dumps(payload))
        try:
            tool_data = json.loads(tool_result_json)
        except json.JSONDecodeError:
            return ""

        prompt = ChatPromptTemplate.from_messages([
            ("system", LCEL_SYSTEM_PROMPT),
            MessagesPlaceholder("messages"),
        ])

        user_msg = HumanMessage(
            content=(
                "Produce the full 5-section underwriting report for this application.\n"
                f"Customer Data: {json.dumps(payload)}"
            )
        )
        ai_msg = AIMessage(content="Evaluating using the rule engine tool...")
        tool_msg = ToolMessage(
            content=tool_result_json,
            tool_call_id="rule_engine_eval",
            name="evaluate_loan_eligibility",
        )

        chain = prompt | self.llm
        response = chain.invoke({"messages": [user_msg, ai_msg, tool_msg]})
        return (response.content or "").strip()

    # ── Deterministic fallback report ───────────────────────────────────────────
    def _build_fallback_explanation(
        self, evaluation: Dict[str, Any], needed_income: float = 0.0
    ) -> str:
        """Fully deterministic 5-section report. Used when LLM is unavailable."""
        eligibility = evaluation["eligibility"]
        factors    = evaluation["key_factors"]
        reasons    = evaluation["reasons"]
        steps      = evaluation["next_steps"]
        score      = evaluation["score"]
        breakdown  = evaluation["scoring_breakdown"]
        terms      = evaluation["estimated_terms"]
        risk_cat   = terms.get("risk_category", "High")

        income    = factors.get("monthly_income", 0) or 0
        credit    = factors.get("credit_score", 0) or 0
        liabs     = factors.get("existing_liabilities", 0) or 0
        emp       = factors.get("employment_type", "Unknown")
        requested = factors.get("loan_amount_requested", 0) or 0
        dti       = round((liabs / income * 100), 1) if income else 0

        def _status(pts, threshold=1):
            return "Passed" if pts >= threshold else "Review Required"

        verdict_detail = {
            "Eligible": "Meets the bank's baseline lending criteria and is Eligible for Consideration.",
            "Conditionally Eligible": "Meets partial criteria. Additional verification is required.",
            "Not Eligible": "Does not currently meet the bank's minimum lending criteria.",
        }.get(eligibility, "")

        risk_meaning = {
            "Very Low": "Bank exposure is minimal. Strong candidate.",
            "Low": "Bank exposure is low. Profile is generally stable.",
            "Moderate": "Some risk factors present. Further review advised.",
            "High": "Significant risk factors identified. Caution recommended.",
            "Very High": "Multiple critical thresholds failed. Not recommended.",
            "Invalid Input": "Data provided was invalid or could not be assessed.",
        }.get(risk_cat, "Risk level is undetermined.")

        s1 = (
            f"### 1. Eligibility Result\n"
            f"   - **Status: {eligibility}** — {verdict_detail}\n"
            f"   - **Rule Engine Score:** {score}/100\n"
            f"   - **Risk Category:** {risk_cat} — {risk_meaning}"
        )

        s2 = (
            f"### 2. Key Evaluation Factors\n"
            f"   - **Monthly Income (Rs.{income:,}):** {_status(breakdown.get('Income',0))} — "
            + ("Meets preferred baseline (Rs.50,000+)." if breakdown.get("Income",0)>=2 else
               "Below preferred threshold of Rs.50,000." if breakdown.get("Income",0)==1 else
               "Below minimum baseline of Rs.30,000.") + "\n"
            f"   - **Credit Score ({credit}):** {_status(breakdown.get('Credit Score',0))} — "
            + ("Excellent (750+)." if breakdown.get("Credit Score",0)==2 else
               "Acceptable, below 750 threshold." if breakdown.get("Credit Score",0)==1 else
               f"Below minimum threshold of 600.") + "\n"
            f"   - **Employment ({emp}):** {_status(breakdown.get('Employment',0),0)} — "
            + ("Salaried — most preferred." if emp=="Salaried" else
               "Self-employed/Business — acceptable." if emp in ["Self-employed","Business"] else
               "Student/Unemployed — high risk.") + "\n"
            f"   - **Liabilities (DTI: {dti}%):** {_status(breakdown.get('Liabilities',0))} — "
            + ("Within acceptable limits." if breakdown.get("Liabilities",0)==2 else
               "Moderate — may affect repayment." if breakdown.get("Liabilities",0)==1 else
               f"DTI {dti}% exceeds 40% cap.") + "\n"
            f"   - **Loan Amount (Rs.{requested:,}):** {_status(breakdown.get('Loan Request',0))} — "
            + ("Within income multiple range." if breakdown.get("Loan Request",0)>=1 else
               f"High relative to income of Rs.{income:,}.")
        )

        reasons_text = "\n".join(f"   - {r}" for r in reasons) or "   - No specific flags raised."
        income_upgrade_line = ""
        if eligibility != "Eligible" and needed_income and needed_income > income:
            income_upgrade_line = (
                f"\n   - If your income increases to Rs.{int(needed_income):,}, you become eligible."
            )

        decision_basis = (
            "All critical thresholds were met." if eligibility == "Eligible"
            else "One or more critical thresholds were not met."
        )
        s3 = (
            f"### 3. Reasoning Summary\n"
            f"   - **Decision Basis:** {decision_basis}\n"
            f"   - **Income:** Rs.{income:,} {'meets' if breakdown.get('Income',0)>=1 else 'does not meet'} the minimum lending threshold.\n"
            f"   - **Credit:** Score of {credit} {'is strong (750+).' if credit>=750 else 'is acceptable.' if credit>=600 else 'is below the 600 minimum.'}\n"
            f"   - **DTI:** {dti}% {'is within limits.' if dti<=40 else 'exceeds the 40% cap.'}\n"
            f"   - **Flags:**\n{reasons_text}"
            f"{income_upgrade_line}"
        )

        steps_detail = "\n".join(f"   - {s}" for s in steps)
        s4 = f"### 4. Suggested Next Steps\n{steps_detail}"
        s5 = (
            "### 5. Disclaimer\n"
            "   - This is an AI-generated informational assessment for decision-support purposes only. "
            "It does not constitute a final credit approval. All decisions must be verified by an "
            "authorized banking officer in accordance with institutional policy."
        )

        return f"{s1}\n\n{s2}\n\n{s3}\n\n{s4}\n\n{s5}"
