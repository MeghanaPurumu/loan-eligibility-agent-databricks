import json
import logging
import requests
from typing import Any, Dict, List
from config import settings

logger = logging.getLogger(__name__)

def retrieve(query: str, limit: int = 3) -> Dict[str, Any]:
    """
    Main retrieval entry point. Dynamically routes requests based on VECTOR_BACKEND.
    Returns:
        Dict: {"policy": str, "documents": List[str], "confidence": float}
    """
    if not settings.ENABLE_RAG:
        return {"policy": "RAG retrieval is disabled.", "documents": [], "confidence": 0.0}

    backend = settings.VECTOR_BACKEND.lower()
    if backend == "databricks":
        return vector_search_retrieve(query, limit)
    else:
        return faiss_retrieve(query, limit)

def faiss_retrieve(query: str, limit: int = 3) -> Dict[str, Any]:
    """
    Queries local FAISS index for relevant loan policy chunks.
    Falls back to a keyword-matching mockup if the index files are missing.
    """
    try:
        from langchain_community.vectorstores import FAISS
        from langchain_ollama import OllamaEmbeddings
        from rag.vector_store import FakeLocalEmbeddings
        
        index_path = settings.FAISS_INDEX_PATH
        if index_path.exists():
            try:
                embeddings = OllamaEmbeddings(
                    model=settings.OLLAMA_EMBED_MODEL,
                    base_url=settings.OLLAMA_BASE_URL
                )
                db = FAISS.load_local(str(index_path), embeddings, allow_dangerous_deserialization=True)
            except Exception as ee:
                logger.warning(f"Failed to load FAISS with Ollama embeddings: {ee}. Trying FakeLocalEmbeddings.")
                embeddings = FakeLocalEmbeddings()
                db = FAISS.load_local(str(index_path), embeddings, allow_dangerous_deserialization=True)
            
            docs_and_scores = db.similarity_search_with_score(query, k=limit)
            
            doc_texts = []
            avg_score = 0.0
            for doc, score in docs_and_scores:
                doc_texts.append(doc.page_content)
                # FAISS L2 distance score: lower is better. Normalize to confidence
                avg_score += score
                
            confidence = max(0.0, min(1.0, 1.0 - (avg_score / (len(docs_and_scores) or 1)) / 2.0))
            
            return {
                "policy": "\n\n".join(doc_texts),
                "documents": doc_texts,
                "confidence": round(confidence, 2)
            }
    except Exception as e:
        logger.warning(f"Local FAISS retrieval failed: {e}. Falling back to keyword search.")
        
    # Keyword search fallback
    return keyword_search_fallback(query)

def vector_search_retrieve(query: str, limit: int = 3) -> Dict[str, Any]:
    """
    Queries Databricks Vector Search endpoint using Databricks REST API.
    """
    host = settings.DATABRICKS_HOST
    token = settings.DATABRICKS_TOKEN
    index_name = settings.DATABRICKS_VECTOR_INDEX

    if not host or not token or not index_name:
        return {
            "policy": "Databricks Vector Search is unconfigured. Running in fallback mode.",
            "documents": ["Missing configuration keys (HOST/TOKEN/INDEX_NAME)"],
            "confidence": 0.0
        }

    # Fix scheme if missing
    clean_host = host.strip()
    if not clean_host.startswith("http"):
        clean_host = f"https://{clean_host}"

    # REST Endpoint for Vector Search Query
    url = f"{clean_host.rstrip('/')}/api/2.0/vector-search/indexes/{index_name}/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "query_text": query,
        "columns": ["text"],
        "num_results": limit
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Parse output structure
        results = data.get("result", {}).get("data_array", [])
        documents = []
        for res in results:
            if len(res) > 0:
                documents.append(str(res[0]))
                
        confidence = 0.85 if len(documents) > 0 else 0.0
        return {
            "policy": "\n\n".join(documents) if documents else "No matching documents found.",
            "documents": documents,
            "confidence": confidence
        }
    except Exception as e:
        logger.warning(f"Databricks Vector Search unavailable ({type(e).__name__}). Falling back to keyword search.")
        return keyword_search_fallback(query)

def keyword_search_fallback(query: str) -> Dict[str, Any]:
    """
    Simple rule/keyword match for development fallback.
    """
    query_lower = query.lower()
    docs = []
    
    # Check rules and basic terms
    if "income" in query_lower:
        docs.append("Loan Policy Section 2.1: Monthly income must exceed INR 30,000 baseline. Prefer INR 50,000+ for standard terms.")
    if "credit" in query_lower or "score" in query_lower:
        docs.append("Loan Policy Section 3.2: Credit score must be >= 600. Scores >= 750 receive premium pricing benefits.")
    if "age" in query_lower:
        docs.append("Loan Policy Section 1.5: Applicants must be between 21 and 60 years old at application date.")
    if "liability" in query_lower or "emi" in query_lower or "debt" in query_lower:
        docs.append("Loan Policy Section 4.4: Debt-to-income (DTI) ratio must be <= 40% including the requested loan EMI.")
    
    if not docs:
        docs.append("General Policy Guidelines: All loan eligibility relies on rules, age restrictions, and credit scores.")

    return {
        "policy": "\n\n".join(docs),
        "documents": docs,
        "confidence": 0.50
    }
