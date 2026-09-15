from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


# Initial chunking configuration
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150


def split_documents(
    documents: list[Document],
) -> list[Document]:
    """
    Split documents into smaller chunks for embedding and retrieval.

    The original document metadata is preserved automatically by the
    RecursiveCharacterTextSplitter.
    """

    if not documents:
        return []

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=[
            "\n\n",
            "\n",
            ". ",
            " ",
            "",
        ],
    )

    chunks = text_splitter.split_documents(documents)

    return chunks