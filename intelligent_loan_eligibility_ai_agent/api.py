from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List

from config import settings
from agents.loan_orchestrator import orchestrate_loan_assessment
import sqlite3
import re

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI(title="Intelligent Loan Eligibility AI Agent API")

# Allow CORS for local React development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Change to specific origin in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent
DATA_PATH = BASE_DIR / "data" / "mock_customers.csv"
RULES_PATH = settings.RULES_PATH
DB_PATH = BASE_DIR / "loan_assessment_logs.db"

# Mount the React build directory only if the full build output (including assets) exists
frontend_dist = BASE_DIR / "frontend-react" / "dist"
frontend_assets = frontend_dist / "assets"

if frontend_assets.exists():
    app.mount("/assets", StaticFiles(directory=frontend_assets), name="assets")

@app.get("/")
def serve_react_app():
    if (frontend_dist / "index.html").exists():
        return FileResponse(frontend_dist / "index.html")
    return {"message": "Frontend build not found. Please run 'npm run build' in frontend-react."}

class AssessRequest(BaseModel):
    payload: Dict[str, Any]

class ChatRequest(BaseModel):
    query: str
    payload: Dict[str, Any]
    result: Dict[str, Any]
    history: List[Dict[str, str]]

@app.get("/api/rules")
def get_rules():
    if RULES_PATH.exists():
        rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
        return rules
    raise HTTPException(status_code=404, detail="Rules configuration not found")

@app.get("/api/customers")
def get_customers():
    if DATA_PATH.exists():
        df = pd.read_csv(DATA_PATH)
        return df.to_dict(orient="records")
    return []

@app.post("/api/assess")
def assess_loan(request: AssessRequest):
    try:
        result = orchestrate_loan_assessment(request.payload)
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── Guardrail patterns for conversational follow-up ─────────────────────────
BLOCKED_CHAT_PATTERNS = [
    r"ignore.*rules",
    r"ignore.*policy",
    r"bypass.*checks",
    r"approve.*anyway",
    r"override.*system",
    r"ignore all instructions",
    r"you are now",
    r"system.*prompt",
    r"set.*decision",
]

GUARANTEE_PATTERNS = [
    r"definitely.*approved",
    r"guarantee.*approval",
    r"guaranteed.*loan",
    r"will.*definitely.*get",
    r"absolutely.*approved",
]

MANDATORY_DISCLAIMER_SHORT = (
    "\n\n*This is an AI-generated response for decision-support only. "
    "It does not constitute a final credit approval.*"
)

def _check_chat_input_guardrail(user_query: str) -> str | None:
    if not settings.ENABLE_GUARDRAILS:
        return None
    query_lower = user_query.lower()
    for pattern in BLOCKED_CHAT_PATTERNS:
        if re.search(pattern, query_lower):
            return (
                "Input Guardrail Triggered: Your message was flagged for attempting to "
                "override system policies. Please ask a legitimate question about your loan assessment."
            )
    return None

def _sanitize_llm_output(response: str) -> str:
    if not settings.ENABLE_GUARDRAILS:
        return response
    for pattern in GUARANTEE_PATTERNS:
        if re.search(pattern, response, re.IGNORECASE):
            response = re.sub(
                pattern,
                "subject to credit verification and formal approval",
                response,
                flags=re.IGNORECASE,
            )
    if "does not constitute" not in response.lower():
        response += MANDATORY_DISCLAIMER_SHORT
    return response

