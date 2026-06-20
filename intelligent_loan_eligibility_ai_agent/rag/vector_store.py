import logging
from pathlib import Path
from typing import List
from langchain_community.vectorstores import FAISS
from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from config import settings

logger = logging.getLogger(__name__)

class FakeLocalEmbeddings(Embeddings):
    """Fallback dummy embeddings model for offline/local development."""
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        # Return a list of arbitrary 128-dimensional vectors
        return [[0.1] * 128 for _ in texts]
        
    def embed_query(self, text: str) -> List[float]:
        return [0.1] * 128

def build_local_faiss_index(documents: List[Document], save_path: Path):
    """
    Builds a local FAISS index from LangChain Document objects.
    Uses OllamaEmbeddings, falling back to FakeLocalEmbeddings if offline.
    """
    db = None
    try:
        embeddings = OllamaEmbeddings(
            model=settings.OLLAMA_EMBED_MODEL,
            base_url=settings.OLLAMA_BASE_URL
        )
        logger.info(f"Embedding {len(documents)} documents using Ollama model '{settings.OLLAMA_EMBED_MODEL}'...")
        db = FAISS.from_documents(documents, embeddings)
    except Exception as e:
        logger.warning(f"Ollama Embeddings failed: {e}. Falling back to FakeLocalEmbeddings.")
        try:
            embeddings = FakeLocalEmbeddings()
            db = FAISS.from_documents(documents, embeddings)
        except Exception as fe:
            logger.error(f"Fallback embeddings also failed: {fe}")
            return False

    if db:
        try:
            # Ensure target directory exists
            save_path.parent.mkdir(parents=True, exist_ok=True)
            db.save_local(str(save_path))
            logger.info(f"FAISS index successfully saved to {save_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save FAISS index: {e}")
    return False
