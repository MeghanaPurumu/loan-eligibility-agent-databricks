import requests
from typing import Any, Dict, List, Optional
from langchain_core.messages import BaseMessage, AIMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatResult, ChatGeneration

class CustomDatabricksChat(BaseChatModel):
    """
    A robust custom LangChain wrapper for Databricks Model Serving.
    Ensures 100% compatibility with the LangChain framework while bypassing 
    fragile package dependency issues (like ModuleNotFoundError).
    Automatically fixes missing HTTPS schemes in host URLs.
    """
    endpoint: str
    host: str
    token: str
    temperature: float = 0.2
    max_tokens: int = 500

    @property
    def _llm_type(self) -> str:
        return "custom_databricks_chat"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        # Fix scheme if missing
        clean_host = self.host.strip()
        if not clean_host.startswith("http"):
            clean_host = f"https://{clean_host}"
            
        url = f"{clean_host.rstrip('/')}/serving-endpoints/{self.endpoint}/invocations"
        
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        # Convert LangChain messages to OpenAI schema expected by Databricks
        formatted_messages = []
        for m in messages:
            role = "user"
            if m.type == "system":
                role = "system"
            elif m.type == "ai":
                role = "assistant"
            formatted_messages.append({"role": role, "content": m.content})
            
        payload = {
            "messages": formatted_messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
        
        res = requests.post(url, json=payload, headers=headers, timeout=60)
        res.raise_for_status()
        
        choices = res.json().get("choices", [])
        content = choices[0].get("message", {}).get("content", "").strip() if choices else ""
        
        message = AIMessage(content=content)
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])
