from typing import Any
from langchain_core.documents import Document
from langchain_chroma import Chroma

from rag.vector_store import load_vector_store

# Number of relevant chunks to retrieve per query
DEFAULT_K = 4

def get_retriever(
    vector_store: Chroma | None = None,
    k: int = DEFAULT_K,
):
    """
    Create and return a retriever for the Chroma vector store.

    If no vector store is provided, the existing persistent vector store
    will be loaded. The retriever will return the top-k most relevant
    document chunks for a given query.
    """

    if vector_store is None:
        vector_store = load_vector_store()

    return vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": k},
    )


def retrieve_relevant_chunks(
    query: str,
    vector_store: Chroma | None = None,
    k: int = DEFAULT_K,
) -> list[dict[str, Any]]:
    """
    Accept a user question, query Chroma, and return relevant document chunks
    along with extracted metadata (filename, page, source).
    """
    if vector_store is None:
        vector_store = load_vector_store()

    # Perform similarity search to fetch LangChain Document chunks
    docs: list[Document] = vector_store.similarity_search(query, k=k)

    results = []
    for doc in docs:
        results.append(
            {
                "content": doc.page_content,
                "filename": doc.metadata.get("filename", "Unknown"),
                "page": doc.metadata.get("page", None),
                "source": doc.metadata.get("source", "Unknown"),
            }
        )

    return results

def format_context_for_prompt(chunks: list[dict[str, Any]]) -> str:
    """
    Format retrieved chunks and metadata into a clean text block
    ready for LLM prompt injection in Step 8.
    """
    if not chunks:
        return "No relevant documents found."

    formatted_entries = []
    for index, chunk in enumerate(chunks, start=1):
        source_label = chunk["filename"]
        if chunk["page"] is not None:
            source_label += f" (Page {chunk['page']})"

        formatted_entries.append(
            f"--- Document Chunk {index} [{source_label}] ---\n"
            f"{chunk['content'].strip()}"
        )

    return "\n\n".join(formatted_entries)


if __name__ == "__main__":
    test_query = input("Enter a test query to search documents: ").strip()
    if test_query:
        print("\n[INFO] Querying vector store...")
        retrieved = retrieve_relevant_chunks(test_query, k=3)
        print(f"[OK] Retrieved {len(retrieved)} chunk(s):\n")
        print(format_context_for_prompt(retrieved))