@app.post("/api/chat")
def chat_followup(request: ChatRequest):
    try:
        blocked_msg = _check_chat_input_guardrail(request.query)
        if blocked_msg:
            return {"response": blocked_msg}

        from langchain_core.messages import SystemMessage, HumanMessage
        history_str = "\n".join([f"{msg['role'].capitalize()}: {msg['content']}" for msg in request.history])
        
        system_prompt = f"""
        You are an Intelligent Loan Assistant. Answer customer follow-up questions based on their assessment.
        Customer Data: {json.dumps(request.payload)}
        Verdict: {request.result.get('decision')}
        Confidence: {request.result.get('confidence')}
        Orchestration factors: {request.result.get('evaluation_factors')}

        Rules:
        - Never guarantee loan approvals. Use terms like "subject to verification" or "preliminary assessment".
        - Be polite, professional, and clear.
        - Use data and rule constraints in explanations.
        - Always mention specific numbers from the customer data when explaining decisions.
        - If the customer asks about improving eligibility, give actionable advice.
        """

        user_prompt = f"""
        Conversation History:
        {history_str}

        Customer Question: {request.query}
        """

        try:
            if settings.MODEL_PROVIDER.lower() == "databricks":
                from tools.custom_llm import CustomDatabricksChat
                llm = CustomDatabricksChat(
                    host=settings.DATABRICKS_HOST,
                    token=settings.DATABRICKS_TOKEN,
                    endpoint=settings.DATABRICKS_SERVING_ENDPOINT,
                    temperature=0.2,
                    max_tokens=500
                )
            else:
                from langchain_ollama import ChatOllama
                llm = ChatOllama(
                    model=settings.OLLAMA_MODEL,
                    base_url=settings.OLLAMA_BASE_URL,
                    temperature=0.2
                )
                
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            response_msg = llm.invoke(messages)
            response = response_msg.content.strip()
        except Exception as e:
            print(f"LLM follow-up failed: {e}")
            response = _get_fallback_chat_response(request.query, request.payload, request.result)
        
        response = _sanitize_llm_output(response)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _get_fallback_chat_response(query: str, payload: Dict[str, Any], result: Dict[str, Any]) -> str:
    """Intelligent rules-based fallback response when LLM endpoints are unreachable."""
    try:
        from tools.eligibility_engine import LoanRuleEngine
        from core.utils import parse_number
        
        engine = LoanRuleEngine()
        evaluation = engine.evaluate(payload)
    except Exception as ex:
        print(f"Fallback engine evaluation failed: {ex}")
        return "I am currently unable to access the policy engine to analyze your profile. Please try again later."

    q = query.lower()
    
    # 1. Ask to improve eligibility
    if any(x in q for x in ["improve", "how to", "what to do", "increase", "better", "fix", "rectify", "help"]):
        advice = []
        if evaluation.eligibility == "Eligible":
            return "Your application is currently rated as **Eligible**. You do not need to make any specific profile improvements. Please proceed with submitting your standard KYC documents (PAN/Aadhaar, address proof, bank statements, and salary slips) for formal underwriting review."
            
        # Address income / DTI
        if evaluation.required_income_for_eligibility > 0:
            needed_formatted = f"INR {int(evaluation.required_income_for_eligibility):,}"
            advice.append(f"• **Increase Monthly Income:** Your income is below the optimal threshold for the requested loan. Increasing your monthly income to approximately **{needed_formatted}** or adding a co-applicant with regular income will significantly improve your status.")
            
        # Address credit score
        credit = payload.get("credit_score", 0)
        try:
            credit_val = int(parse_number(credit) or 0)
            if credit_val < 750:
                advice.append("• **Boost Credit Score:** Your current credit score is below our premium benchmark (750). To improve this, ensure all utility bills, credit card balances, and existing EMI payments are settled on time, and limit new credit inquiries.")
        except:
            pass
            
        # Address existing liabilities / EMI
        existing = payload.get("existing_loan")
        if existing == "Yes" or payload.get("monthly_loan_payment"):
            advice.append("• **Reduce Outstanding Debt:** High existing monthly EMI obligations increase your debt-to-income ratio. Paying off smaller outstanding loans before applying will lower your liabilities and boost borrowing eligibility.")
            
        # Address requested loan amount
        requested = payload.get("loan_amount_requested", 0)
        try:
            requested_val = int(parse_number(requested) or 0)
            income_val = int(parse_number(payload.get("monthly_income", 1)) or 1)
            if income_val > 0 and (requested_val / income_val) > 20:
                suggested_max = income_val * 20
                suggested_formatted = f"INR {int(suggested_max):,}"
                advice.append(f"• **Reduce Requested Amount:** The requested loan amount is high relative to your income. Consider lowering your request to around **{suggested_formatted}** to fit within the standard multiplier guidelines.")
        except:
            pass
            
        if not advice:
            advice.append("• **Provide Co-applicant Details:** Adding a co-applicant (spouse or parent) with a stable income and a strong credit history can help mitigate high-risk indicators.")
            
        response_str = "Based on our policy rules, here are key actionable steps you can take to improve your loan eligibility:\n\n" + "\n\n".join(advice)
        return response_str
        
    # 2. General why rejected
    if any(x in q for x in ["why", "reason", "rejected", "decline", "failed", "not eligible"]):
        reasons = evaluation.reasons
        if reasons:
            reasons_str = "\n".join([f"- {r}" for r in reasons])
            return f"Your preliminary assessment status is **{evaluation.eligibility}** due to the following policy criteria:\n\n{reasons_str}\n\nOur system requires applicants to meet specific thresholds for age, income, debt-to-income ratio, and credit history to ensure institutional compliance."
        else:
            return "Your application does not currently meet our baseline eligibility criteria. This is typically due to a combination of credit score, debt-to-income ratio, or income requirements."
            
    # 3. Default fallback answer
    return (
        f"As your virtual assistant, I can confirm your current preliminary assessment status is **{evaluation.eligibility}** "
        f"with an eligibility score of **{evaluation.score}/100**. For specific tips on how to improve this assessment, please ask 'What should I improve?'"
    )

@app.get("/api/dashboard")
def get_dashboard_data():
    if DB_PATH.exists():
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM loan_assessment_logs")
            data = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            conn.close()
            
            result = []
            for row in data:
                result.append(dict(zip(columns, row)))
            return {"data": result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to load logs: {e}")
    return {"data": []}
