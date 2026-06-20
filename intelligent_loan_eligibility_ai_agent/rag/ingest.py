import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import logging
from pathlib import Path
from typing import List
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from config import settings
from rag.vector_store import build_local_faiss_index

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fallback text policy in case PDF is not present
FALLBACK_POLICY_TEXT = """
Loan Eligibility Policy Document - BFSI Lending Division

1. GENERAL APPLICANT AGE CRITERIA
1.1 All applicants requesting retail lending products must be between the ages of 21 and 60 years at the time of application submission.
1.2 Requests from applicants outside of this age range are categorized as "Not Eligible" immediately. Age exceptions are subject to senior underwriting committee review and collateral backing.

2. INCOME BASELINES AND EMPLOYMENT STATUS
2.1 Minimum monthly verified net income required for loan eligibility is INR 30,000.
2.2 Applicants earning between INR 30,000 and INR 50,000 are classified as "Conditionally Eligible", requiring additional guarantors or security pledges.
2.3 Applicants with net monthly income of INR 50,000 and above meet the baseline income requirements for standard loan terms.
2.4 Salaried employees represent the lowest risk category and are preferred. Business owners and self-employed applicants are conditionally accepted based on 2 years of tax returns.
2.5 Unemployed applicants, students, and retired applicants are categorized as high-risk or Not Eligible unless sufficient co-signers or pension streams are verified.

3. CREDIT HISTORY AND BUREAU SCORES
3.1 The bank utilizes credit bureau scores ranging from 300 to 900.
3.2 Any applicant with a credit bureau score below 600 is classified as "Not Eligible" due to default history or high credit risk.
3.3 Credit scores between 600 and 749 are acceptable under conditional eligibility, subject to high-liability ratio review.
3.4 Credit scores of 750 and above represent excellent credit history and are fast-tracked for preferred interest rates.

4. EXISTING DEBT AND LIABILITIES
4.1 The Debt-to-Income (DTI) ratio is computed as total monthly existing EMIs divided by net monthly verified income.
4.2 A DTI ratio below 25% represents low liability and is preferred.
4.3 A DTI ratio between 25% and 40% is acceptable under conditional eligibility terms.
4.4 Any DTI ratio exceeding 40% represents excessive leverage and results in a "Not Eligible" verdict.

5. LOAN REQUEST LIMITS
5.1 The maximum allowable loan amount requested cannot exceed 20 times the verified monthly net income of the applicant.
5.2 Requested amounts exceeding this multiple are flagged as high risk and require loan reduction.
"""

def extract_pdf_text(pdf_path: Path) -> str:
    """Extracts text content from a PDF file using pypdf."""
    text = ""
    try:
        import pypdf
        if pdf_path.exists():
            reader = pypdf.PdfReader(str(pdf_path))
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            logger.info(f"Successfully extracted text from {pdf_path}")
            return text
        else:
            logger.warning(f"PDF file not found at {pdf_path}. Using fallback policy text.")
    except Exception as e:
        logger.error(f"Failed to read PDF file: {e}. Using fallback policy text.")
    
    return FALLBACK_POLICY_TEXT

def ingest_policy_data():
    """Main ingestion flow reading policy document and rules, chunking, and writing to vector store."""
    pdf_path = settings.POLICY_PDF_PATH
    rules_path = settings.RULES_PATH

    logger.info("Extracting policy documents...")
    policy_text = extract_pdf_text(pdf_path)

    # Convert rules to text format for vector lookup compatibility
    rules_text = ""
    if rules_path.exists():
        try:
            rules_data = json.loads(rules_path.read_text(encoding="utf-8"))
            rules_text = "Loan Eligibility Rules Config:\n" + json.dumps(rules_data, indent=2)
            logger.info("Successfully read loan rules rules for ingestion context.")
        except Exception as e:
            logger.error(f"Failed to read rules JSON: {e}")
    
    # Compile document sources
    raw_documents = [
        Document(page_content=policy_text, metadata={"source": "loan_policy.pdf"}),
    ]
    if rules_text:
        raw_documents.append(Document(page_content=rules_text, metadata={"source": "loan_rules.json"}))

    # Split documents into chunks
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    split_docs = text_splitter.split_documents(raw_documents)
    logger.info(f"Split documents into {len(split_docs)} chunks.")

    # Save to local FAISS index
    success = build_local_faiss_index(split_docs, settings.FAISS_INDEX_PATH)
    if success:
        logger.info("Ingestion completed successfully!")
    else:
        logger.error("Ingestion failed.")

if __name__ == "__main__":
    ingest_policy_data()
