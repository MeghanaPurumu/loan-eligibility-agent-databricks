# Architecture

```text
User -> Streamlit UI -> LoanEligibilityAgent -> LoanRuleEngine
                                         -> OllamaClient (local LLM)
                                         -> Explanation Output
```

### Components
- **Streamlit UI**: Collects customer input and displays results.
- **LoanEligibilityAgent**: Orchestrates validation, evaluation, and explanation.
- **LoanRuleEngine**: Reads policy from JSON and computes the decision.
- **OllamaClient**: Calls the local Ollama API for natural-language explanations.
