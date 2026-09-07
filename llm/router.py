from llm.ollama_provider import get_ollama_response
from llm.groq_provider import get_groq_response


def get_llm_response(provider: str, messages):
    """
    Send messages to the selected LLM provider.

    Returns the provider response as a Python dictionary.
    """

    provider = provider.lower().strip()

    # ========================================================
    # GROQ
    # ========================================================

    if provider == "groq":

        return get_groq_response(
            messages
        )

    # ========================================================
    # OLLAMA
    # ========================================================

    if provider == "ollama":

        return get_ollama_response(
            messages
        )

    # ========================================================
    # UNSUPPORTED PROVIDER
    # ========================================================

    raise ValueError(
        f"Unsupported LLM provider: {provider}. "
        "Choose 'ollama' or 'groq'."
    )