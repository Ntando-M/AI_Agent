from langchain_ollama import OllamaEmbeddings


# Keep this model fixed after documents have been indexed.
EMBEDDING_MODEL = "nomic-embed-text"


def get_embedding_model() -> OllamaEmbeddings:
    """
    Create and return the Ollama embedding model.
    """

    return OllamaEmbeddings(
        model=EMBEDDING_MODEL
    )