from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document

from rag.embeddings import get_embedding_model


# Persistent location for the Chroma vector database
VECTOR_STORE_DIRECTORY = Path("chroma_db")

# Name of the Chroma collection
COLLECTION_NAME = "ai_data_analyst_documents"


def create_vector_store(
    chunks: list[Document],
) -> Chroma:
    """
    Create a persistent Chroma vector store from document chunks.

    The document chunks are embedded using the configured Ollama
    embedding model and stored locally in Chroma.
    """

    if not chunks:
        raise ValueError(
            "Cannot create a vector store from an empty chunk list."
        )

    embedding_model = get_embedding_model()

    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embedding_model,
        collection_name=COLLECTION_NAME,
        persist_directory=str(VECTOR_STORE_DIRECTORY),
    )

    return vector_store


def load_vector_store() -> Chroma:
    """
    Load the existing persistent Chroma vector store.
    """

    if not VECTOR_STORE_DIRECTORY.exists():
        raise FileNotFoundError(
            "Chroma vector store not found. "
            "Create it before attempting to load it."
        )

    embedding_model = get_embedding_model()

    vector_store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embedding_model,
        persist_directory=str(VECTOR_STORE_DIRECTORY),
    )

    return vector_store